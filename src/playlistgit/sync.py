from __future__ import annotations

from playlistgit.matcher import match_track
from playlistgit.models import PlaylistDiff, PlaylistSnapshot, Track, TrackMatch


def diff_snapshots(
    spotify: PlaylistSnapshot,
    youtube_music: PlaylistSnapshot,
    threshold: int,
) -> PlaylistDiff:
    spotify_only = unmatched_tracks(spotify.tracks, youtube_music.tracks, threshold)
    youtube_only = unmatched_tracks(youtube_music.tracks, spotify.tracks, threshold)
    shared_count = max(0, min(len(spotify.tracks), len(youtube_music.tracks)) - len(spotify_only))
    return PlaylistDiff(
        playlist_name=spotify.playlist_name,
        spotify_only=spotify_only,
        youtube_music_only=youtube_only,
        shared_count=shared_count,
    )


def unmatched_tracks(source: list[Track], target: list[Track], threshold: int) -> list[TrackMatch]:
    target_by_key = {track.stable_key: track for track in target}
    unmatched: list[TrackMatch] = []

    for track in source:
        if track.stable_key in target_by_key:
            continue
        match = match_track(track, target)
        if match.score < threshold:
            unmatched.append(match)
    return unmatched

