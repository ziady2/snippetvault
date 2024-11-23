"""argparse-based CLI.

The top-level ``main`` function is what the ``snippetbox`` script
calls into. Subcommands all take a parsed ``args`` namespace and
return an exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import (
    backup,
    batch,
    dedup,
    health,
    io_csv,
    io_gist,
    io_html,
    io_json,
    io_markdown,
    io_textmate,
    io_vscode,
    io_zip,
    lint,
    markdown_render,
    quality,
    query as structured_query,
    recipes,
    report,
    search,
    server,
    snapshot,
    storage,
    tagger,
)
from .errors import SnippetboxError
from .snippet import Snippet
from .tag import parse as parse_tags


def _open_book(args) -> storage.Book:
    book_path = Path(args.book) if getattr(args, "book", None) else storage.default_book_path()
    if not book_path.exists():
        # auto-init the first time
        return storage.Book.init(book_path)
    return storage.Book.load(book_path)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="snippetbox",
        description="An offline knowledge base for organizing and reviewing code snippets.",
    )
    p.add_argument("--book", help="path to the JSON book", default=None)
    p.add_argument("--version", action="store_true", help="print version and exit")
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("init", help="create an empty book")
    sp.add_argument("--force", action="store_true", help="overwrite existing book")

    sp = sub.add_parser("add", help="add a snippet")
    sp.add_argument("--title", default="", help="snippet title")
    sp.add_argument("--lang", default="plain", help="language (e.g. python, sql)")
    sp.add_argument("--tags", default="", help="comma-separated tags")
    sp.add_argument("--from-file", default="", help="read body from file (else stdin)")
    sp.add_argument("--auto-tag", action="store_true", help="run the auto-tagger after add")

    sp = sub.add_parser("list", help="list snippets")
    sp.add_argument("--lang", default="", help="filter by language")
    sp.add_argument("--tag", default="", help="filter by tag")
    sp.add_argument("--limit", type=int, default=50, help="max rows")
    sp.add_argument("--archived", action="store_true", help="include archived")

    sp = sub.add_parser("show", help="show one snippet")
    sp.add_argument("ident", help="id or slug")
    sp.add_argument("--format", choices=("text", "markdown", "html", "json"), default="text")

    sp = sub.add_parser("search", help="search snippets")
    sp.add_argument("query", nargs="?", default="")
    sp.add_argument("--mode", choices=("substring", "token", "fuzzy"), default="token")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--no-rank", action="store_true")
    sp.add_argument("--lang", default="", help="filter by language(s), comma-separated")
    sp.add_argument("--tag", default="", help="filter by tag(s), comma-separated")

    sp = sub.add_parser("query", help="run a structured field query")
    sp.add_argument("query", nargs="?", default="", help="query such as 'lang:python tag:web'")
    sp.add_argument("--limit", type=int, default=50, help="maximum rows")

    sp = sub.add_parser("doctor", help="run whole-book diagnostics")
    sp.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    sp.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="return a non-zero status when warnings are present",
    )

    sp = sub.add_parser("quality", help="score snippet quality")
    sp.add_argument("--limit", type=int, default=20, help="maximum low-scoring snippets to show")
    sp.add_argument("--threshold", type=float, default=80.0, help="show scores below this value")
    sp.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    sp = sub.add_parser("snapshot", help="create a deterministic book snapshot")
    sp.add_argument("--label", default="", help="optional snapshot label")
    sp.add_argument("--store", action="store_true", help="store the snapshot in book metadata")
    sp.add_argument("--json", action="store_true", help="emit the complete snapshot JSON")

    sp = sub.add_parser("batch", help="plan or apply batch edits")
    sp.add_argument(
        "--operation",
        "-o",
        action="append",
        default=[],
        help="operation such as add-tag=web, set-language=python, or archive",
    )
    sp.add_argument("--query", default="", help="structured query selecting snippets")
    sp.add_argument("--apply", action="store_true", help="write planned changes to the book")

    sp = sub.add_parser("delete", help="delete a snippet")
    sp.add_argument("ident", help="id or slug")

    sp = sub.add_parser("import", help="import snippets from a file")
    sp.add_argument("source", help="path to source file")
    sp.add_argument("--format", choices=("json", "markdown", "vscode", "textmate", "gist", "csv", "zip"), required=True)

    sp = sub.add_parser("export", help="export snippets to a file")
    sp.add_argument("target", help="path to target file")
    sp.add_argument("--format", choices=("json", "markdown", "vscode", "textmate", "gist", "csv", "zip", "html"), required=True)

    sp = sub.add_parser("report", help="report on the book")
    sp.add_argument("--what", choices=("language", "tag", "lines", "usage", "stale", "coverage", "overview"), default="overview")
    sp.add_argument("--limit", type=int, default=20)

    sub.add_parser("dedup", help="find duplicate snippets")

    sub.add_parser("lint", help="lint the book")

    sp = sub.add_parser("backup", help="backup the book")
    sp.add_argument("--label", default="", help="label suffix to attach")

    sp = sub.add_parser("restore", help="restore a backup")
    sp.add_argument("source", help="backup file or label")

    sp = sub.add_parser("auto-tag", help="run the auto-tagger across the book")
    sp.add_argument("--max-tags", type=int, default=6)

    sp = sub.add_parser("serve", help="run the web UI")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)

    sub.add_parser("info", help="print summary stats")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if getattr(args, "version", False):
        from . import __version__

        print(__version__)
        return 0
    cmd = args.command or ""
    handler = _DISPATCH.get(cmd)
    if handler is None:
        parser.print_help()
        return 1
    try:
        return handler(args)
    except SnippetboxError as exc:
        print(f"snippetbox: {exc}", file=sys.stderr)
        return 2


# -----------------------------------------------------------------
# subcommand handlers
# -----------------------------------------------------------------


def _cmd_init(args) -> int:
    book_path = Path(args.book) if args.book else storage.default_book_path()
    storage.Book.init(book_path, overwrite=args.force)
    print(f"book ready at {book_path}")
    return 0


def _cmd_add(args) -> int:
    book = _open_book(args)
    if args.from_file:
        body = Path(args.from_file).read_text(encoding="utf-8")
    else:
        body = sys.stdin.read() if not sys.stdin.isatty() else ""
    snippet = Snippet(
        title=args.title,
        body=body,
        language=args.lang or "plain",
        tags=parse_tags(args.tags),
    )
    if args.auto_tag:
        tagger.apply_to(snippet)
    book.add(snippet)
    book.save()
    print(snippet.id, snippet.slug or "(no slug)")
    return 0


def _cmd_list(args) -> int:
    book = _open_book(args)
    snippets: list = list(book)
    if args.lang:
        snippets = search.filter_by_language(snippets, args.lang)
    if args.tag:
        snippets = search.filter_by_tag(snippets, args.tag)
    if not args.archived:
        snippets = [s for s in snippets if not s.archived]
    snippets = sorted(snippets, key=lambda s: -s.updated_at)[: args.limit]
    for s in snippets:
        print(f"{s.id}  {s.language:<10}  {s.title or s.slug or '(untitled)'}")
    return 0


def _resolve(book: storage.Book, ident: str) -> Optional[Snippet]:
    s = book.get(ident)
    if s is not None:
        return s
    return book.get_by_slug(ident)


def _cmd_show(args) -> int:
    book = _open_book(args)
    snippet = _resolve(book, args.ident)
    if snippet is None:
        print(f"not found: {args.ident}", file=sys.stderr)
        return 1
    if args.format == "text":
        print(snippet.title or "(untitled)")
        print("-" * 40)
        print(snippet.body or "")
    elif args.format == "json":
        print(json.dumps(snippet.to_dict(), ensure_ascii=False, indent=2))
    elif args.format == "html":
        print(io_html.render([snippet], title=snippet.title or "snippet"))
    else:
        print(markdown_render.render_one(snippet))
    return 0


def _cmd_search(args) -> int:
    book = _open_book(args)
    languages = [t for t in (args.lang or "").split(",") if t]
    tags = [t for t in (args.tag or "").split(",") if t]
    hits = search.search(
        list(book),
        args.query,
        mode=args.mode,
        rank=not args.no_rank,
        languages=languages,
        tags=tags,
        limit=args.limit,
    )
    if not hits:
        print("(no matches)")
        return 0
    for hit in hits:
        s = hit.snippet
        print(f"{s.id}  {s.language:<10}  {s.title or s.slug or '(untitled)'}  ({hit.score:.2f})")
    return 0


def _cmd_query(args) -> int:
    book = _open_book(args)
    try:
        snippets = structured_query.filter_snippets(list(book), args.query)
    except ValueError as exc:
        print(f"invalid query: {exc}", file=sys.stderr)
        return 1
    snippets.sort(key=lambda snippet: (-snippet.updated_at, snippet.title.lower(), snippet.id))
    for snippet in snippets[: max(0, args.limit)]:
        tags = ",".join(snippet.all_tags()) or "-"
        print(
            f"{snippet.id}  {snippet.language:<10}  "
            f"{snippet.title or snippet.slug or '(untitled)'}  [{tags}]"
        )
    return 0


def _cmd_doctor(args) -> int:
    book = _open_book(args)
    result = health.inspect_book(book)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render_text())
    return health.exit_code(result, warnings_as_errors=args.warnings_as_errors)


def _cmd_quality(args) -> int:
    book = _open_book(args)
    result = quality.score_library(list(book))
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(f"average: {result.average:.1f}/100")
    print(f"minimum: {result.minimum:.1f}/100")
    counts = result.grade_counts()
    print("grades: " + " ".join(f"{grade}={counts[grade]}" for grade in "ABCDF"))
    below = result.below(args.threshold)[: max(0, args.limit)]
    if below:
        print("")
        print(f"below {args.threshold:.1f}:")
        for item in below:
            print(f"{item.snippet_id}  {item.score:5.1f}  {item.grade}")
    return 0


def _cmd_snapshot(args) -> int:
    book = _open_book(args)
    result = snapshot.create(book, label=args.label)
    if args.store:
        snapshot.store(book, result)
        book.save()
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"snapshot: {result.id}")
        print(f"snippets: {len(result.snippets)}")
        print(f"collections: {len(result.collections)}")
        print(f"schema_version: {result.schema_version}")
        print(f"stored: {'yes' if args.store else 'no'}")
    return 0


def _cmd_batch(args) -> int:
    if not args.operation:
        print("at least one --operation is required", file=sys.stderr)
        return 1
    try:
        operations = batch.parse_operations(args.operation)
        predicate = structured_query.compile_predicate(args.query) if args.query else None
        result = batch.plan(list(_open_book(args)), operations, predicate=predicate)
    except ValueError as exc:
        print(f"invalid batch request: {exc}", file=sys.stderr)
        return 1
    print(batch.render_plan(result))
    if not args.apply:
        print("dry run; pass --apply to write changes")
        return 0
    book = _open_book(args)
    changed = batch.apply_to_book(book, result, save=True)
    print(f"applied changes to {changed} snippets")
    return 0


def _cmd_delete(args) -> int:
    book = _open_book(args)
    snippet = _resolve(book, args.ident)
    if snippet is None:
        print(f"not found: {args.ident}", file=sys.stderr)
        return 1
    book.delete(snippet.id)
    book.save()
    print(f"deleted {snippet.id}")
    return 0


def _cmd_import(args) -> int:
    book = _open_book(args)
    raw = Path(args.source)
    fmt = args.format
    if fmt == "json":
        snippets = io_json.import_from_file(raw)
    elif fmt == "markdown":
        snippets = io_markdown.import_from_file(raw)
    elif fmt == "vscode":
        snippets = io_vscode.import_from_file(raw)
    elif fmt == "textmate":
        snippets = io_textmate.import_from_file(raw)
    elif fmt == "gist":
        snippets = io_gist.import_from_file(raw)
    elif fmt == "csv":
        snippets = io_csv.import_from_file(raw)
    elif fmt == "zip":
        snippets = io_zip.import_from_file(raw)
    else:
        raise SnippetboxError(f"bad import format: {fmt}")
    n = storage.merge_into(book, snippets)
    book.save()
    print(f"imported {n} new snippets ({len(snippets)} parsed)")
    return 0


def _cmd_export(args) -> int:
    book = _open_book(args)
    target = Path(args.target)
    snippets = list(book)
    fmt = args.format
    if fmt == "json":
        io_json.export_to_file(snippets, target)
    elif fmt == "markdown":
        io_markdown.export_to_file(snippets, target)
    elif fmt == "vscode":
        io_vscode.export_to_file(snippets, target)
    elif fmt == "textmate":
        io_textmate.export_to_file(snippets, target)
    elif fmt == "gist":
        io_gist.export_to_file(snippets, target)
    elif fmt == "csv":
        io_csv.export_to_file(snippets, target)
    elif fmt == "zip":
        io_zip.export_to_file(snippets, target)
    elif fmt == "html":
        io_html.export_to_file(snippets, target)
    else:
        raise SnippetboxError(f"bad export format: {fmt}")
    print(f"wrote {target}")
    return 0


def _cmd_report(args) -> int:
    book = _open_book(args)
    snippets = list(book)
    rep_fns = {
        "language": report.by_language,
        "tag": report.by_tag,
        "lines": report.line_counts,
        "stale": report.stale,
        "coverage": report.coverage,
    }
    if args.what == "overview":
        ov = report.overview(snippets)
        for k, v in ov.items():
            print(f"{k}: {v}")
        return 0
    if args.what == "usage":
        rep = report.usage_top(snippets, n=args.limit)
    else:
        fn = rep_fns.get(args.what)
        if fn is None:
            print(f"unknown report: {args.what}", file=sys.stderr)
            return 1
        rep = fn(snippets)
    print(rep.to_text())
    return 0


def _cmd_dedup(args) -> int:
    book = _open_book(args)
    clusters = dedup.find_duplicates(list(book))
    print(dedup.report(clusters) or "(no duplicates)")
    return 0


def _cmd_lint(args) -> int:
    book = _open_book(args)
    issues = lint.lint_book(book.data)
    if not issues:
        print("clean")
        return 0
    print(lint.render_issues(issues))
    return 1 if lint.has_errors(issues) else 0


def _cmd_backup(args) -> int:
    book_path = Path(args.book) if args.book else storage.default_book_path()
    target = backup.make_backup(book_path, label=args.label)
    print(f"backed up to {target}")
    return 0


def _cmd_restore(args) -> int:
    book_path = Path(args.book) if args.book else storage.default_book_path()
    src = Path(args.source)
    if not src.exists():
        labelled = backup.find_by_label(book_path, args.source)
        if labelled is None:
            print(f"no such backup: {args.source}", file=sys.stderr)
            return 1
        src = labelled
    backup.restore_backup(book_path, src)
    print(f"restored from {src}")
    return 0


def _cmd_auto_tag(args) -> int:
    book = _open_book(args)
    n = recipes.auto_tag_all(book, max_tags=args.max_tags)
    book.save()
    print(f"updated auto_tags on {n} snippets")
    return 0


def _cmd_serve(args) -> int:  # pragma: no cover - manually tested
    book_path = Path(args.book) if args.book else storage.default_book_path()
    print(f"serving {book_path} on http://{args.host}:{args.port}")
    server.serve(book_path, host=args.host, port=args.port)
    return 0


def _cmd_info(args) -> int:
    book = _open_book(args)
    stats = book.stats()
    for k, v in stats.items():
        print(f"{k}: {v}")
    return 0


_DISPATCH = {
    "init": _cmd_init,
    "add": _cmd_add,
    "list": _cmd_list,
    "show": _cmd_show,
    "search": _cmd_search,
    "query": _cmd_query,
    "doctor": _cmd_doctor,
    "quality": _cmd_quality,
    "snapshot": _cmd_snapshot,
    "batch": _cmd_batch,
    "delete": _cmd_delete,
    "import": _cmd_import,
    "export": _cmd_export,
    "report": _cmd_report,
    "dedup": _cmd_dedup,
    "lint": _cmd_lint,
    "backup": _cmd_backup,
    "restore": _cmd_restore,
    "auto-tag": _cmd_auto_tag,
    "serve": _cmd_serve,
    "info": _cmd_info,
}
