from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from .models import Track
from .repository import MusicRepository


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScanResult:
    found: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0


def _decode_text_frame(payload: bytes) -> str:
    if not payload:
        return ""
    encoding = payload[0]
    data = payload[1:]
    codecs = {0: "latin-1", 1: "utf-16", 2: "utf-16-be", 3: "utf-8"}
    return data.decode(codecs.get(encoding, "utf-8"), errors="replace").rstrip("\x00")


def _synchsafe(value: bytes) -> int:
    result = 0
    for byte in value:
        result = (result << 7) | (byte & 0x7F)
    return result


def _read_id3v2(path: Path) -> dict[str, str]:
    """Read the common text frames used by the scanner; malformed tags are ignored."""
    with path.open("rb") as stream:
        header = stream.read(10)
        if len(header) != 10 or header[:3] != b"ID3":
            return {}
        version = header[3]
        body = stream.read(_synchsafe(header[6:10]))
    fields: dict[str, str] = {}
    names = {"TIT2": "title", "TPE1": "artist", "TALB": "album"}
    position = 0
    while position + 10 <= len(body):
        frame_id = body[position : position + 4].decode("latin-1")
        size_bytes = body[position + 4 : position + 8]
        size = _synchsafe(size_bytes) if version == 4 else int.from_bytes(size_bytes, "big")
        position += 10
        if not frame_id.strip("\x00") or size <= 0 or position + size > len(body):
            break
        if frame_id in names:
            fields[names[frame_id]] = _decode_text_frame(body[position : position + size])
        position += size
    return fields


class MusicScanner:
    def __init__(self, repository: MusicRepository) -> None:
        self.repository = repository

    def _metadata(self, path: Path) -> Track:
        title, artist, album, duration = path.stem, path.parent.name, "", None
        try:
            from mutagen import File as MutagenFile  # type: ignore[import-not-found]

            audio = MutagenFile(path, easy=True)
            if audio is not None:
                title = (audio.get("title") or [title])[0]
                artist = (audio.get("artist") or [artist])[0]
                album = (audio.get("album") or [album])[0]
                duration = getattr(getattr(audio, "info", None), "length", None)
        except Exception:
            try:
                tags = _read_id3v2(path)
                title = tags.get("title", title)
                artist = tags.get("artist", artist)
                album = tags.get("album", album)
            except (OSError, UnicodeError, ValueError):
                logger.warning("Could not read metadata for %s", path, exc_info=True)
        return Track(title=title, artist=artist, album=album, path=path.resolve(), duration=duration)

    def scan(self, root: Path) -> ScanResult:
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        files = sorted(path.resolve() for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".mp3")
        added = updated = 0
        for path in files:
            status = self.repository.upsert(self._metadata(path))
            added += status == "added"
            updated += status == "updated"
        removed = self.repository.remove_paths(self.repository.paths_under(root) - set(files))
        logger.info("Music scan: found=%s added=%s updated=%s removed=%s", len(files), added, updated, removed)
        return ScanResult(found=len(files), added=added, updated=updated, removed=removed)
