from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class Service(StrEnum):
    SPOTIFY = "spotify"
    YOUTUBE_MUSIC = "youtube_music"


class Track(BaseModel):
    title: str
    artists: list[str] = Field(default_factory=list)
    album: str | None = None
    duration_ms: int | None = None
    isrc: str | None = None
    spotify_id: str | None = None
    youtube_music_id: str | None = None
    source: Service | None = None

    @property
    def artist_text(self) -> str:
        return ", ".join(self.artists)

    @property
    def stable_key(self) -> str:
        if self.isrc:
            return f"isrc:{self.isrc.lower()}"
        if self.spotify_id:
            return f"spotify:{self.spotify_id}"
        if self.youtube_music_id:
            return f"ytmusic:{self.youtube_music_id}"
        return "text:" + "|".join(
            [
                self.title.casefold().strip(),
                self.artist_text.casefold().strip(),
                str(self.duration_ms or ""),
            ]
        )


class PlaylistRef(BaseModel):
    name: str
    spotify_id: str | None = None
    youtube_music_id: str | None = None


class RemotePlaylist(BaseModel):
    name: str
    service_playlist_id: str
    track_count: int | None = None


class PlaylistSnapshot(BaseModel):
    playlist_name: str
    service: Service
    service_playlist_id: str
    tracks: list[Track]
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrackMatch(BaseModel):
    source: Track
    target: Track | None
    score: float
    reason: str


class PlaylistDiff(BaseModel):
    playlist_name: str
    spotify_only: list[TrackMatch] = Field(default_factory=list)
    youtube_music_only: list[TrackMatch] = Field(default_factory=list)
    shared_count: int = 0
