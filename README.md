# Playlist Git

Git-like playlist syncing for Spotify and YouTube Music.

This is an early local desktop/TUI/CLI app for people who want their playlists to survive switching music apps. It keeps local SQLite snapshots, compares Spotify and YouTube Music, and can add missing songs in both directions.

The intended product experience is simple:

1. Open the app.
2. Sign in to Spotify.
3. Connect YouTube Music.
4. Load playlists from both services.
5. Pick the two playlists that should stay together.
6. Preview sync.
7. Sync now.

The first sync policy is intentionally conservative:

- Additive sync only.
- No automatic deletes.
- Low-confidence matches are reported instead of written.
- Credentials and local database files are excluded from git.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playlistgit init
playlistgit desktop
```

For the terminal UI:

```bash
playlistgit ui
```

The desktop app is the intended normal-user surface. The terminal app remains available for development and power users.

You can also edit the config directly:

```text
.playlistgit/config.toml
```

Add your Spotify credentials, then use the app to load and select playlists. Raw playlist IDs are saved behind the scenes.

Check setup:

```bash
playlistgit doctor
```

Preview sync:

```bash
playlistgit sync
```

Actually sync additions:

```bash
playlistgit sync --apply
```

That default matters: `playlistgit sync` is a dry run. It shows what would be added without changing Spotify or YouTube Music.

## Authentication

Yes, you need to log in to both services.

### Spotify

Create a Spotify app at the Spotify developer dashboard. Set a redirect URI such as:

```text
http://127.0.0.1:8080/callback
```

For local development, put your Spotify client ID in the app. Playlist Git uses Spotify PKCE, so a client secret is not required for the normal local flow.

```toml
[spotify]
client_id = "..."
redirect_uri = "http://127.0.0.1:8080/callback"
```

The first command that touches Spotify will open an OAuth flow in your browser and cache the token under `.playlistgit/`.

### YouTube Music

This uses `ytmusicapi`, the same underlying approach as `linsomniac/spotify_to_ytmusic`.

Generate browser-header auth:

```bash
ytmusicapi browser
```

Save the generated file as:

```text
.playlistgit/headers_auth.json
```

This auth method is unofficial because YouTube Music does not provide the same clean public playlist API that Spotify does.

## Usage

Interactive app:

```bash
playlistgit ui
```

CLI commands:

```bash
playlistgit status
playlistgit snapshot
playlistgit diff
playlistgit sync
playlistgit sync --apply
playlistgit log
```

## Config Example

```toml
[sync]
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
spotify_id = "spotify_playlist_id"
youtube_music_id = "youtube_music_playlist_id"
```
