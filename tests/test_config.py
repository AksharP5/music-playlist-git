from pathlib import Path

from playlistgit.config import AppConfig, load_config, save_config
from playlistgit.models import PlaylistRef


def test_save_config_round_trips(tmp_path: Path) -> None:
    config = AppConfig(
        playlists=[
            PlaylistRef(
                name="Main",
                spotify_id="spotify-playlist",
                youtube_music_id="yt-playlist",
            )
        ]
    )
    config.spotify.client_id = "client"
    config.spotify.client_secret = "secret"

    save_config(tmp_path, config)
    loaded = load_config(tmp_path)

    assert loaded.spotify.client_id == "client"
    assert loaded.spotify.client_secret == "secret"
    assert loaded.playlists[0].spotify_id == "spotify-playlist"
    assert loaded.playlists[0].youtube_music_id == "yt-playlist"
