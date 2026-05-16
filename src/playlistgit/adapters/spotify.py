from __future__ import annotations

from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from playlistgit.config import SpotifyConfig
from playlistgit.models import Service, Track


SCOPES = "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"


class SpotifyAdapter:
    def __init__(self, config: SpotifyConfig, cache_path: Path) -> None:
        if not config.client_id or not config.client_secret:
            raise ValueError("Spotify client_id/client_secret are required in .playlistgit/config.toml")

        auth = SpotifyOAuth(
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            scope=SCOPES,
            cache_path=str(cache_path),
            open_browser=True,
        )
        self.client = spotipy.Spotify(auth_manager=auth)

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        fields = (
            "items(track(id,name,album(name),artists(name),duration_ms,external_ids(isrc))),"
            "next"
        )
        response = self.client.playlist_items(playlist_id, fields=fields, additional_types=("track",))
        tracks: list[Track] = []

        while response:
            for item in response["items"]:
                raw = item.get("track")
                if not raw or not raw.get("id"):
                    continue
                tracks.append(
                    Track(
                        title=raw["name"],
                        artists=[artist["name"] for artist in raw.get("artists", [])],
                        album=(raw.get("album") or {}).get("name"),
                        duration_ms=raw.get("duration_ms"),
                        isrc=(raw.get("external_ids") or {}).get("isrc"),
                        spotify_id=raw["id"],
                        source=Service.SPOTIFY,
                    )
                )
            if response.get("next"):
                response = self.client.next(response)
            else:
                response = None
        return tracks

    def add_tracks(self, playlist_id: str, tracks: list[Track], dry_run: bool = True) -> list[Track]:
        ids = [track.spotify_id for track in tracks if track.spotify_id]
        if dry_run or not ids:
            return [track for track in tracks if track.spotify_id]

        for start in range(0, len(ids), 100):
            self.client.playlist_add_items(playlist_id, ids[start : start + 100])
        return [track for track in tracks if track.spotify_id]

    def search_track(self, track: Track) -> Track | None:
        query = f'track:"{track.title}" artist:"{track.artist_text}"'
        result = self.client.search(q=query, type="track", limit=5)
        items = result.get("tracks", {}).get("items", [])
        if not items:
            return None

        raw = items[0]
        return Track(
            title=raw["name"],
            artists=[artist["name"] for artist in raw.get("artists", [])],
            album=(raw.get("album") or {}).get("name"),
            duration_ms=raw.get("duration_ms"),
            isrc=(raw.get("external_ids") or {}).get("isrc"),
            spotify_id=raw["id"],
            source=Service.SPOTIFY,
        )

