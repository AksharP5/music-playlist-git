from __future__ import annotations

from rapidfuzz import fuzz

from playlistgit.models import Track, TrackMatch


def match_track(source: Track, candidates: list[Track]) -> TrackMatch:
    for candidate in candidates:
        if source.isrc and candidate.isrc and source.isrc.casefold() == candidate.isrc.casefold():
            return TrackMatch(source=source, target=candidate, score=100, reason="isrc")

    best: Track | None = None
    best_score = 0.0
    for candidate in candidates:
        score = score_tracks(source, candidate)
        if score > best_score:
            best = candidate
            best_score = score

    return TrackMatch(source=source, target=best, score=best_score, reason="fuzzy")


def score_tracks(left: Track, right: Track) -> float:
    title = fuzz.token_set_ratio(left.title, right.title)
    artist = fuzz.token_set_ratio(left.artist_text, right.artist_text)
    album = fuzz.token_set_ratio(left.album or "", right.album or "") if left.album or right.album else 75
    duration = duration_score(left.duration_ms, right.duration_ms)
    return (title * 0.45) + (artist * 0.35) + (album * 0.10) + (duration * 0.10)


def duration_score(left: int | None, right: int | None) -> float:
    if not left or not right:
        return 70
    delta = abs(left - right)
    if delta <= 2000:
        return 100
    if delta >= 30000:
        return 0
    return max(0, 100 - (delta / 300))

