from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from pathlib import Path

from playlistgit.adapters import SpotifyAdapter, YouTubeMusicAdapter
from playlistgit.app_credentials import app_credentials
from playlistgit.config import init_config, load_config, resolve_path, save_config
from playlistgit.matcher import score_tracks
from playlistgit.models import PlaylistRef, PlaylistSnapshot, RemotePlaylist, Service, Track
from playlistgit.paths import desktop_data_root
from playlistgit.store import Store
from playlistgit.sync import diff_snapshots
from playlistgit.ytmusic_oauth import YouTubeMusicOAuth


try:
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised by users without desktop extra.
    raise SystemExit(
        "Desktop dependencies are not installed. Run `pip install -e \".[desktop]\"` first."
    ) from exc


class UiBridge(QObject):
    log = Signal(str)
    busy = Signal(bool)
    spotify_playlists = Signal(list)
    ytmusic_playlists = Signal(list)


class PlaylistGitWindow(QMainWindow):
    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self.root = root or desktop_data_root()
        init_config(self.root)
        self.config = load_config(self.root)
        self.app_creds = app_credentials()
        self.bridge = UiBridge()
        self.bridge.log.connect(self.log)
        self.bridge.busy.connect(self.set_busy)
        self.bridge.spotify_playlists.connect(self.set_spotify_playlists)
        self.bridge.ytmusic_playlists.connect(self.set_ytmusic_playlists)

        self.setWindowTitle("Playlist Git")
        self.setMinimumSize(980, 680)
        self.spotify_items: dict[str, RemotePlaylist] = {}
        self.ytmusic_items: dict[str, RemotePlaylist] = {}
        self.buttons: list[QPushButton] = []
        self.build_ui()
        self.load_existing_selection()

    def build_ui(self) -> None:
        root_widget = QWidget()
        root_layout = QHBoxLayout(root_widget)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(16)
        right = QVBoxLayout()
        right.setSpacing(16)
        root_layout.addLayout(left, 2)
        root_layout.addLayout(right, 3)

        title = QLabel("Playlist Git")
        title.setObjectName("Title")
        subtitle = QLabel("Keep Spotify and YouTube Music playlists in sync from your own computer.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("Subtitle")
        left.addWidget(title)
        left.addWidget(subtitle)

        accounts = QGroupBox("1. Connect accounts")
        accounts_layout = QGridLayout(accounts)
        accounts_layout.setVerticalSpacing(10)
        spotify_status = "Ready" if self.app_creds.has_spotify else "Developer build missing Spotify app ID"
        accounts_layout.addWidget(QLabel("Spotify"), 0, 0)
        self.spotify_status = QLabel(spotify_status)
        self.spotify_status.setObjectName("Subtitle")
        accounts_layout.addWidget(self.spotify_status, 0, 1)
        self.spotify_button = QPushButton("Connect Spotify")
        self.spotify_button.clicked.connect(self.connect_spotify)
        accounts_layout.addWidget(self.spotify_button, 1, 1)

        youtube_status = "Ready" if self.app_creds.has_google else "Developer build missing Google app ID"
        accounts_layout.addWidget(QLabel("YouTube Music"), 2, 0)
        self.ytmusic_status = QLabel(youtube_status)
        self.ytmusic_status.setObjectName("Subtitle")
        accounts_layout.addWidget(self.ytmusic_status, 2, 1)
        self.ytmusic_button = QPushButton("Connect YouTube Music")
        self.ytmusic_button.clicked.connect(self.connect_ytmusic)
        accounts_layout.addWidget(self.ytmusic_button, 3, 1)
        left.addWidget(accounts)

        playlists = QGroupBox("2. Choose playlists")
        playlist_layout = QGridLayout(playlists)
        playlist_layout.addWidget(QLabel("Sync name"), 0, 0)
        first = self.config.playlists[0] if self.config.playlists else PlaylistRef(name="Main")
        self.sync_name = QLineEdit(first.name)
        playlist_layout.addWidget(self.sync_name, 0, 1)
        playlist_layout.addWidget(QLabel("Spotify"), 1, 0)
        self.spotify_combo = QComboBox()
        self.spotify_combo.setMinimumContentsLength(28)
        playlist_layout.addWidget(self.spotify_combo, 1, 1)
        self.load_spotify_button = QPushButton("Load Spotify playlists")
        self.load_spotify_button.clicked.connect(self.load_spotify_playlists)
        playlist_layout.addWidget(self.load_spotify_button, 2, 1)
        playlist_layout.addWidget(QLabel("YouTube Music"), 3, 0)
        self.ytmusic_combo = QComboBox()
        self.ytmusic_combo.setMinimumContentsLength(28)
        playlist_layout.addWidget(self.ytmusic_combo, 3, 1)
        self.load_ytmusic_button = QPushButton("Load YouTube playlists")
        self.load_ytmusic_button.clicked.connect(self.load_ytmusic_playlists)
        playlist_layout.addWidget(self.load_ytmusic_button, 4, 1)
        self.save_button = QPushButton("Save selection")
        self.save_button.clicked.connect(self.save_form)
        playlist_layout.addWidget(self.save_button, 5, 1)
        left.addWidget(playlists)

        sync_card = QGroupBox("3. Sync")
        sync_layout = QVBoxLayout(sync_card)
        help_text = QLabel(
            "Preview first. Sync Now only writes high-confidence additions and never deletes songs."
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("Subtitle")
        sync_layout.addWidget(help_text)
        button_row = QHBoxLayout()
        self.preview_button = QPushButton("Preview Sync")
        self.preview_button.clicked.connect(lambda: self.sync(apply=False))
        self.apply_button = QPushButton("Sync Now")
        self.apply_button.clicked.connect(lambda: self.sync(apply=True))
        button_row.addWidget(self.preview_button)
        button_row.addWidget(self.apply_button)
        sync_layout.addLayout(button_row)
        right.addWidget(sync_card)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Sync results will appear here.")
        right.addWidget(self.output, 1)

        footer = QLabel(f"Local data folder: {self.root}")
        footer.setObjectName("Footer")
        right.addWidget(footer)

        self.buttons = [
            self.spotify_button,
            self.ytmusic_button,
            self.load_spotify_button,
            self.load_ytmusic_button,
            self.save_button,
            self.preview_button,
            self.apply_button,
        ]
        self.setCentralWidget(root_widget)
        self.apply_styles()

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7fb;
                color: #151922;
                font-size: 14px;
            }
            QLabel#Title {
                font-size: 32px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#Subtitle, QLabel#Footer {
                color: #5b6472;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d9dee8;
                border-radius: 8px;
                margin-top: 12px;
                padding: 16px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLineEdit, QComboBox, QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #c9d1df;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton {
                background: #1f6feb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #195ec8;
            }
            QPushButton:disabled {
                background: #9aa8bd;
            }
            """
        )

    def load_existing_selection(self) -> None:
        playlist = self.current_playlist()
        if playlist.spotify_id:
            self.spotify_combo.addItem(f"Saved playlist ({playlist.spotify_id})", playlist.spotify_id)
        if playlist.youtube_music_id:
            self.ytmusic_combo.addItem(
                f"Saved playlist ({playlist.youtube_music_id})", playlist.youtube_music_id
            )

    def connect_spotify(self) -> None:
        self.run_task(self._connect_spotify)

    def connect_ytmusic(self) -> None:
        self.connect_ytmusic_device_flow()

    def load_spotify_playlists(self) -> None:
        self.run_task(self._load_spotify_playlists)

    def load_ytmusic_playlists(self) -> None:
        self.run_task(self._load_ytmusic_playlists)

    def sync(self, apply: bool) -> None:
        self.run_task(lambda: self._sync(apply=apply))

    def _connect_spotify(self) -> None:
        self.save_form()
        if not self.config.spotify.client_id:
            raise RuntimeError(
                "This developer build is missing a bundled Spotify app ID. "
                "Set PLAYLISTGIT_SPOTIFY_CLIENT_ID before launching the app."
            )
        adapter = SpotifyAdapter(
            self.config.spotify,
            resolve_path(self.root, ".playlistgit/spotify_token_cache"),
        )
        self.bridge.log.emit(f"Spotify connected as {adapter.display_name()}.")

    def connect_ytmusic_device_flow(self) -> None:
        self.save_form()
        if not self.app_creds.has_google:
            QMessageBox.warning(
                self,
                "Developer credentials missing",
                "This build is missing a bundled Google OAuth app ID. "
                "Set PLAYLISTGIT_GOOGLE_CLIENT_ID and PLAYLISTGIT_GOOGLE_CLIENT_SECRET "
                "before launching the app.",
            )
            return

        auth = YouTubeMusicOAuth(
            self.app_creds.google_client_id,
            self.app_creds.google_client_secret,
        )
        try:
            _verification_url, user_code, device_code = auth.begin()
        except Exception as exc:
            QMessageBox.warning(self, "YouTube Music", str(exc))
            return

        accepted = QMessageBox.information(
            self,
            "Connect YouTube Music",
            "A browser window opened for YouTube Music.\n\n"
            f"Enter this code if asked:\n\n{user_code}\n\n"
            "After you finish signing in, click OK here.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if accepted != QMessageBox.StandardButton.Ok:
            return

        self.run_task(lambda: self._finish_ytmusic_auth(auth, device_code))

    def _finish_ytmusic_auth(self, auth: YouTubeMusicOAuth, device_code: str) -> None:
        auth_path = resolve_path(self.root, self.config.youtube_music.auth_file)
        auth.finish(device_code, auth_path)
        YouTubeMusicAdapter(
            auth_path,
            oauth_client_id=self.app_creds.google_client_id,
            oauth_client_secret=self.app_creds.google_client_secret,
        )
        self.bridge.log.emit("YouTube Music connected.")

    def _load_spotify_playlists(self) -> None:
        self.save_form()
        adapter = SpotifyAdapter(
            self.config.spotify,
            resolve_path(self.root, ".playlistgit/spotify_token_cache"),
        )
        playlists = adapter.list_playlists()
        self.bridge.spotify_playlists.emit(playlists)
        self.bridge.log.emit(f"Loaded {len(playlists)} Spotify playlists.")

    def _load_ytmusic_playlists(self) -> None:
        self.save_form()
        adapter = YouTubeMusicAdapter(
            resolve_path(self.root, self.config.youtube_music.auth_file),
            oauth_client_id=self.app_creds.google_client_id,
            oauth_client_secret=self.app_creds.google_client_secret,
        )
        playlists = adapter.list_playlists()
        self.bridge.ytmusic_playlists.emit(playlists)
        self.bridge.log.emit(f"Loaded {len(playlists)} YouTube Music playlists.")

    def _sync(self, apply: bool) -> None:
        self.save_form()
        playlist = self.current_playlist()
        if not playlist.spotify_id or not playlist.youtube_music_id:
            self.bridge.log.emit("Choose both playlists before syncing.")
            return

        cfg = self.config
        self.bridge.log.emit("Fetching playlists...")
        spotify = SpotifyAdapter(cfg.spotify, resolve_path(self.root, ".playlistgit/spotify_token_cache"))
        ytmusic = YouTubeMusicAdapter(
            resolve_path(self.root, cfg.youtube_music.auth_file),
            oauth_client_id=self.app_creds.google_client_id,
            oauth_client_secret=self.app_creds.google_client_secret,
        )
        db = Store(resolve_path(self.root, cfg.sync.database))

        spotify_snapshot = PlaylistSnapshot(
            playlist_name=playlist.name,
            service=Service.SPOTIFY,
            service_playlist_id=playlist.spotify_id,
            tracks=spotify.get_playlist_tracks(playlist.spotify_id),
        )
        ytmusic_snapshot = PlaylistSnapshot(
            playlist_name=playlist.name,
            service=Service.YOUTUBE_MUSIC,
            service_playlist_id=playlist.youtube_music_id,
            tracks=ytmusic.get_playlist_tracks(playlist.youtube_music_id),
        )
        db.save_snapshot(spotify_snapshot)
        db.save_snapshot(ytmusic_snapshot)
        diff = diff_snapshots(spotify_snapshot, ytmusic_snapshot, cfg.sync.match_threshold)

        self.bridge.log.emit(
            f"Preview: {len(diff.spotify_only)} Spotify-only, "
            f"{len(diff.youtube_music_only)} YouTube-only additions."
        )
        if not apply:
            self.bridge.log.emit("No changes written. Use Sync Now to apply additions.")
            return

        to_yt = self.resolve_tracks(diff.spotify_only, ytmusic.search_track)
        to_spotify = self.resolve_tracks(diff.youtube_music_only, spotify.search_track)
        ytmusic.add_tracks(playlist.youtube_music_id, to_yt, dry_run=False)
        spotify.add_tracks(playlist.spotify_id, to_spotify, dry_run=False)
        self.bridge.log.emit(
            f"Done. Added {len(to_yt)} to YouTube Music and {len(to_spotify)} to Spotify."
        )

    def resolve_tracks(self, matches, search: Callable[[Track], Track | None]) -> list[Track]:
        resolved = []
        for match in matches:
            found = search(match.source)
            if found and score_tracks(match.source, found) >= self.config.sync.match_threshold:
                resolved.append(found)
            else:
                self.bridge.log.emit(f"Skipped low-confidence match: {match.source.title}")
        return resolved

    def save_form(self) -> None:
        cfg = self.config.model_copy(deep=True)
        cfg.spotify.client_id = self.app_creds.spotify_client_id or cfg.spotify.client_id
        cfg.spotify.redirect_uri = "http://127.0.0.1:8080/callback"
        cfg.youtube_music.auth_file = ".playlistgit/youtube_music_oauth.json"
        cfg.playlists = [
            PlaylistRef(
                name=self.sync_name.text().strip() or "Main",
                spotify_id=self.combo_value(self.spotify_combo),
                youtube_music_id=self.combo_value(self.ytmusic_combo),
            )
        ]
        save_config(self.root, cfg)
        self.config = cfg

    def current_playlist(self) -> PlaylistRef:
        return self.config.playlists[0] if self.config.playlists else PlaylistRef(name="Main")

    def set_spotify_playlists(self, playlists: list[RemotePlaylist]) -> None:
        self.set_combo_items(self.spotify_combo, playlists)

    def set_ytmusic_playlists(self, playlists: list[RemotePlaylist]) -> None:
        self.set_combo_items(self.ytmusic_combo, playlists)

    def set_combo_items(self, combo: QComboBox, playlists: list[RemotePlaylist]) -> None:
        current = self.combo_value(combo)
        combo.clear()
        for playlist in playlists:
            suffix = f" ({playlist.track_count} tracks)" if playlist.track_count is not None else ""
            combo.addItem(f"{playlist.name}{suffix}", playlist.service_playlist_id)
        if current:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)

    def combo_value(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return str(data) if data else ""

    def run_task(self, target: Callable[[], None]) -> None:
        self.bridge.busy.emit(True)

        def runner() -> None:
            try:
                target()
            except Exception as exc:
                self.bridge.log.emit(str(exc))
            finally:
                self.bridge.busy.emit(False)

        threading.Thread(target=runner, daemon=True).start()

    def set_busy(self, busy: bool) -> None:
        for button in self.buttons:
            button.setEnabled(not busy)

    def log(self, message: str) -> None:
        self.output.appendPlainText(message)


def main() -> None:
    app = QApplication(sys.argv)
    window = PlaylistGitWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
