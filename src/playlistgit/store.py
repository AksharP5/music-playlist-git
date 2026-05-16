from __future__ import annotations

import sqlite3
from pathlib import Path

from playlistgit.models import PlaylistSnapshot, Service, Track


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self) -> None:
        self.connection.executescript(
            """
            create table if not exists snapshots (
                id integer primary key autoincrement,
                playlist_name text not null,
                service text not null,
                service_playlist_id text not null,
                fetched_at text not null
            );

            create table if not exists snapshot_tracks (
                snapshot_id integer not null references snapshots(id) on delete cascade,
                position integer not null,
                stable_key text not null,
                track_json text not null
            );
            """
        )
        self.connection.commit()

    def save_snapshot(self, snapshot: PlaylistSnapshot) -> int:
        cursor = self.connection.execute(
            """
            insert into snapshots (playlist_name, service, service_playlist_id, fetched_at)
            values (?, ?, ?, ?)
            """,
            (
                snapshot.playlist_name,
                snapshot.service.value,
                snapshot.service_playlist_id,
                snapshot.fetched_at.isoformat(),
            ),
        )
        snapshot_id = int(cursor.lastrowid)
        self.connection.executemany(
            """
            insert into snapshot_tracks (snapshot_id, position, stable_key, track_json)
            values (?, ?, ?, ?)
            """,
            [
                (snapshot_id, index, track.stable_key, track.model_dump_json())
                for index, track in enumerate(snapshot.tracks)
            ],
        )
        self.connection.commit()
        return snapshot_id

    def latest_snapshot(self, playlist_name: str, service: Service) -> PlaylistSnapshot | None:
        row = self.connection.execute(
            """
            select * from snapshots
            where playlist_name = ? and service = ?
            order by id desc
            limit 1
            """,
            (playlist_name, service.value),
        ).fetchone()
        if not row:
            return None
        tracks = [
            Track.model_validate_json(track_row["track_json"])
            for track_row in self.connection.execute(
                """
                select track_json from snapshot_tracks
                where snapshot_id = ?
                order by position asc
                """,
                (row["id"],),
            )
        ]
        return PlaylistSnapshot(
            playlist_name=row["playlist_name"],
            service=Service(row["service"]),
            service_playlist_id=row["service_playlist_id"],
            fetched_at=row["fetched_at"],
            tracks=tracks,
        )

    def list_snapshots(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                select s.id, s.playlist_name, s.service, s.service_playlist_id, s.fetched_at,
                       count(st.stable_key) as track_count
                from snapshots s
                left join snapshot_tracks st on st.snapshot_id = s.id
                group by s.id
                order by s.id desc
                limit 50
                """
            )
        )

