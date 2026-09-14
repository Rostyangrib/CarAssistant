from __future__ import annotations

from pathlib import Path

from music_backend.database import Database
from music_backend.models import Track
from music_backend.repository import MusicRepository


def test_database_creates_schema(tmp_path: Path) -> None:
    database = Database(tmp_path / "nested" / "music.db")
    database.initialize()
    with database.connect() as connection:
        table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'").fetchone()
        indices = {row[1] for row in connection.execute("PRAGMA index_list(tracks)")}
    assert table is not None
    assert {"idx_tracks_title", "idx_tracks_artist", "idx_tracks_album"} <= indices


def test_add_get_and_update(repository: MusicRepository, tracks) -> None:
    assert repository.upsert(tracks[0]) == "added"
    assert repository.upsert(tracks[0]) == "unchanged"
    found = repository.find_track("группа")
    assert found and found.artist == "Кино"
    changed = type(tracks[0])("Группа крови", "Кино", tracks[0].path, "Новое", 275.0)
    assert repository.upsert(changed) == "updated"
    assert repository.get_track(found.id).album == "Новое"


def test_find_artist_and_random(repository: MusicRepository, tracks) -> None:
    for track in tracks:
        repository.upsert(track)
    assert repository.find_artist("кино") == "Кино"
    assert len(repository.find_by_artist("Кино")) == 2
    assert repository.get_random_track() in [repository.find_track(track.title) for track in tracks]


def test_fuzzy_artist_search_handles_common_stt_distortions(repository, tracks, tmp_path) -> None:
    for track in tracks:
        repository.upsert(track)
    repository.upsert(Track("Трек", "9mice, Kai Angel", tmp_path / "9mice.mp3"))
    assert repository.find_artist("Nine Wives") == "9mice, Kai Angel"
    assert repository.find_artist("9-майс") == "9mice, Kai Angel"
    assert repository.find_artist("исполнитель 9 М") == "9mice, Kai Angel"
    assert repository.find_artist("совершенно другое имя") is None


def test_get_all_tracks(repository: MusicRepository, tracks) -> None:
    for track in tracks:
        repository.upsert(track)
    assert len(repository.get_all_tracks()) == len(tracks)


def test_fuzzy_track_search_handles_transliteration_and_suffix(repository, tmp_path) -> None:
    repository.upsert(
        Track(
            "Balaclava (Prod. DJ Tape & Serge Laconic)",
            "Big Baby Tape",
            tmp_path / "balaclava.mp3",
        )
    )
    found = repository.find_track("Балаклава")
    assert found and found.title == "Balaclava (Prod. DJ Tape & Serge Laconic)"
