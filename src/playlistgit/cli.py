from __future__ import annotations

from pathlib import Path
from typing import Annotated, Callable

import typer
from rich.console import Console
from rich.table import Table

from playlistgit.adapters import SpotifyAdapter, YouTubeMusicAdapter
from playlistgit.config import init_config, load_config, resolve_path
from playlistgit.matcher import score_tracks
from playlistgit.models import PlaylistRef, PlaylistSnapshot, Service, Track, TrackMatch
from playlistgit.store import Store
from playlistgit.sync import diff_snapshots

app = typer.Typer(no_args_is_help=True)
console = Console()


def root() -> Path:
    return Path.cwd()


def store() -> Store:
    cfg = load_config(root())
    return Store(resolve_path(root(), cfg.sync.database))


def configured_playlists() -> list[PlaylistRef]:
    playlists = load_config(root()).playlists
    return [playlist for playlist in playlists if playlist.spotify_id and playlist.youtube_music_id]


def spotify_adapter() -> SpotifyAdapter:
    cfg = load_config(root())
    return SpotifyAdapter(cfg.spotify, resolve_path(root(), ".playlistgit/spotify_token_cache"))


def ytmusic_adapter() -> YouTubeMusicAdapter:
    cfg = load_config(root())
    return YouTubeMusicAdapter(resolve_path(root(), cfg.youtube_music.auth_file))


@app.command()
def init() -> None:
    """Create local config files."""
    path = init_config(root())
    console.print(f"Config ready at [bold]{path}[/bold]")
    console.print("Next: edit it with your Spotify credentials and playlist IDs, then run `playlistgit doctor`.")


@app.command()
def ui() -> None:
    """Launch the interactive terminal app."""
    from playlistgit.tui import run

    run()


@app.command()
def doctor() -> None:
    """Check whether local setup is ready to sync."""
    cfg = load_config(root())
    checks = [
        ("Spotify client ID", bool(cfg.spotify.client_id)),
        ("Spotify redirect URI", bool(cfg.spotify.redirect_uri)),
        (
            "YouTube Music auth file",
            resolve_path(root(), cfg.youtube_music.auth_file).exists(),
        ),
        ("At least one playlist mapping", bool(configured_playlists())),
    ]

    table = Table(title="Setup Doctor")
    table.add_column("Check")
    table.add_column("Status")
    for name, passed in checks:
        table.add_row(name, "ok" if passed else "missing")
    console.print(table)

    if all(passed for _, passed in checks):
        console.print("Ready. Run `playlistgit sync` to preview changes.")
    else:
        console.print("Fix missing items in `.playlistgit/config.toml` before syncing.")


@app.command()
def status() -> None:
    """Show configured playlists and latest local snapshots."""
    cfg = load_config(root())
    db = Store(resolve_path(root(), cfg.sync.database))

    table = Table(title="Playlist Git Status")
    table.add_column("Playlist")
    table.add_column("Spotify")
    table.add_column("YouTube Music")
    table.add_column("Latest Spotify Snapshot")
    table.add_column("Latest YTMusic Snapshot")

    for playlist in cfg.playlists:
        spotify = db.latest_snapshot(playlist.name, Service.SPOTIFY)
        ytmusic = db.latest_snapshot(playlist.name, Service.YOUTUBE_MUSIC)
        table.add_row(
            playlist.name,
            "set" if playlist.spotify_id else "missing",
            "set" if playlist.youtube_music_id else "missing",
            _snapshot_label(spotify),
            _snapshot_label(ytmusic),
        )
    console.print(table)


@app.command()
def snapshot() -> None:
    """Fetch and store current playlist state from Spotify and YouTube Music."""
    cfg = load_config(root())
    db = Store(resolve_path(root(), cfg.sync.database))
    spotify = spotify_adapter()
    ytmusic = ytmusic_adapter()

    for playlist in configured_playlists():
        spotify_tracks = spotify.get_playlist_tracks(playlist.spotify_id or "")
        ytmusic_tracks = ytmusic.get_playlist_tracks(playlist.youtube_music_id or "")
        spotify_id = db.save_snapshot(
            PlaylistSnapshot(
                playlist_name=playlist.name,
                service=Service.SPOTIFY,
                service_playlist_id=playlist.spotify_id or "",
                tracks=spotify_tracks,
            )
        )
        ytmusic_id = db.save_snapshot(
            PlaylistSnapshot(
                playlist_name=playlist.name,
                service=Service.YOUTUBE_MUSIC,
                service_playlist_id=playlist.youtube_music_id or "",
                tracks=ytmusic_tracks,
            )
        )
        console.print(
            f"{playlist.name}: saved Spotify snapshot {spotify_id} ({len(spotify_tracks)} tracks), "
            f"YouTube Music snapshot {ytmusic_id} ({len(ytmusic_tracks)} tracks)"
        )


@app.command("diff")
def diff_command() -> None:
    """Show tracks that appear to exist on only one service."""
    cfg = load_config(root())
    db = Store(resolve_path(root(), cfg.sync.database))
    for playlist in configured_playlists():
        spotify = db.latest_snapshot(playlist.name, Service.SPOTIFY)
        ytmusic = db.latest_snapshot(playlist.name, Service.YOUTUBE_MUSIC)
        if not spotify or not ytmusic:
            console.print(f"{playlist.name}: missing snapshots. Run `playlistgit snapshot` first.")
            continue
        render_diff(diff_snapshots(spotify, ytmusic, cfg.sync.match_threshold))


@app.command()
def sync(
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Actually write additions to remote playlists."),
    ] = False,
) -> None:
    """Add missing tracks in both directions. Deletes are not automated."""
    cfg = load_config(root())
    db = Store(resolve_path(root(), cfg.sync.database))
    spotify = spotify_adapter()
    ytmusic = ytmusic_adapter()
    dry_run = not apply

    for playlist in configured_playlists():
        spotify_snapshot = PlaylistSnapshot(
            playlist_name=playlist.name,
            service=Service.SPOTIFY,
            service_playlist_id=playlist.spotify_id or "",
            tracks=spotify.get_playlist_tracks(playlist.spotify_id or ""),
        )
        ytmusic_snapshot = PlaylistSnapshot(
            playlist_name=playlist.name,
            service=Service.YOUTUBE_MUSIC,
            service_playlist_id=playlist.youtube_music_id or "",
            tracks=ytmusic.get_playlist_tracks(playlist.youtube_music_id or ""),
        )
        db.save_snapshot(spotify_snapshot)
        db.save_snapshot(ytmusic_snapshot)

        diff = diff_snapshots(spotify_snapshot, ytmusic_snapshot, cfg.sync.match_threshold)
        render_diff(diff)

        to_ytmusic = resolve_missing(diff.spotify_only, ytmusic.search_track, cfg.sync.match_threshold)
        to_spotify = resolve_missing(diff.youtube_music_only, spotify.search_track, cfg.sync.match_threshold)

        added_yt = ytmusic.add_tracks(playlist.youtube_music_id or "", to_ytmusic, dry_run=dry_run)
        added_spotify = spotify.add_tracks(playlist.spotify_id or "", to_spotify, dry_run=dry_run)

        prefix = "Would add" if dry_run else "Added"
        console.print(f"{playlist.name}: {prefix} {len(added_yt)} to YouTube Music")
        console.print(f"{playlist.name}: {prefix} {len(added_spotify)} to Spotify")


@app.command()
def log() -> None:
    """Show recent local playlist snapshots."""
    rows = store().list_snapshots()
    table = Table(title="Recent Snapshots")
    table.add_column("ID")
    table.add_column("Playlist")
    table.add_column("Service")
    table.add_column("Tracks")
    table.add_column("Fetched")
    for row in rows:
        table.add_row(
            str(row["id"]),
            row["playlist_name"],
            row["service"],
            str(row["track_count"]),
            row["fetched_at"],
        )
    console.print(table)


def resolve_missing(
    matches: list[TrackMatch],
    search: Callable[[Track], Track | None],
    threshold: int,
) -> list[Track]:
    resolved: list[Track] = []
    for match in matches:
        candidate = search(match.source)
        if not candidate:
            console.print(f"Unresolved: {format_track(match.source)}")
            continue
        score = score_tracks(match.source, candidate)
        if score >= threshold:
            resolved.append(candidate)
        else:
            console.print(
                f"Low confidence ({score:.0f}): {format_track(match.source)} -> {format_track(candidate)}"
            )
    return resolved


def render_diff(diff) -> None:
    table = Table(title=f"Diff: {diff.playlist_name}")
    table.add_column("Side")
    table.add_column("Track")
    table.add_column("Best Existing Match")
    table.add_column("Score")

    for match in diff.spotify_only:
        table.add_row("Spotify only", format_track(match.source), _target_label(match), f"{match.score:.0f}")
    for match in diff.youtube_music_only:
        table.add_row("YTMusic only", format_track(match.source), _target_label(match), f"{match.score:.0f}")

    if not diff.spotify_only and not diff.youtube_music_only:
        table.add_row("Synced", "No additive differences found", "", "")
    console.print(table)


def format_track(track: Track) -> str:
    return f"{track.title} - {track.artist_text}"


def _target_label(match: TrackMatch) -> str:
    return format_track(match.target) if match.target else "none"


def _snapshot_label(snapshot: PlaylistSnapshot | None) -> str:
    if not snapshot:
        return "none"
    return f"{len(snapshot.tracks)} tracks @ {snapshot.fetched_at:%Y-%m-%d %H:%M}"
