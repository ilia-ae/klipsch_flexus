#!/usr/bin/env python3
"""Check that an environment has exactly what a committed requirements file pins.

Run with the environment's own interpreter, isolated, for example
``.venv-test/bin/python -I scripts/check_pins.py requirements_test.txt``. Standard
library only. Every ``name==version`` line must be installed at that version
and every other requirement must be installed at all; ``-r`` includes are
followed. Exit 1 lists the differences (the venv is stale: recreate it).

``--collections ansible/requirements.yml ansible/collections`` checks installed
Ansible collections (their MANIFEST.json) against the pinned list instead; it
needs PyYAML, which the Ansible venv has.

The local CI (make test-latest / test-min / venv / collections) runs this so
signed evidence never describes a run on tooling the commit does not pin.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import sys
from pathlib import Path

REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements(path: Path, seen: set[Path] | None = None) -> list[tuple[str, str | None]]:
    seen = seen if seen is not None else set()
    path = path.resolve()
    if path in seen:
        return []
    seen.add(path)
    found: list[tuple[str, str | None]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split(" #", 1)[0].split("\t#", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "--requirement ")):
            found += requirements(path.parent / line.split(None, 1)[1], seen)
            continue
        if line.startswith("-"):
            continue  # pip options (index URLs, constraints) do not name packages
        match = REQUIREMENT.match(line.split(";", 1)[0])
        if not match:
            raise SystemExit(f"{path}: cannot parse requirement {raw!r}")
        name, spec = match.groups()
        pinned = re.fullmatch(r"==\s*([^\s,]+)", spec.strip())
        found.append((name, pinned.group(1) if pinned else None))
    return found


def check_packages(path: Path) -> list[str]:
    problems = []
    for name, pinned in requirements(path):
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"{name}: not installed (wanted {pinned or 'any version'})")
            continue
        if pinned is not None and installed != pinned:
            problems.append(f"{name}: installed {installed}, {path.name} pins {pinned}")
    return problems


def check_collections(path: Path, root: Path) -> list[str]:
    import yaml  # the Ansible venv has PyYAML

    problems = []
    for item in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("collections", []):
        name, wanted = item["name"], str(item.get("version", ""))
        namespace, collection = name.split(".", 1)
        manifest = root / "ansible_collections" / namespace / collection / "MANIFEST.json"
        try:
            installed = json.loads(manifest.read_text(encoding="utf-8"))["collection_info"]["version"]
        except (OSError, ValueError, KeyError):
            problems.append(f"{name}: not installed in {root} (wanted {wanted})")
            continue
        if installed != wanted:
            problems.append(f"{name}: installed {installed}, {path.name} pins {wanted}")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "--collections":
        problems = check_collections(Path(argv[1]), Path(argv[2]))
        source = argv[1]
    elif len(argv) == 1:
        problems = check_packages(Path(argv[0]))
        source = argv[0]
    else:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: check_pins.py REQUIREMENTS | --collections REQUIREMENTS.yml COLLECTIONS_DIR", file=sys.stderr)
        return 2
    if problems:
        print(f"{sys.prefix} does not match {source}:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
