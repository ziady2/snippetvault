# Recipes

Copy-pasteable workflows.

## Bootstrap

```bash
snippetbox init
```

Creates `~/.snippetbox/book.json`.

## Add a snippet from a file

```bash
snippetbox add --title "tail a file" --lang python --tags io,async \
    --from-file ./tail.py
```

## Add a snippet from clipboard / pipe

```bash
xclip -o | snippetbox add --title "stuff" --lang python --tags misc
```

(or on macOS: `pbpaste | snippetbox add ...`)

## Search

```bash
# substring
snippetbox search "asyncio.sleep" --mode substring

# token (default) — every word must hit somewhere
snippetbox search "tail file"

# fuzzy — typo-tolerant
snippetbox search "asyncii sleep" --mode fuzzy
```

## List by language or tag

```bash
snippetbox list --lang python
snippetbox list --tag git --limit 100
```

## Show in different formats

```bash
snippetbox show <id> --format text       # default
snippetbox show <id> --format markdown   # for README pasting
snippetbox show <id> --format html       # for the browser
snippetbox show <id> --format json       # for piping
```

## Backup before a big migration

```bash
snippetbox backup --label pre-merge
```

Saves `~/.snippetbox/backups/book-YYYYMMDD-HHMMSS.json-pre-merge`.

To restore: `snippetbox restore pre-merge`.

## Auto-tag every snippet

```bash
snippetbox auto-tag --max-tags 4
```

Re-runs the regex auto-tagger across the book. Manual tags are not
touched.

## Find duplicates

```bash
snippetbox dedup
```

Prints clusters of snippets with identical normalised bodies.

## Lint

```bash
snippetbox lint
```

Soft style warnings (empty bodies, `MAYBE_LANG`, etc).

## Reports

```bash
snippetbox report --what overview     # summary line per stat
snippetbox report --what language     # count per language
snippetbox report --what tag          # count per tag
snippetbox report --what stale        # not-touched-in-180-days
snippetbox report --what coverage     # tagged-vs-untagged per language
```

## Browse from a phone on the same network

```bash
snippetbox serve
```

Then point a browser at `http://<your-laptop>:8765`. Server is
`127.0.0.1`-bound by default, so you'll need to tunnel or run with
`--host 0.0.0.0` on a trusted network.

## Import from another tool

```bash
# from a markdown export
snippetbox import notes.md --format markdown

# from VSCode
snippetbox import ~/Library/Application\ Support/Code/User/snippets/python.json --format vscode

# from a CSV (e.g. Obsidian export)
snippetbox import notes.csv --format csv

# from a saved GitHub gist JSON
gh gist view <id> --json files,owner,description,html_url > /tmp/gist.json
snippetbox import /tmp/gist.json --format gist
```

## Export

```bash
snippetbox export book.md   --format markdown
snippetbox export book.html --format html
snippetbox export book.zip  --format zip
snippetbox export vscode.json --format vscode
```

## Bulk one-off: add a tag to every result of a search

There's no CLI shortcut for this yet, but you can do it from Python:

```python
from snippetbox import recipes, storage
book = storage.Book.load(storage.default_book_path())
recipes.search_and_mark(book, "asyncio", add_tags=["read"])
book.save()
```
