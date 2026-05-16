# Product Direction

The best consumer version of Playlist Git should be a local desktop app, not an npm-first developer tool.

## Why Local Desktop

- Users need to connect personal Spotify and YouTube Music accounts.
- Credentials should stay on the user's machine.
- A website would require backend account storage, OAuth review, hosting, abuse protection, and privacy work before it is trustworthy.
- npm is acceptable for developers, but it is not friendly for non-technical users.

## Recommended Path

1. Keep the Python TUI as the fast iteration surface.
2. Move the same sync engine behind a small desktop app.
3. Package the desktop app for macOS first, then Windows.
4. Keep CLI/TUI commands for power users and automation.

## Target UX

- No manual playlist IDs.
- No config-file editing for normal users.
- Clear preview before writes.
- Additive sync by default.
- Deletions require explicit confirmation.
- Plain-language results: "3 songs will be added to Spotify, 2 songs will be added to YouTube Music."

