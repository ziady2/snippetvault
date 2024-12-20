"""Whole-book diagnostics that combine structural and content checks."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from .catalog import Catalog
from .dependencies import DependencyGraph
from .policy import PolicyIssue, SnippetPolicy, evaluate_many
from .revision import RevisionStore


LEVELS = {"ok": 0, "info": 1, "warning": 2, "error": 3}


@dataclass(frozen=True)
class HealthFinding:
    code: str
    message: str
    level: str = "warning"
    entity: str = ""
    component: str = "book"

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"unknown health level: {self.level}")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "level": self.level,
            "entity": self.entity,
            "component": self.component,
        }


@dataclass
class HealthReport:
    findings: List[HealthFinding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def level(self) -> str:
        if not self.findings:
            return "ok"
        return max(self.findings, key=lambda finding: LEVELS[finding.level]).level

    @property
    def healthy(self) -> bool:
        return not any(finding.level == "error" for finding in self.findings)

    def counts(self) -> dict:
        counts = {level: 0 for level in LEVELS if level != "ok"}
        for finding in self.findings:
            counts[finding.level] = counts.get(finding.level, 0) + 1
        return counts

    def by_component(self, component: str) -> List[HealthFinding]:
        return [finding for finding in self.findings if finding.component == component]

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "healthy": self.healthy,
            "counts": self.counts(),
            "metrics": dict(self.metrics),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def render_text(self) -> str:
        rows = [f"health: {self.level}"]
        for key, value in sorted(self.metrics.items()):
            rows.append(f"{key}: {value}")
        if self.findings:
            rows.append("")
            for finding in sorted(
                self.findings,
                key=lambda item: (-LEVELS[item.level], item.component, item.code, item.entity),
            ):
                entity = f" [{finding.entity}]" if finding.entity else ""
                rows.append(
                    f"{finding.level.upper():7} {finding.component}:{finding.code}{entity}: {finding.message}"
                )
        return "\n".join(rows)


def _policy_findings(issues: Iterable[PolicyIssue]) -> List[HealthFinding]:
    return [
        HealthFinding(
            code=issue.code,
            message=issue.message,
            level=issue.severity,
            entity=issue.snippet_id,
            component="policy",
        )
        for issue in issues
    ]


def inspect_book(book, *, policy: Optional[SnippetPolicy] = None, now: float = 0) -> HealthReport:
    snippets = list(book)
    collections = book.collections()
    catalog = Catalog(snippets, collections)
    graph = DependencyGraph.from_snippets(snippets)
    findings: list[HealthFinding] = []

    for issue in catalog.issues():
        findings.append(
            HealthFinding(
                code=issue.code,
                message=issue.message,
                level="error" if issue.code.startswith("duplicate") else "warning",
                entity=issue.entity,
                component="catalog",
            )
        )
    for issue in graph.issues():
        findings.append(
            HealthFinding(
                code=issue.code,
                message=issue.message,
                level="error" if issue.code == "dependency_cycle" else "warning",
                entity=issue.snippet_id,
                component="dependencies",
            )
        )
    findings.extend(_policy_findings(evaluate_many(snippets, policy, now=now)))

    revision_store = RevisionStore(book.data.setdefault("metadata", {}))
    for error in revision_store.validate():
        findings.append(
            HealthFinding(
                code="invalid_revision_history",
                message=error,
                level="warning",
                component="revisions",
            )
        )

    schema_version = book.data.get("schema_version")
    if not isinstance(schema_version, int):
        findings.append(
            HealthFinding(
                code="invalid_schema_version",
                message="schema_version must be an integer",
                level="error",
                component="storage",
            )
        )
    metadata = book.data.get("metadata")
    if not isinstance(metadata, dict):
        findings.append(
            HealthFinding(
                code="invalid_metadata",
                message="book metadata must be an object",
                level="error",
                component="storage",
            )
        )

    tag_counts = Counter(tag for snippet in snippets for tag in snippet.all_tags())
    metrics = {
        **catalog.summary(),
        "dependency_edges": sum(len(edges) for edges in graph.edges.values()),
        "revision_count": revision_store.count(),
        "book_bytes": Path(book.path).stat().st_size if Path(book.path).exists() else 0,
        "tag_assignments": sum(tag_counts.values()),
    }
    findings.sort(key=lambda item: (-LEVELS[item.level], item.component, item.code, item.entity))
    return HealthReport(findings=findings, metrics=metrics)


def inspect_path(path: Path, *, policy: Optional[SnippetPolicy] = None, now: float = 0) -> HealthReport:
    from .storage import Book

    path = Path(path)
    if not path.exists():
        return HealthReport(
            findings=[
                HealthFinding(
                    "book_missing",
                    f"book does not exist: {path}",
                    level="error",
                    component="storage",
                )
            ]
        )
    try:
        return inspect_book(Book.load(path), policy=policy, now=now)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return HealthReport(
            findings=[
                HealthFinding(
                    "book_unreadable",
                    str(exc),
                    level="error",
                    component="storage",
                )
            ]
        )


def merge_reports(*reports: HealthReport) -> HealthReport:
    findings = [finding for report in reports for finding in report.findings]
    metrics: dict = {}
    for index, report in enumerate(reports, start=1):
        for key, value in report.metrics.items():
            metrics[f"report_{index}.{key}"] = value
    return HealthReport(findings=findings, metrics=metrics)


def exit_code(report: HealthReport, *, warnings_as_errors: bool = False) -> int:
    if any(finding.level == "error" for finding in report.findings):
        return 2
    if warnings_as_errors and any(finding.level == "warning" for finding in report.findings):
        return 1
    return 0
