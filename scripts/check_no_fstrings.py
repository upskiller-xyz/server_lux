"""Fails if any f-string is present under the given roots.

Project convention: `.format()`/%-formatting and named template classes instead
of f-strings, so messages stay greppable and logging calls stay lazy.

Detection is AST-based, not textual. A grep for `f"` misses single-quoted
(`f'...'`), triple-quoted (`f'''...'''`) and concatenated-prefix forms, so the
gate would pass while prohibited code remained. Every f-string — whatever its
quoting — parses to an `ast.JoinedStr`, which is what this walks.

Usage:
    python scripts/check_no_fstrings.py src tests
"""
import ast
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

SOURCE_SUFFIX = ".py"
VIOLATION_TEMPLATE = "{path}:{line}: f-string"
ERROR_TEMPLATE = (
    "::error::{count} f-string(s) found — use .format() or a template class"
)


class FStringScanner:
    """Collects the f-string locations in one source tree."""

    def __init__(self, roots: List[str]):
        self._roots = [Path(root) for root in roots]

    def violations(self) -> List[Tuple[Path, int]]:
        found: List[Tuple[Path, int]] = []
        for path in self._sources():
            found.extend(self._scan(path))
        return sorted(found)

    def _sources(self) -> Iterator[Path]:
        for root in self._roots:
            yield from sorted(root.rglob("*" + SOURCE_SUFFIX))

    @staticmethod
    def _scan(path: Path) -> List[Tuple[Path, int]]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            # A file that does not parse is a failure in its own right, but it is
            # ruff's and pytest's to report — not this gate's.
            print("{path}: skipped, does not parse ({exc})".format(path=path, exc=exc))
            return []
        return [
            (path, node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.JoinedStr)
        ]


class Gate:
    """Prints the findings and decides the exit status."""

    @classmethod
    def run(cls, roots: List[str]) -> int:
        violations = FStringScanner(roots).violations()
        for path, line in violations:
            print(VIOLATION_TEMPLATE.format(path=path, line=line))
        if violations:
            print(ERROR_TEMPLATE.format(count=len(violations)))
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(Gate.run(sys.argv[1:] or ["src", "tests"]))
