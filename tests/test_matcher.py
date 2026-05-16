from playlistgit.matcher import match_track, score_tracks
from playlistgit.models import Track


def test_match_track_prefers_isrc() -> None:
    source = Track(title="Song", artists=["Artist"], isrc="ABC123")
    candidates = [
        Track(title="Different", artists=["Someone"], isrc="NOPE"),
        Track(title="Song Remaster", artists=["Artist"], isrc="ABC123"),
    ]

    match = match_track(source, candidates)

    assert match.score == 100
    assert match.reason == "isrc"
    assert match.target == candidates[1]


def test_score_tracks_uses_text_and_duration() -> None:
    left = Track(title="Midnight City", artists=["M83"], album="Hurry Up", duration_ms=243000)
    right = Track(title="Midnight City", artists=["M83"], album="Hurry Up", duration_ms=244000)

    assert score_tracks(left, right) > 95

