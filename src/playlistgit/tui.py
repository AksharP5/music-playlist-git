from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Log, Static

from playlistgit.adapters import SpotifyAdapter, YouTubeMusicAdapter
from playlistgit.config import init_config, load_config, resolve_path, save_config
from playlistgit.matcher import score_tracks
from playlistgit.models import PlaylistRef, PlaylistSnapshot, Service
from playlistgit.store import Store
from playlistgit.sync import diff_snapshots


class PlaylistGitTUI(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    .panel {
        border: solid $accent;
        padding: 1 2;
        height: auto;
    }

    #left {
        width: 42%;
    }

    #right {
        width: 58%;
    }

    Input {
        margin-bottom: 1;
    }

    Button {
        margin-right: 1;
        margin-bottom: 1;
    }

    #log {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "doctor", "Doctor"),
        ("s", "sync_preview", "Preview Sync"),
        ("a", "sync_apply", "Apply Sync"),
    ]

    def __init__(self, project_root: Path | None = None) -> None:
        super().__init__()
        self.project_root = project_root or Path.cwd()
        init_config(self.project_root)
        self.config = load_config(self.project_root)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Static("Setup", classes="panel")
                yield Label("Spotify Client ID")
                yield Input(value=self.config.spotify.client_id, id="spotify_client_id")
                yield Label("Spotify Client Secret")
                yield Input(
                    value=self.config.spotify.client_secret,
                    password=True,
                    id="spotify_client_secret",
                )
                yield Label("Spotify Redirect URI")
                yield Input(value=self.config.spotify.redirect_uri, id="spotify_redirect_uri")
                yield Label("YouTube Music Auth File")
                yield Input(value=self.config.youtube_music.auth_file, id="ytmusic_auth_file")

                yield Static("Playlist Mapping", classes="panel")
                first = self.config.playlists[0] if self.config.playlists else PlaylistRef(name="Main")
                yield Label("Playlist Name")
                yield Input(value=first.name, id="playlist_name")
                yield Label("Spotify Playlist ID")
                yield Input(value=first.spotify_id or "", id="spotify_playlist_id")
                yield Label("YouTube Music Playlist ID")
                yield Input(value=first.youtube_music_id or "", id="ytmusic_playlist_id")

                with Horizontal():
                    yield Button("Save Setup", id="save", variant="primary")
                    yield Button("Doctor", id="doctor")
                with Horizontal():
                    yield Button("Sign in Spotify", id="spotify_login")
                    yield Button("Check YouTube", id="ytmusic_login")
            with Vertical(id="right"):
                yield Static("Sync", classes="panel")
                with Horizontal():
                    yield Button("Preview Sync", id="preview", variant="primary")
                    yield Button("Sync Now", id="apply", variant="success")
                yield Log(id="log", highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        self.write_log("Playlist Git is ready.")
        self.write_log("Fill setup fields, save, run Doctor, then Preview Sync.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "save":
            self.save_form()
        elif button_id == "doctor":
            self.action_doctor()
        elif button_id == "spotify_login":
            self.check_spotify()
        elif button_id == "ytmusic_login":
            self.check_ytmusic()
        elif button_id == "preview":
            self.sync_worker(apply=False)
        elif button_id == "apply":
            self.sync_worker(apply=True)

    def action_doctor(self) -> None:
        self.save_form()
        cfg = self.config
        checks = [
            ("Spotify client ID", bool(cfg.spotify.client_id)),
            ("Spotify client secret", bool(cfg.spotify.client_secret)),
            ("Spotify redirect URI", bool(cfg.spotify.redirect_uri)),
            ("YouTube Music auth file", resolve_path(self.project_root, cfg.youtube_music.auth_file).exists()),
            ("Spotify playlist ID", bool(self.current_playlist().spotify_id)),
            ("YouTube Music playlist ID", bool(self.current_playlist().youtube_music_id)),
        ]
        for label, ok in checks:
            self.write_log(f"{'OK' if ok else 'MISSING'} - {label}")

    def action_sync_preview(self) -> None:
        self.sync_worker(apply=False)

    def action_sync_apply(self) -> None:
        self.sync_worker(apply=True)

    def save_form(self) -> None:
        cfg = self.config.model_copy(deep=True)
        cfg.spotify.client_id = self.input_value("spotify_client_id")
        cfg.spotify.client_secret = self.input_value("spotify_client_secret")
        cfg.spotify.redirect_uri = self.input_value("spotify_redirect_uri")
        cfg.youtube_music.auth_file = self.input_value("ytmusic_auth_file")
        cfg.playlists = [
            PlaylistRef(
                name=self.input_value("playlist_name") or "Main",
                spotify_id=self.input_value("spotify_playlist_id"),
                youtube_music_id=self.input_value("ytmusic_playlist_id"),
            )
        ]
        save_config(self.project_root, cfg)
        self.config = cfg
        self.write_log("Saved setup to .playlistgit/config.toml")

    @work(thread=True)
    def check_spotify(self) -> None:
        try:
            self.save_form()
            adapter = SpotifyAdapter(
                self.config.spotify,
                resolve_path(self.project_root, ".playlistgit/spotify_token_cache"),
            )
            self.call_from_thread(self.write_log, f"Spotify signed in as {adapter.display_name()}")
        except Exception as exc:
            self.call_from_thread(self.write_log, f"Spotify check failed: {exc}")

    @work(thread=True)
    def check_ytmusic(self) -> None:
        try:
            self.save_form()
            YouTubeMusicAdapter(resolve_path(self.project_root, self.config.youtube_music.auth_file))
            self.call_from_thread(self.write_log, "YouTube Music auth file loaded.")
        except Exception as exc:
            self.call_from_thread(self.write_log, f"YouTube Music check failed: {exc}")

    @work(thread=True)
    def sync_worker(self, apply: bool) -> None:
        try:
            self.save_form()
            cfg = self.config
            playlist = self.current_playlist()
            if not playlist.spotify_id or not playlist.youtube_music_id:
                self.call_from_thread(self.write_log, "Add both playlist IDs before syncing.")
                return

            self.call_from_thread(self.write_log, "Fetching Spotify and YouTube Music playlists...")
            spotify = SpotifyAdapter(cfg.spotify, resolve_path(self.project_root, ".playlistgit/spotify_token_cache"))
            ytmusic = YouTubeMusicAdapter(resolve_path(self.project_root, cfg.youtube_music.auth_file))
            db = Store(resolve_path(self.project_root, cfg.sync.database))

            spotify_snapshot = PlaylistSnapshot(
                playlist_name=playlist.name,
                service=Service.SPOTIFY,
                service_playlist_id=playlist.spotify_id,
                tracks=spotify.get_playlist_tracks(playlist.spotify_id),
            )
            ytmusic_snapshot = PlaylistSnapshot(
                playlist_name=playlist.name,
                service=Service.YOUTUBE_MUSIC,
                service_playlist_id=playlist.youtube_music_id,
                tracks=ytmusic.get_playlist_tracks(playlist.youtube_music_id),
            )
            db.save_snapshot(spotify_snapshot)
            db.save_snapshot(ytmusic_snapshot)

            diff = diff_snapshots(spotify_snapshot, ytmusic_snapshot, cfg.sync.match_threshold)
            self.call_from_thread(
                self.write_log,
                f"Found {len(diff.spotify_only)} Spotify-only and "
                f"{len(diff.youtube_music_only)} YouTube-only additions.",
            )

            if not apply:
                self.call_from_thread(self.write_log, "Preview complete. Press Sync Now to apply additions.")
                return

            # Keep apply conservative in the first UI: only add direct searched matches.
            to_yt = []
            for match in diff.spotify_only:
                found = ytmusic.search_track(match.source)
                if found and score_tracks(match.source, found) >= cfg.sync.match_threshold:
                    to_yt.append(found)
            to_spotify = []
            for match in diff.youtube_music_only:
                found = spotify.search_track(match.source)
                if found and score_tracks(match.source, found) >= cfg.sync.match_threshold:
                    to_spotify.append(found)

            ytmusic.add_tracks(playlist.youtube_music_id, to_yt, dry_run=False)
            spotify.add_tracks(playlist.spotify_id, to_spotify, dry_run=False)
            self.call_from_thread(
                self.write_log,
                f"Sync complete. Added {len(to_yt)} to YouTube Music and {len(to_spotify)} to Spotify.",
            )
        except Exception as exc:
            self.call_from_thread(self.write_log, f"Sync failed: {exc}")

    def input_value(self, widget_id: str) -> str:
        return self.query_one(f"#{widget_id}", Input).value.strip()

    def current_playlist(self) -> PlaylistRef:
        return self.config.playlists[0] if self.config.playlists else PlaylistRef(name="Main")

    def write_log(self, message: str) -> None:
        self.query_one("#log", Log).write_line(message)


def run() -> None:
    PlaylistGitTUI().run()
