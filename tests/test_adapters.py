from pathlib import Path

from playlistgit.adapters.spotify import SpotifyAdapter
from playlistgit.adapters.ytmusic import YouTubeMusicAdapter


def test_spotify_list_playlists_parses_current_user_playlists() -> None:
    adapter = object.__new__(SpotifyAdapter)
    adapter.client = FakeSpotifyClient()

    playlists = adapter.list_playlists()

    assert playlists[0].name == "Liked-ish"
    assert playlists[0].service_playlist_id == "sp1"
    assert playlists[0].track_count == 12


def test_ytmusic_list_playlists_parses_library_playlists(tmp_path: Path) -> None:
    auth_file = tmp_path / "headers_auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    adapter = object.__new__(YouTubeMusicAdapter)
    adapter.client = FakeYTMusicClient()

    playlists = adapter.list_playlists()

    assert playlists[0].name == "Driving"
    assert playlists[0].service_playlist_id == "yt1"
    assert playlists[0].track_count == 42


class FakeSpotifyClient:
    def current_user_playlists(self, limit: int = 50, offset: int = 0):
        return {
            "items": [
                {
                    "id": "sp1",
                    "name": "Liked-ish",
                    "tracks": {"total": 12},
                }
            ],
            "next": None,
        }

    def next(self, response):
        return None


class FakeYTMusicClient:
    def get_library_playlists(self, limit=None):
        return [
            {
                "playlistId": "yt1",
                "title": "Driving",
                "count": 42,
            }
        ]

