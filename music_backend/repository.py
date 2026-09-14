from __future__ import annotations

from pathlib import Path
import random
import re
import sqlite3

from .database import Database
from .models import Track


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_tokens(value: str) -> tuple[str, ...]:
    endings = ("иями", "ями", "ами", "ого", "ему", "ому", "ую", "юю", "ах", "ях", "ой", "ей", "ы", "и", "а", "я", "у", "ю", "е", "о")
    tokens: list[str] = []
    for token in re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE):
        for ending in endings:
            if len(token) > len(ending) + 2 and token.endswith(ending):
                token = token[: -len(ending)]
                break
        tokens.append(token)
    return tuple(tokens)


class MusicRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _row_to_track(row: sqlite3.Row) -> Track:
        return Track(
            id=row["id"], title=row["title"], artist=row["artist"],
            album=row["album"], path=Path(row["path"]), duration=row["duration"],
        )

    def upsert(self, track: Track) -> str:
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT title, artist, album, duration FROM tracks WHERE path = ?", (str(track.path),)
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO tracks(title, artist, album, path, duration, title_norm, artist_norm, album_norm) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        track.title, track.artist, track.album, str(track.path), track.duration,
                        track.title.casefold(), track.artist.casefold(), track.album.casefold(),
                    ),
                )
                return "added"
            values = (track.title, track.artist, track.album, track.duration)
            if tuple(existing) == values:
                return "unchanged"
            connection.execute(
                "UPDATE tracks SET title=?, artist=?, album=?, duration=?, title_norm=?, artist_norm=?, album_norm=? "
                "WHERE path=?",
                (*values, track.title.casefold(), track.artist.casefold(), track.album.casefold(), str(track.path)),
            )
            return "updated"

    def get_track(self, track_id: int) -> Track | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        return self._row_to_track(row) if row else None

    def find_track(self, title: str) -> Track | None:
        matches = self.find_tracks(title, limit=1)
        return matches[0] if matches else None

    def find_tracks(self, query: str, limit: int = 20) -> list[Track]:
        normalized = query.casefold()
        pattern = f"%{_escape_like(normalized)}%"
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tracks WHERE title_norm LIKE ? ESCAPE '\\' "
                "ORDER BY CASE WHEN title_norm = ? THEN 0 ELSE 1 END, title LIMIT ?",
                (pattern, normalized, limit),
            ).fetchall()
            if not rows:
                candidates = connection.execute("SELECT * FROM tracks ORDER BY title LIMIT 500").fetchall()
                wanted = _search_tokens(query)
                rows = [row for row in candidates if _search_tokens(row["title"]) == wanted][:limit]
        return [self._row_to_track(row) for row in rows]

    def find_artist(self, artist: str) -> str | None:
        normalized = artist.casefold()
        pattern = f"%{_escape_like(normalized)}%"
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT artist FROM tracks WHERE artist_norm LIKE ? ESCAPE '\\' "
                "ORDER BY CASE WHEN artist_norm = ? THEN 0 ELSE 1 END LIMIT 1",
                (pattern, normalized),
            ).fetchone()
        return str(row["artist"]) if row else None

    def find_by_artist(self, artist: str) -> list[Track]:
        resolved = self.find_artist(artist)
        if resolved is None:
            return []
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tracks WHERE artist_norm = ? ORDER BY album, title", (resolved.casefold(),)
            ).fetchall()
        return [self._row_to_track(row) for row in rows]

    def get_random_track(self) -> Track | None:
        with self.database.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
            if not count:
                return None
            row = connection.execute("SELECT * FROM tracks LIMIT 1 OFFSET ?", (random.randrange(count),)).fetchone()
        return self._row_to_track(row)

    def paths_under(self, root: Path) -> set[Path]:
        prefix = str(root.resolve()) + "%"
        with self.database.connect() as connection:
            rows = connection.execute("SELECT path FROM tracks WHERE path LIKE ?", (prefix,)).fetchall()
        return {Path(row["path"]) for row in rows}

    def remove_paths(self, paths: set[Path]) -> int:
        if not paths:
            return 0
        with self.database.connect() as connection:
            connection.executemany("DELETE FROM tracks WHERE path = ?", ((str(path),) for path in paths))
        return len(paths)
