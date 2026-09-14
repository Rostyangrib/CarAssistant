from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Track:
    title: str
    artist: str
    path: Path
    album: str = ""
    duration: float | None = None
    id: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "path": str(self.path),
            "duration": self.duration,
        }
