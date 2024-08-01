# snippetbox 2.0

Snippetbox is an offline knowledge base for code snippets that should remain
searchable, reviewable, and portable over time. It stores the complete library
in readable JSON, exposes a command-line interface and localhost browser, and
has no runtime dependencies or hosted service.

The project is designed for one developer or a small team that wants a
grep-able source of truth without giving up revisions, structured queries,
quality checks, deterministic snapshots, or safe sharing.

## What it does

- Stores snippets as records in one JSON file (the *book*).
- Tags, languages, collections, full-text, fuzzy, and structured field search.
- Imports/exports: VSCode user-snippets, TextMate bundles, GitHub
  Gist JSON, plain markdown, the textmate-ish XML some editors still
  produce, and CSVs you might have exported from Notion or Obsidian.
- Renders pretty markdown with code fences and a table of contents.
- A tiny stdlib-only HTTP server you can leave running on
  `localhost:8765` to browse from a phone or another laptop on the
  same network.
- An audit log if you turn it on; off by default because I forgot it
  existed for the first six months.
- Revision history, review queues, saved selections, reusable templates, and
  previewable batch edits.
- Dependency graphs, three-way sync planning, import conflict plans, retention
  policies, and whole-book diagnostics.
- Deterministic snapshots and manifests, provenance tracking, quality scoring,
  and redaction profiles for safer exports.

## What it doesn't do

- Cloud sync. The `sync` module plans deterministic offline merges, but it does
  not contact a remote service.
- Editor integration. I tried writing a VSCode extension once. It
  was painful. The export format works fine instead.
- AI summarisation, AI tagging, AI anything. The auto-tagger uses a
  keyword table I curate by hand.
- Authentication. The HTTP server binds to localhost only on
  purpose.

## Install

```bash
pip install snippetbox
```

Or from source:

```bash
unzip snippetbox.zip
cd snippetbox
python -m pip install -e ".[dev]"
```

You'll get a `snippetbox` command on your PATH.

## Quick start

```bash
snippetbox init
snippetbox add --lang python --title "tail a file" --tags io,async <<'EOF'
import asyncio, aiofiles
async def tail(path):
    async with aiofiles.open(path) as f:
        await f.seek(0, 2)
        while True:
            line = await f.readline()
            if line:
                yield line
            else:
                await asyncio.sleep(0.1)
EOF
snippetbox list --tag io
snippetbox search "asyncio.sleep"
snippetbox query 'lang:python tag:async -archived:true'
snippetbox doctor
snippetbox quality
snippetbox show <id> --format markdown
```

The `init` command writes a fresh book at `~/.snippetbox/book.json`.
You can override that with `--book some/other.json` on every command,
or `export SNIPPETBOX_BOOK=...` once.

## Storage

Everything lives in a single JSON file. I picked JSON over SQLite
for one selfish reason: I want `grep '"language": "python"' book.json`
to keep working. SQLite is the better engineering choice; JSON is the
better hobbyist choice. The file uses an atomic-rename write so a
power cut won't shred it. Past that, back it up however you back up
anything.

## Schema versioning

The book has a `schema_version` field. Old books get migrated
forward on read. I've bumped the schema three times so far:

- `0 -> 1`: initial published shape.
- `1 -> 2`: added `collections`, gave each snippet a stable `slug`.
- `2 -> 3`: split `tags` from `auto_tags` so the auto-tagger can
  re-run without nuking my hand-tags. This was the migration I
  regretted most because I'd been editing tags in place for months.

Books from schemas 0, 1, and 2 are migrated forward automatically. A book with
a newer unknown schema is rejected rather than silently downgraded.

## Library API

Applications can use the same workflows without invoking the CLI:

```python
from pathlib import Path
from snippetbox import SnippetService

service = SnippetService.open(Path("book.json"), create=True, autosave=True)
matches = service.structured_query("lang:python tag:web")
report = service.health()
```

Low-level modules remain importable for callers that need custom storage,
query, review, snapshot, manifest, transformation, or sync workflows.

## Status

The 2.0 release is covered by a broad deterministic test suite and a Python
3.10–3.13 CI matrix. The application remains dependency-free at runtime; its
development tools are version-pinned for reproducible verification.

## Licence

MIT. See `LICENSE`.
