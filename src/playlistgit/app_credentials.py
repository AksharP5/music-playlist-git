from __future__ import annotations

import os
from dataclasses import dataclass


# Public OAuth app credentials for packaged builds.
#
# These are intentionally blank in the open-source repo. A release build should set them through
# environment variables or a private build-time patch. End users should never type these values.
BUNDLED_SPOTIFY_CLIENT_ID = ""
BUNDLED_GOOGLE_CLIENT_ID = ""
BUNDLED_GOOGLE_CLIENT_SECRET = ""


@dataclass(frozen=True)
class AppCredentials:
    spotify_client_id: str
    google_client_id: str
    google_client_secret: str

    @property
    def has_spotify(self) -> bool:
        return bool(self.spotify_client_id)

    @property
    def has_google(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


def app_credentials() -> AppCredentials:
    return AppCredentials(
        spotify_client_id=os.getenv("PLAYLISTGIT_SPOTIFY_CLIENT_ID", BUNDLED_SPOTIFY_CLIENT_ID),
        google_client_id=os.getenv("PLAYLISTGIT_GOOGLE_CLIENT_ID", BUNDLED_GOOGLE_CLIENT_ID),
        google_client_secret=os.getenv("PLAYLISTGIT_GOOGLE_CLIENT_SECRET", BUNDLED_GOOGLE_CLIENT_SECRET),
    )
