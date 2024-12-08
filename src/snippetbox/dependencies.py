"""Dependency graph for snippets that reference reusable snippets."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set

from .snippet import Snippet


_DIRECTIVE_RE = re.compile(r"(?:@snippet\((?P<call>[^)\s]+)\)|\bsnippet:(?P<plain>[A-Za-z0-9._-]+))")


def extract_references(text: str) -> list[str]:
    """Extract ordered, unique snippet references from text."""
    result: list[str] = []
    seen: set[str] = set()
    for match in _DIRECTIVE_RE.finditer(text or ""):
        value = match.group("call") or match.group("plain")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


@dataclass(frozen=True)
class DependencyIssue:
    code: str
    snippet_id: str
    dependency_id: str = ""
    message: str = ""


@dataclass
class DependencyGraph:
    """Directed graph where an edge A -> B means A depends on B."""

    edges: Dict[str, Set[str]] = field(default_factory=dict)
    titles: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_snippets(cls, snippets: Iterable[Snippet]) -> "DependencyGraph":
        snippets = list(snippets)
        by_alias: dict[str, str] = {}
        titles: dict[str, str] = {}
        for snippet in snippets:
            titles[snippet.id] = snippet.title or snippet.slug or snippet.id
            by_alias[snippet.id] = snippet.id
            if snippet.slug:
                by_alias[snippet.slug] = snippet.id
        edges: dict[str, set[str]] = {}
        for snippet in snippets:
            raw_refs = extract_references("\n".join((snippet.body, snippet.notes)))
            edges[snippet.id] = {by_alias.get(reference, reference) for reference in raw_refs}
        return cls(edges=edges, titles=titles)

    def nodes(self) -> set[str]:
        result = set(self.edges)
        for dependencies in self.edges.values():
            result.update(dependencies)
        return result

    def dependencies_of(self, snippet_id: str, *, transitive: bool = False) -> set[str]:
        direct = set(self.edges.get(snippet_id, set()))
        if not transitive:
            return direct
        result: set[str] = set()
        queue = deque(direct)
        while queue:
            dependency = queue.popleft()
            if dependency in result:
                continue
            result.add(dependency)
            queue.extend(self.edges.get(dependency, set()) - result)
        return result

    def dependents_of(self, snippet_id: str, *, transitive: bool = False) -> set[str]:
        reverse = self.reverse_edges()
        direct = set(reverse.get(snippet_id, set()))
        if not transitive:
            return direct
        result: set[str] = set()
        queue = deque(direct)
        while queue:
            dependent = queue.popleft()
            if dependent in result:
                continue
            result.add(dependent)
            queue.extend(reverse.get(dependent, set()) - result)
        return result

    def reverse_edges(self) -> Dict[str, Set[str]]:
        reverse: dict[str, set[str]] = defaultdict(set)
        for source, targets in self.edges.items():
            reverse.setdefault(source, set())
            for target in targets:
                reverse[target].add(source)
        return dict(reverse)

    def missing(self) -> Dict[str, Set[str]]:
        known = set(self.edges)
        return {
            source: dependencies - known
            for source, dependencies in self.edges.items()
            if dependencies - known
        }

    def cycles(self) -> List[List[str]]:
        """Return deterministic simple cycles found by depth-first search."""
        cycles: list[list[str]] = []
        seen_cycles: set[tuple[str, ...]] = set()
        state: dict[str, int] = {}
        stack: list[str] = []

        def canonical(cycle: list[str]) -> tuple[str, ...]:
            ring = cycle[:-1]
            if not ring:
                return ()
            rotations = [tuple(ring[index:] + ring[:index]) for index in range(len(ring))]
            return min(rotations)

        def visit(node: str) -> None:
            state[node] = 1
            stack.append(node)
            for dependency in sorted(self.edges.get(node, set())):
                if dependency not in self.edges:
                    continue
                if state.get(dependency, 0) == 0:
                    visit(dependency)
                elif state.get(dependency) == 1:
                    start = stack.index(dependency)
                    cycle = stack[start:] + [dependency]
                    key = canonical(cycle)
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(cycle)
            stack.pop()
            state[node] = 2

        for node in sorted(self.edges):
            if state.get(node, 0) == 0:
                visit(node)
        return cycles

    def topological_order(self) -> List[str]:
        """Return dependencies before dependents; raise on cycles."""
        if self.cycles():
            raise ValueError("dependency graph contains a cycle")
        indegree = {node: 0 for node in self.edges}
        reverse = self.reverse_edges()
        for node, dependencies in self.edges.items():
            indegree[node] = sum(1 for dependency in dependencies if dependency in indegree)
        ready = deque(sorted(node for node, count in indegree.items() if count == 0))
        order: list[str] = []
        while ready:
            node = ready.popleft()
            order.append(node)
            for dependent in sorted(reverse.get(node, set())):
                if dependent not in indegree:
                    continue
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        if len(order) != len(indegree):
            raise ValueError("dependency graph contains a cycle")
        return order

    def issues(self) -> List[DependencyIssue]:
        issues: list[DependencyIssue] = []
        for source, missing in sorted(self.missing().items()):
            for dependency in sorted(missing):
                issues.append(
                    DependencyIssue(
                        code="missing_dependency",
                        snippet_id=source,
                        dependency_id=dependency,
                        message=f"{source} references missing snippet {dependency}",
                    )
                )
        for cycle in self.cycles():
            issues.append(
                DependencyIssue(
                    code="dependency_cycle",
                    snippet_id=cycle[0],
                    message=" -> ".join(cycle),
                )
            )
        return issues

    def layers(self) -> List[List[str]]:
        """Group nodes by dependency depth for visualisation."""
        order = self.topological_order()
        depth: dict[str, int] = {}
        for node in order:
            dependencies = [depth[item] for item in self.edges.get(node, set()) if item in depth]
            depth[node] = (max(dependencies) + 1) if dependencies else 0
        layers: list[list[str]] = []
        for node in order:
            while len(layers) <= depth[node]:
                layers.append([])
            layers[depth[node]].append(node)
        return layers

    def to_dict(self) -> dict:
        return {
            "edges": {node: sorted(targets) for node, targets in sorted(self.edges.items())},
            "titles": dict(sorted(self.titles.items())),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DependencyGraph":
        edges = {
            str(node): {str(target) for target in targets or []}
            for node, targets in (data.get("edges") or {}).items()
        }
        titles = {str(node): str(title) for node, title in (data.get("titles") or {}).items()}
        return cls(edges=edges, titles=titles)
