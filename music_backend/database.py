from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL UNIQUE,
    duration REAL,
    title_norm TEXT NOT NULL DEFAULT '',
    artist_norm TEXT NOT NULL DEFAULT '',
    album_norm TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album COLLATE NOCASE);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(tracks)")}
            for column in ("title_norm", "artist_norm", "album_norm"):
                if column not in columns:
                    connection.execute(f"ALTER TABLE tracks ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            rows = connection.execute("SELECT id, title, artist, album FROM tracks").fetchall()
            connection.executemany(
                "UPDATE tracks SET title_norm=?, artist_norm=?, album_norm=? WHERE id=?",
                ((row["title"].casefold(), row["artist"].casefold(), row["album"].casefold(), row["id"]) for row in rows),
            )
            connection.executescript(
                "CREATE INDEX IF NOT EXISTS idx_tracks_title_norm ON tracks(title_norm);"
                "CREATE INDEX IF NOT EXISTS idx_tracks_artist_norm ON tracks(artist_norm);"
                "CREATE INDEX IF NOT EXISTS idx_tracks_album_norm ON tracks(album_norm);"
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
