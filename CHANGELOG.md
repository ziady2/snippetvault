# Changelog

All notable changes to this project will be documented here. Format
is loosely [Keep a Changelog](https://keepachangelog.com/), version
numbers follow SemVer most of the time.

## [2.0.0] - 2026-08-20

### Added
- Structured field queries, explainable ranking profiles, catalog indexes, and
  saved selections.
- Revision history, line diffs, review queues, activity timelines, templates,
  and previewable batch transformations.
- Dependency graphs, three-way sync planning, import conflict plans, retention
  policies, provenance records, and named workspaces.
- Deterministic book snapshots, portable file manifests, redaction profiles,
  whole-book diagnostics, maintenance repairs, statistics, and quality scores.
- CLI commands: `query`, `doctor`, `quality`, `snapshot`, and dry-run-first
  `batch` edits.
- A high-level `SnippetService` API for applications embedding snippetbox.

### Changed
- Development dependencies are pinned and CI targets Python 3.10–3.13.
- The runtime container is dependency-minimal; a separate dependency-only
  environment Dockerfile is included for reproducible verification.
- Package metadata and documentation now describe the full offline knowledge
  base rather than the original small CLI.

### Fixed
- Deserialisation now preserves valid zero-valued timestamps.
- Three-way sync deletion actions now propagate in the correct direction.
- Slug repair preserves and normalises an existing slug before falling back to
  a title-derived value.

## [1.2.0] - 2026-05-15

### Added
- HTTP server (`snippetbox serve`) — stdlib only, localhost-bound.
- TextMate bundle import/export (`io_textmate`).
- `dedup` module: detect snippets with identical normalised body.
- `lint` module: warn about empty bodies, missing language, etc.
- New CLI commands: `serve`, `dedup`, `lint`, `merge`.

### Changed
- Schema bump `2 -> 3`: split `tags` (manual) from `auto_tags`.
- Search now returns relevance-ranked results by default. Old
  behaviour available via `--no-rank`.

### Fixed
- `parse_date` no longer returns `None` for trailing whitespace.
- `validate_slug` accepts unicode word chars (was ASCII only).

## [1.1.0] - 2026-01-22

### Added
- Markdown rendering with TOC.
- Auto-tagger using a curated keyword map.
- VSCode user-snippet import (`io_vscode`).

### Changed
- Storage: atomic write via `os.replace`. Was naive open+truncate.

## [1.0.0] - 2025-09-08

### Added
- Stable JSON schema (`schema_version: 2`).
- `collections` for grouping snippets.
- Per-snippet `slug` for stable URLs in the upcoming HTTP server.

### Changed
- Schema bump `1 -> 2`.

## [0.4.0] - 2025-04-30

### Added
- CSV import/export.
- Backup/restore commands.
- `report` module for usage breakdowns.

## [0.3.0] - 2025-01-12

### Added
- First Gist (JSON) import.
- Plugin discovery via entry points.

## [0.2.0] - 2024-10-09

### Added
- Search across title + body + tags.
- `audit_log` module (off by default).

## [0.1.0] - 2024-08-01

### Added
- Initial JSON storage layer.
- `Snippet`, `Tag`, `Author` dataclasses.
- Basic CLI: `init`, `add`, `list`, `show`.
- Schema `1`.
