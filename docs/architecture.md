# Architecture

This is a "single user, single machine, single JSON file" app. The
architecture goes out of its way to stay boring.

## Module map

```
src/snippetbox/
├── __init__.py            -- public surface
├── __main__.py            -- python -m snippetbox
├── errors.py              -- all exceptions

# core models
├── snippet.py             -- the Snippet dataclass
├── tag.py                 -- Tag + helpers
├── author.py              -- Author dataclass
├── collection.py          -- Collection dataclass
├── language.py            -- curated language table

# storage
├── storage.py             -- Book class + atomic JSON write
├── migrate.py             -- schema 0/1/2 -> 3
├── backup.py              -- snapshot + restore

# parsers / formatters
├── parser.py              -- string -> typed value helpers
├── validators.py          -- "is this OK?" boolean-with-message
├── markdown_render.py     -- snippet -> markdown
├── highlight.py           -- naive line classifier

# business logic
├── search.py              -- substring/token/fuzzy search
├── query.py               -- structured field query language
├── ranking.py             -- explainable ranking profiles
├── catalog.py             -- in-memory indexes and related snippets
├── tagger.py              -- regex-rule auto-tagger
├── usage.py               -- usage log + recency
├── dedup.py               -- duplicate detection
├── lint.py                -- soft style warnings
├── merge.py               -- simple two-book merge
├── sync.py                -- three-way merge planning
├── import_plan.py         -- import collision planning
├── batch.py               -- previewable metadata edits
├── transform.py           -- composable body transformations
├── selection.py           -- reusable named queries
├── retention.py           -- archive/delete retention plans
├── quality.py             -- explainable quality scores
├── policy.py              -- configurable library rules
├── health.py              -- whole-book diagnostics
└── maintenance.py         -- safe repair operations

# history and collaboration
├── revision.py            -- metadata-backed snippet revisions
├── diffing.py             -- line comparison and rendering
├── review.py              -- review queue state machine
├── timeline.py            -- activity timeline helpers
├── provenance.py          -- source records and checksums
├── template.py            -- parameterised snippets
└── dependencies.py        -- snippet reference graph

# portability and application services
├── snapshot.py            -- deterministic book snapshots
├── manifest.py            -- checksummed file manifests
├── sharing.py             -- redaction profiles
├── workspace.py           -- named book registry
├── stats.py               -- library distributions and trends
├── identifiers.py         -- ids, aliases, and safe slugs
├── timestamps.py          -- UTC and time-window helpers
└── service.py             -- high-level embedding API

# i/o codecs
├── io_json.py             -- native
├── io_markdown.py         -- # heading + ```fence```
├── io_html.py             -- single-page HTML
├── io_zip.py              -- folder-of-files zip
├── io_vscode.py           -- vscode user-snippets
├── io_textmate.py         -- textmate-style XML bundle
├── io_gist.py             -- github gist json
├── io_csv.py              -- notion / obsidian csv

# utilities
├── audit_log.py           -- optional newline-delimited json log
├── plugins.py             -- tiny plugin registry
├── config.py              -- ~/.snippetbox/config.toml
├── report.py              -- canned reports
├── recipes.py             -- multi-module workflows
└── server.py              -- stdlib HTTP browser
```

## Why one big JSON file

I picked JSON over SQLite for one selfish reason: I want
`grep '"language": "python"' book.json` to keep working. SQLite is
the better engineering choice; JSON is the better hobbyist choice.

Trade-offs:

- Pro: trivially diff-able. Trivially `git`-trackable. Trivially
  recoverable if the schema goes weird.
- Pro: zero dependencies.
- Con: you read the entire book to do *anything*. Doesn't matter
  while the book is < ~50MB. I'm at 1.2MB after two years.
- Con: no concurrent writers. Solved by "don't have concurrent
  writers". I run one CLI at a time.

## Atomic writes

`storage.atomic_write_json` does:

1. Serialise to a string.
2. Open a temp file in the same directory.
3. Write + flush + fsync.
4. `os.replace(tmp, target)`.

That's the canonical "torn write" defence on POSIX. On Windows it's
the same call (`os.replace` falls through to `MoveFileEx` which is
atomic on the same volume).

If the process dies between steps 1 and 4 the original file is
untouched. If it dies during step 4, you get either the old file
(replace not committed) or the new file (replace committed) — not a
half-written one.

## Schema migrations

`migrate.py` is a forward-only pipeline. The book carries a
`schema_version` integer. On read, we run `migrate(book)` which
applies registered functions until the version matches
`CURRENT_SCHEMA`. We never migrate backwards; if you've used this
on schema 5 you cannot then go to 4.

The migrations registered today:

| from | to | what                                               |
|------|----|----------------------------------------------------|
| 0    | 1  | wrap bare-list books in a dict; ensure required keys |
| 1    | 2  | add `collections`; assign per-snippet `slug`         |
| 2    | 3  | split manual `tags` from `auto_tags`                 |

## Search

`search.search(snippets, query, mode=...)` runs one of three modes:

- `substring`: dumb `q in haystack`.
- `token`: tokenise `q`, every token must match somewhere
  (title/body/tags). AND semantics.
- `fuzzy`: like `token`, but allow Levenshtein distance 1 per token.

Ranking weights title hits higher than body hits, body hits higher
than tag hits, with a small favourite multiplier. Unscored hits are
filtered out.

## Auto-tagger

`tagger.suggest_tags(snippet)` runs a curated regex table over the
snippet body+title. It's not magic, it's not a model. Each tag has
1-N regexes; if any match, the tag is suggested. The output goes
into `snippet.auto_tags`, leaving the user-curated `snippet.tags`
alone.

You can extend the table at runtime with `tagger.add_custom_rule`.

## HTTP server

`server.py` exposes a stdlib `http.server` with these routes:

- `GET /` — single-page HTML browse view.
- `GET /api/snippets` — JSON dump.
- `GET /api/snippet/<id>` — one snippet as JSON.
- `GET /snippet/<slug>` — one snippet as HTML.
- `GET /healthz` — `ok`.

Bound to `127.0.0.1` on purpose. The kitchen tablet is annoying about
CORS, hence the explicit content types.
