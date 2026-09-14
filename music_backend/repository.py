from __future__ import annotations

from pathlib import Path
from difflib import SequenceMatcher
import logging
import random
import re
import sqlite3

from .database import Database
from .models import Track


logger = logging.getLogger(__name__)

_CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
)
_ARTIST_NOISE_WORDS = {
    "artist", "ispolnitel", "ispolnitelya", "vklyuchi", "vkluchi", "pesni", "pesnyu",
    "muzyku", "hochu", "poslushat", "postav", "postavte",
}


def _artist_match_key(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"\b(?:nine|найн|девять)\b", "9", normalized)
    transliterated = normalized.translate(_CYRILLIC_TO_LATIN)
    tokens = re.findall(r"[a-z0-9]+", transliterated)
    meaningful = [token for token in tokens if token not in _ARTIST_NOISE_WORDS]
    return "".join(meaningful).replace("9", "nine")


def _artist_match_keys(value: str) -> tuple[str, ...]:
    parts = re.split(r"[,;&]|\b(?:feat(?:uring)?|ft)\.?\b", value, flags=re.IGNORECASE)
    keys = {_artist_match_key(value)}
    keys.update(_artist_match_key(part) for part in parts)
    return tuple(key for key in keys if key)


def _track_match_key(value: str) -> str:
    transliterated = value.casefold().translate(_CYRILLIC_TO_LATIN)
    tokens = re.findall(r"[a-z0-9]+", transliterated)
    noise = {"pesnya", "pesnyu", "trek", "vklyuchi", "vkluchi", "postav"}
    return "".join(token for token in tokens if token not in noise)


def _track_match_keys(value: str) -> tuple[str, ...]:
    base = re.split(r"[([]|\b(?:feat(?:uring)?|ft|prod)\.?\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return tuple({_track_match_key(value), _track_match_key(base)} - {""})


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
                if not rows:
                    query_key = _track_match_key(query)
                    ranked = []
                    for candidate in candidates:
                        keys = _track_match_keys(str(candidate["title"]))
                        score = max(
                            (SequenceMatcher(None, query_key, key).ratio() for key in keys),
                            default=0.0,
                        )
                        ranked.append((score, candidate))
                    ranked.sort(key=lambda item: item[0], reverse=True)
                    if ranked and ranked[0][0] >= 0.72:
                        runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
                        if ranked[0][0] - runner_up >= 0.08:
                            rows = [ranked[0][1]]
                            logger.debug(
                                "Fuzzy track match: query=%r title=%r score=%.3f",
                                query,
                                rows[0]["title"],
                                ranked[0][0],
                            )
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
            if row is not None:
                return str(row["artist"])
            rows = connection.execute(
                "SELECT DISTINCT artist FROM tracks ORDER BY artist LIMIT 500"
            ).fetchall()
        query_key = _artist_match_key(artist)
        if len(query_key) < 3:
            return None
        ranked = []
        matched_keys: dict[str, str] = {}
        for candidate in rows:
            candidate_artist = str(candidate["artist"])
            keys = _artist_match_keys(candidate_artist)
            matched_key = max(
                keys, key=lambda key: SequenceMatcher(None, query_key, key).ratio()
            )
            score = SequenceMatcher(None, query_key, matched_key).ratio()
            ranked.append((score, candidate_artist))
            matched_keys[candidate_artist] = matched_key
        ranked.sort(reverse=True)
        if not ranked:
            return None
        best_score, best_artist = ranked[0]
        best_key = matched_keys[best_artist]
        prefix_match = len(query_key) >= 5 and (
            best_key.startswith(query_key) or query_key.startswith(best_key)
        )
        runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
        if (best_score >= 0.70 or prefix_match) and best_score - runner_up >= 0.08:
            logger.debug(
                "Fuzzy artist match: query=%r artist=%r score=%.3f", artist, best_artist, best_score
            )
            return best_artist
        return None

    def get_all_tracks(self) -> list[Track]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM tracks ORDER BY artist, album, title").fetchall()
        return [self._row_to_track(row) for row in rows]

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
