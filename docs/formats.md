# File formats

Reference for every codec snippetbox can read or write.

## Native JSON

The on-disk book.

```json
{
  "schema_version": 3,
  "metadata": { "created_at": 1700000000.0, "version": "2.0.0" },
  "snippets": [
    {
      "id": "abc123",
      "title": "Tail a file",
      "slug": "tail-a-file",
      "body": "...",
      "language": "python",
      "tags": ["io", "async"],
      "auto_tags": ["asyncio"],
      "created_at": 1700000000.0,
      "updated_at": 1700000000.0,
      "favourite": false,
      "archived": false,
      "used_count": 3,
      "source": "",
      "notes": "",
      "author": { "name": "...", "email": "..." },
      "extra": {}
    }
  ],
  "collections": [
    {
      "name": "favs",
      "description": "",
      "snippet_ids": ["abc123"],
      "created_at": 1700000000.0,
      "updated_at": 1700000000.0
    }
  ]
}
```

Notes:

- `id` is a 12-character SHA-256 prefix derived from `title + body +
  created_at`. Stable across saves.
- `slug` is a normalised slug; falls back to a 7-char body hash if
  the title slugs to empty.
- `body` is stored verbatim (with whatever line endings you gave it).
- `extra` is an opaque per-snippet bag for plugins.

## Markdown export

One snippet per `# heading`, optional metadata, fenced body.

````markdown
# Tail a file

- language: `python`
- tags: `io`, `async`

```python
import asyncio
async def tail(path):
    while True:
        await asyncio.sleep(0.1)
```
````

Recognised meta keys: `language`, `tags`, `auto-tags`, `source`,
`notes`. Unrecognised meta keys are silently dropped.

## VSCode user-snippets

JSON object keyed by display name.

```json
{
  "Tail a file": {
    "prefix": "tail",
    "body": ["import asyncio", "async def tail(path):"],
    "description": "tail-poll a file",
    "scope": "python"
  }
}
```

`scope` may be a comma-separated language list; we only honour the
first entry (because `Snippet.language` is a single string).

## TextMate-style XML

```xml
<snippets>
  <snippet>
    <name>Tail a file</name>
    <scope>source.python</scope>
    <content><![CDATA[import asyncio
async def tail(path): ...]]></content>
    <tabTrigger>tail-a-file</tabTrigger>
  </snippet>
</snippets>
```

`source.<lang>` is honoured for the language. `text.plain` maps to
`plain`. Anything else is kept as-is.

## GitHub Gist JSON

Whatever `gh gist view <id> --raw` or the `/gists/<id>` API gives you:

```json
{
  "description": "from a chat reply",
  "html_url": "https://gist.github.com/abc123",
  "owner": { "login": "ziad" },
  "files": {
    "tail.py": {
      "filename": "tail.py",
      "language": "Python",
      "content": "import asyncio..."
    }
  }
}
```

Each file in `files` becomes a separate snippet. `language` is
lower-cased. `description` becomes `notes`. `html_url` becomes
`source`.

## CSV (Notion / Obsidian friendly)

Comma-separated, header row, one snippet per row. Multi-line bodies
are kept verbatim (CSV quoting via `csv.writer`). Tags use `|` as the
internal separator inside a single cell.

```
id,title,language,tags,auto_tags,slug,source,notes,body
abc,Tail a file,python,io|async,asyncio,tail-a-file,,,...
```

`detect_dialect` will hint at `,`, `;`, or `\t` separators.

## ZIP "folder of files"

A `.zip` with this layout:

```
manifest.json
snippets/
  tail-a-file.py
  another-snippet.sql
```

`manifest.json` is identical to the native JSON manifest minus
`body`, plus a `filename` field per entry. This format is good for
emailing snippets to non-Python people.

## HTML export

A single self-contained `.html` file with inline CSS, a top-of-page
TOC, and one `<section>` per snippet. No JavaScript.
