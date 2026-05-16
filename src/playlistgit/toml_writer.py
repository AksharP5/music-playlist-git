from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playlistgit.config import AppConfig

def dump_config(config: AppConfig) -> str:
    lines = [
        "[sync]",
        f'database = "{config.sync.database}"',
        f"match_threshold = {config.sync.match_threshold}",
        "",
        "[spotify]",
        f'client_id = "{_escape(config.spotify.client_id)}"',
        f'client_secret = "{_escape(config.spotify.client_secret)}"',
        f'redirect_uri = "{_escape(config.spotify.redirect_uri)}"',
        "",
        "[youtube_music]",
        f'auth_file = "{_escape(config.youtube_music.auth_file)}"',
        "",
    ]

    for playlist in config.playlists:
        lines.extend(
            [
                "[[playlists]]",
                f'name = "{_escape(playlist.name)}"',
                f'spotify_id = "{_escape(playlist.spotify_id or "")}"',
                f'youtube_music_id = "{_escape(playlist.youtube_music_id or "")}"',
                "",
            ]
        )
    return "\n".join(lines)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
