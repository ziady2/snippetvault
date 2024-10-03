"""Print a quick monthly-style overview of the book.

Run with: ``python examples/monthly_report.py``
"""

from __future__ import annotations

from snippetbox import report, storage


def main() -> None:
    book = storage.Book.load(storage.default_book_path())
    snips = list(book)

    overview = report.overview(snips)
    print("# Snippetbox monthly report\n")
    for k, v in overview.items():
        print(f"- {k}: {v}")
    print()

    print("## Languages")
    print(report.histogram_languages(snips))
    print()

    print("## Top tags")
    by_tag = report.by_tag(snips)
    for tag, count in by_tag.rows[:15]:
        print(f"- {tag}: {count}")
    print()

    print("## Stale (>180 days)")
    stale = report.stale(snips, days=180)
    if not stale.rows:
        print("(nothing stale)")
    else:
        for row in stale.rows[:10]:
            print(f"- {row[0]}: {row[1]} days")


if __name__ == "__main__":
    main()
