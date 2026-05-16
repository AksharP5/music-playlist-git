from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

from playlistgit.models import PlaylistRef


DEFAULT_CONFIG = """[sync]
database = ".playlistgit/playlistgit.db"
match_threshold = 88

[spotify]
client_id = ""
client_secret = ""
redirect_uri = "http://127.0.0.1:8080/callback"

[youtube_music]
auth_file = ".playlistgit/headers_auth.json"

[[playlists]]
name = "Main"
spotify_id = ""
youtube_music_id = ""
"""


class SyncConfig(BaseModel):
    database: str = ".playlistgit/playlistgit.db"
    match_threshold: int = 88


class SpotifyConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://127.0.0.1:8080/callback"


class YouTubeMusicConfig(BaseModel):
    auth_file: str = ".playlistgit/headers_auth.json"


class AppConfig(BaseModel):
    sync: SyncConfig = Field(default_factory=SyncConfig)
    spotify: SpotifyConfig = Field(default_factory=SpotifyConfig)
    youtube_music: YouTubeMusicConfig = Field(default_factory=YouTubeMusicConfig)
    playlists: list[PlaylistRef] = Field(default_factory=list)


def config_dir(root: Path) -> Path:
    return root / ".playlistgit"


def config_path(root: Path) -> Path:
    return config_dir(root) / "config.toml"


def init_config(root: Path) -> Path:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return path


def load_config(root: Path) -> AppConfig:
    path = config_path(root)
    if not path.exists():
        raise FileNotFoundError(f"Missing config at {path}. Run `playlistgit init` first.")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)


def resolve_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return root / path

