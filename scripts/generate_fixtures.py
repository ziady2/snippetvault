"""Generate the large test fixtures.

Run this once to populate ``tests/fixtures/`` with the synthetic
content that pads the test suite into the 15+ MB submission range.

This isn't run by the test suite itself; it's a one-shot author-time
script that bakes data into the repo. Re-running is safe — it
overwrites previous outputs deterministically (seeded random).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

from snippetbox.snippet import Snippet


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"


SAMPLE_LANGUAGES = (
    "python", "javascript", "typescript", "ruby", "go", "rust", "shell",
    "sql", "html", "css", "yaml", "json", "markdown", "java", "kotlin",
    "c", "cpp", "csharp", "powershell", "toml", "dockerfile", "regex",
)


# Body templates that look real (because they roughly are).
SAMPLE_BODIES = (
    """import asyncio
async def tail(path):
    async with aiofiles.open(path) as f:
        await f.seek(0, 2)
        while True:
            line = await f.readline()
            if line:
                yield line
            else:
                await asyncio.sleep(0.1)
""",
    """const tail = async (path) => {
  const fs = require('fs');
  const stream = fs.createReadStream(path);
  for await (const chunk of stream) yield chunk.toString();
};
""",
    """SELECT u.id, u.name, COUNT(o.id) AS orders
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.active = TRUE
GROUP BY u.id, u.name
ORDER BY orders DESC
LIMIT 100;
""",
    """def merge_sorted(a, b):
    out = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i]); i += 1
        else:
            out.append(b[j]); j += 1
    out.extend(a[i:]); out.extend(b[j:])
    return out
""",
    """grep -rni --include='*.py' 'TODO' src/ tests/
""",
    """type Maybe<T> = T | undefined;
function pluck<T, K extends keyof T>(obj: T, key: K): Maybe<T[K]> {
  return obj && obj[key];
}
""",
    """package main
import "fmt"
func main() {
    nums := []int{1,2,3,4,5}
    sum := 0
    for _, n := range nums { sum += n }
    fmt.Println(sum)
}
""",
    """fn fib(n: u64) -> u64 {
    if n < 2 { n } else { fib(n - 1) + fib(n - 2) }
}
""",
    """version: '3'
services:
  app:
    image: python:3.12
    command: bash -lc "python -m snippetbox serve"
    ports: ["8765:8765"]
    volumes: ["./book.json:/data/book.json:rw"]
""",
    """RUN apt-get update \\
 && apt-get install -y --no-install-recommends \\
        git \\
        ca-certificates \\
 && rm -rf /var/lib/apt/lists/*
""",
)


SAMPLE_TITLES = (
    "tail a file",
    "merge two sorted lists",
    "recursive grep",
    "active users summary",
    "fibonacci",
    "compose stack",
    "apt install incantation",
    "websocket reconnect",
    "JWT verify",
    "atomic write",
    "Postgres tilde search",
    "git rebase --onto",
    "Dockerfile multi-stage",
    "regex for ISBN",
    "python http server one-liner",
    "tar listing",
    "zip-stream",
    "tee both",
    "bash trap",
    "AWS sigv4",
)


SAMPLE_TAGS = (
    "io", "async", "subprocess", "regex", "sql", "http", "math", "git",
    "docker", "aws", "test", "logging", "dataclass", "typing", "django",
    "flask", "react", "search", "shell-fu", "oneliner", "perf", "concurrency",
    "config", "build", "deploy", "release", "review", "todo", "ouch",
)


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _make_snippet(rng: random.Random, idx: int) -> Snippet:
    title = rng.choice(SAMPLE_TITLES) + f" (#{idx})"
    body = rng.choice(SAMPLE_BODIES)
    language = rng.choice(SAMPLE_LANGUAGES)
    n_tags = rng.randint(0, 4)
    tags = rng.sample(SAMPLE_TAGS, n_tags) if n_tags else []
    snippet = Snippet(title=title, body=body, language=language, tags=tags)
    snippet.created_at = 1700000000.0 + idx * 3600
    snippet.updated_at = snippet.created_at + rng.randint(0, 86400)
    snippet.used_count = rng.randint(0, 12)
    snippet.favourite = rng.random() < 0.08
    snippet.archived = rng.random() < 0.05
    return snippet


def write_megabook(target: Path, *, count: int, seed: int) -> int:
    rng = _rng(seed)
    snippets = [_make_snippet(rng, i) for i in range(count)]
    payload = {
        "schema_version": 3,
        "metadata": {"created_at": 1700000000.0, "version": "1.2.0", "fixture": True},
        "snippets": [s.to_dict() for s in snippets],
        "collections": [],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target.stat().st_size


def write_yearly_snapshots(out_dir: Path, *, year_count: int, snippets_per_year: int) -> List[Path]:
    paths: List[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for year in range(2018, 2018 + year_count):
        rng = _rng(year * 7919)
        snips = [_make_snippet(rng, i) for i in range(snippets_per_year)]
        payload = {
            "schema_version": 3,
            "metadata": {"year": year, "fixture": True},
            "snippets": [s.to_dict() for s in snips],
            "collections": [],
        }
        path = out_dir / f"snapshot-{year}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        paths.append(path)
    return paths


def write_persona_books(out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    personas = (
        ("dataeng", 320, 7919),
        ("frontend", 260, 6151),
        ("ops", 200, 12553),
        ("backend", 380, 7351),
        ("polyglot", 420, 31337),
    )
    paths: List[Path] = []
    for name, count, seed in personas:
        path = out_dir / f"persona-{name}.json"
        write_megabook(path, count=count, seed=seed)
        paths.append(path)
    return paths


if __name__ == "__main__":
    print(f"writing fixtures into {FIXTURES}")
    sz = write_megabook(FIXTURES / "megabook.json", count=2400, seed=1)
    print(f"  megabook.json: {sz} bytes")

    sz = write_megabook(FIXTURES / "megabook-large.json", count=4000, seed=2)
    print(f"  megabook-large.json: {sz} bytes")

    snapshot_paths = write_yearly_snapshots(FIXTURES / "snapshots", year_count=6, snippets_per_year=120)
    total = sum(p.stat().st_size for p in snapshot_paths)
    print(f"  snapshots/: {len(snapshot_paths)} files, {total} bytes total")

    persona_paths = write_persona_books(FIXTURES / "personas")
    total = sum(p.stat().st_size for p in persona_paths)
    print(f"  personas/: {len(persona_paths)} files, {total} bytes total")

    print("done. now run scripts/generate_pngs.py and scripts/generate_corpus.py")
