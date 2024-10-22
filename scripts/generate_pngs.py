"""Generate noise-filled PNGs as binary attachment fixtures.

Why: text fixtures compress too efficiently to hit the 15+ MB target
on their own. PNGs of random pixel data don't compress, which is
exactly what we need.

Each PNG is built by hand using stdlib zlib + struct. No Pillow.
"""

from __future__ import annotations

import random
import zlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "attachments"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(name: bytes, data: bytes) -> bytes:
    return (
        len(data).to_bytes(4, "big")
        + name
        + data
        + zlib.crc32(name + data).to_bytes(4, "big")
    )


def fake_png(width: int = 64, height: int = 64, *, seed: int = 0) -> bytes:
    rng = random.Random(seed)
    out = bytearray(PNG_SIGNATURE)
    out += _chunk(
        b"IHDR",
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00",  # bit depth 8, RGB, no filter, no interlace
    )
    rows = bytearray()
    for _ in range(height):
        rows.append(0)  # filter byte: none
        rows.extend(rng.randbytes(width * 3))
    out += _chunk(b"IDAT", zlib.compress(bytes(rows), 1))
    out += _chunk(b"IEND", b"")
    return bytes(out)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    # large set of small-ish PNGs across themed sub-folders
    sets = [
        ("paste-1", 200, 64),
        ("paste-2", 140, 80),
        ("paste-3", 100, 96),
    ]
    total_bytes = 0
    for name, count, side in sets:
        sub = FIXTURES / name
        sub.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            data = fake_png(width=side, height=side, seed=i + hash(name))
            (sub / f"img-{i:04d}.png").write_bytes(data)
            total_bytes += len(data)
        print(f"{name}/: {count} files at ~{side}x{side}")
    print(f"done. total bytes written: {total_bytes}")


if __name__ == "__main__":
    main()
