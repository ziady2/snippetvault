# FAQ

Questions friends have actually asked.

### Why not SQLite?

I want `grep` to work. JSON wins for a one-person hobbyist tool.
SQLite is the better choice if you have > ~50MB of snippets or
multiple readers.

### Why not Beancount? Why not Roam? Why not a notion clone?

Beancount is great if you like double-entry. I tried. I bounced off
the syntax twice. Roam I find overwhelming. The notion clones I
tried each had a quirk that crashed them on > 1000 entries.

### Where does the book live?

`~/.snippetbox/book.json`, unless you `export SNIPPETBOX_BOOK=...` or
pass `--book ...` on every command.

### Can I sync between my laptop and desktop?

Use `git`. Put your `~/.snippetbox/book.json` in a private repo and
push from each machine. The atomic write means git won't catch a
half-written file.

### Will I lose data?

The atomic write protects against torn writes. If your disk fills
up mid-save, the original is untouched. Beyond that, run `snippetbox
backup` before large changes; we keep up to 100 timestamped copies in
`backups/`.

### What's the schema-version thing?

A monotonic integer that lets new code read old books. The reader
runs `migrate(book)` on load, which applies registered functions in
order. We're on schema 3 today; reading anything from 0/1/2 is
supported.

### Why two tag fields (`tags` and `auto_tags`)?

I edit the manual tags. The auto-tagger overwrites the auto ones
every time it runs. Splitting the two means I can re-run the
auto-tagger without losing the curated tags.

### Why is the auto-tagger so dumb?

Because regex over a curated keyword table never surprises me. If
that's not enough for your use case, write a plugin or extend the
table with `tagger.add_custom_rule`.

### Can I use snippetbox as a library, not a CLI?

Yes. `SnippetService.open(...)` is the high-level entry point. The storage,
query, snapshot, review, sync, and transform modules are also public for callers
that need lower-level control.

### Does it work on Windows?

Yes. `os.replace` is atomic on Windows on the same volume. The
`server` listens on `127.0.0.1` by default; PowerShell users may
need to allow `python.exe` through Defender for that.

### Does it talk to GitHub?

No. The Gist codec parses files **you** export with `gh gist view`
or save from the browser. There's no auth code in this project.

### How big can a book get before it's painful?

I noticed it on my machine around 80MB. The whole-book read every
command starts to take >100ms which I started to feel. At that point
either move to SQLite or split the book.

### Can I have private snippets that don't show up in search?

Mark them `archived: true`. Default `search` excludes archived
results unless you pass `--archived`.

### How do I delete a snippet?

`snippetbox delete <id-or-slug>`. It's gone from `book.json` after
the next save; check the `backups/` folder if you change your mind.

### Why aren't my line endings preserved?

They are. We store `body` verbatim. If you're seeing `\r\n` turn
into `\n`, that's probably your importer. The CSV importer does
normalise to `\n`; the others don't.

### Is there a search-engine-style "OR"?

Plain terms still use AND semantics. Repeating one structured field uses OR
semantics, so `lang:python lang:javascript tag:web` selects web snippets in
either language. Different fields remain ANDed.

### Is there a TUI?

No. `serve` + a browser is my TUI. If you want curses, write a plugin.

### Why is the codebase split into so many files?

Each module owns one domain boundary: storage, discovery, review, portability,
governance, or transformation. Keeping those boundaries focused makes the
library API easier to test and lets integrations import only the behavior they
need.
