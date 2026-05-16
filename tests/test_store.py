from pathlib import Path

from playlistgit.models import PlaylistSnapshot, Service, Track
from playlistgit.store import Store


def test_store_round_trips_latest_snapshot(tmp_path: Path) -> None:
    store = Store(tmp_path / "playlistgit.db")
    snapshot = PlaylistSnapshot(
        playlist_name="Main",
        service=Service.SPOTIFY,
        service_playlist_id="sp",
        tracks=[Track(title="Song", artists=["Artist"], spotify_id="123")],
    )

    store.save_snapshot(snapshot)
    latest = store.latest_snapshot("Main", Service.SPOTIFY)

    assert latest is not None
    assert latest.tracks[0].title == "Song"
    assert latest.tracks[0].spotify_id == "123"

