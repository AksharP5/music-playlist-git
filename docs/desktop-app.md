# Desktop App

Playlist Git should ship as a free local desktop app. The current implementation uses PySide6 for the app shell and PyInstaller for packaging.

## Why This Route

- Free and open-source friendly.
- No hosted backend is required.
- Spotify and YouTube Music tokens stay on the user's computer.
- The existing Python sync engine can be reused directly.
- The CLI and TUI remain available for power users.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[desktop,dev]"
playlistgit desktop
```

You can also run:

```bash
playlistgit-desktop
```

## Build A macOS App Bundle

```bash
source .venv/bin/activate
pip install -e ".[desktop]"
pyinstaller packaging/pyinstaller/playlistgit.spec
```

The output appears under:

```text
dist/Playlist Git.app
```

## User Data

The desktop app stores local config, OAuth tokens, and the SQLite sync database in the operating system's user data folder through `platformdirs`.

No credentials should be committed to git.

## Current Auth Limitation

Spotify now uses PKCE, so no client secret is required. During local development, a Spotify client ID is still required. A released app should register a Playlist Git Spotify application and bundle that public client ID.

YouTube Music is harder because there is no clean official YouTube Music playlist API. The desktop app uses `ytmusicapi` OAuth/device login when a Google OAuth app ID is bundled.

## Developer Credentials

End users should not type OAuth IDs, secrets, redirect URLs, or auth file paths. Developer builds read app credentials from environment variables:

```bash
export PLAYLISTGIT_SPOTIFY_CLIENT_ID="..."
export PLAYLISTGIT_GOOGLE_CLIENT_ID="..."
export PLAYLISTGIT_GOOGLE_CLIENT_SECRET="..."
playlistgit desktop
```

For public releases, these values should be provided by the release build, not by the user.
