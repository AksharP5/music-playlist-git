from __future__ import annotations

import json
import time
import webbrowser
from pathlib import Path

from ytmusicapi.auth.oauth import OAuthCredentials


class YouTubeMusicOAuth:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.credentials = OAuthCredentials(client_id, client_secret)

    def begin(self) -> tuple[str, str, str]:
        code = self.credentials.get_code()
        verification_url = code["verification_url"]
        user_code = code["user_code"]
        device_code = code["device_code"]
        webbrowser.open(f"{verification_url}?user_code={user_code}")
        return verification_url, user_code, device_code

    def finish(self, device_code: str, output_path: Path) -> None:
        token = self.credentials.token_from_code(device_code)
        token["expires_at"] = int(time.time()) + int(token.get("expires_in", 0))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(token, indent=2), encoding="utf-8")
