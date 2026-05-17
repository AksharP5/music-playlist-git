from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir


APP_AUTHOR = "PlaylistGit"
APP_NAME = "Playlist Git"


def desktop_data_root() -> Path:
    root = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    root.mkdir(parents=True, exist_ok=True)
    return root
