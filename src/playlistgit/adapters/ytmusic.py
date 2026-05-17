from __future__ import annotations

from pathlib import Path

from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials

from playlistgit.models import RemotePlaylist, Service, Track


class YouTubeMusicAdapter:
    def __init__(
        self,
        auth_file: Path,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
    ) -> None:
        if not auth_file.exists():
            raise FileNotFoundError(
                f"Missing YouTube Music auth file at {auth_file}. Run `ytmusicapi browser` first."
            )
        oauth_credentials = None
        if oauth_client_id and oauth_client_secret:
            oauth_credentials = OAuthCredentials(oauth_client_id, oauth_client_secret)
        self.client = YTMusic(str(auth_file), oauth_credentials=oauth_credentials)

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        playlist = self.client.get_playlist(playlist_id, limit=None)
        tracks: list[Track] = []
        for raw in playlist.get("tracks", []):
            video_id = raw.get("videoId")
            if not video_id:
                continue
            tracks.append(
                Track(
                    title=raw.get("title") or "",
                    artists=[artist["name"] for artist in raw.get("artists", []) if artist.get("name")],
                    album=(raw.get("album") or {}).get("name"),
                    duration_ms=_duration_to_ms(raw.get("duration")),
                    youtube_music_id=video_id,
                    source=Service.YOUTUBE_MUSIC,
                )
            )
        return tracks

    def list_playlists(self) -> list[RemotePlaylist]:
        playlists: list[RemotePlaylist] = []
        for raw in self.client.get_library_playlists(limit=None):
            playlist_id = raw.get("playlistId")
            if not playlist_id:
                continue
            playlists.append(
                RemotePlaylist(
                    name=raw.get("title") or "Untitled playlist",
                    service_playlist_id=playlist_id,
                    track_count=raw.get("count"),
                )
            )
        return playlists

    def add_tracks(self, playlist_id: str, tracks: list[Track], dry_run: bool = True) -> list[Track]:
        ids = [track.youtube_music_id for track in tracks if track.youtube_music_id]
        if dry_run or not ids:
            return [track for track in tracks if track.youtube_music_id]

        self.client.add_playlist_items(playlist_id, ids, duplicates=False)
        return [track for track in tracks if track.youtube_music_id]

    def search_track(self, track: Track) -> Track | None:
        query = f"{track.title} {track.artist_text}"
        results = self.client.search(query, filter="songs", limit=5)
        if not results:
            results = self.client.search(query, filter="videos", limit=5)
        if not results:
            return None

        raw = results[0]
        return Track(
            title=raw.get("title") or "",
            artists=[artist["name"] for artist in raw.get("artists", []) if artist.get("name")],
            album=(raw.get("album") or {}).get("name"),
            duration_ms=_duration_to_ms(raw.get("duration")),
            youtube_music_id=raw.get("videoId"),
            source=Service.YOUTUBE_MUSIC,
        )


def _duration_to_ms(duration: str | None) -> int | None:
    if not duration:
        return None
    parts = [int(part) for part in duration.split(":")]
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds * 1000
