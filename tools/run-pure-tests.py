#!/usr/bin/env python3
"""Runs the dependency-free backend tests without pytest.

pytest is the supported runner (`cd backend && pytest`), and CI uses it. This
script exists for environments that cannot install packages: it collects
`test_*` callables from the modules named on the command line — or from every
test module that imports cleanly — and runs them, reporting the same failures
pytest would for plain-assert tests. It does not support fixtures, so the
database and API tests are skipped here by design.

    python3 tools/run-pure-tests.py                # everything that imports
    python3 tools/run-pure-tests.py test_composer  # one module
"""

from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))


def discover() -> list[str]:
    return sorted(p.stem for p in (BACKEND / "tests").glob("test_*.py"))


def main() -> int:
    names = sys.argv[1:] or discover()
    passed = failed = skipped = 0
    failures: list[str] = []

    for name in names:
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            skipped += 1
            print(f"SKIP  {name}  ({exc.name} not installed)")
            continue

        for attr in sorted(vars(module)):
            if not attr.startswith("test_"):
                continue
            fn = getattr(module, attr)
            if not callable(fn):
                continue
            # Anything wanting fixtures belongs to pytest, not here.
            if fn.__code__.co_argcount:
                skipped += 1
                print(f"SKIP  {name}::{attr}  (needs fixtures)")
                continue
            try:
                fn()
            except Exception:
                failed += 1
                failures.append(f"{name}::{attr}\n{traceback.format_exc()}")
                print(f"FAIL  {name}::{attr}")
            else:
                passed += 1
                print(f"ok    {name}::{attr}")

    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    for failure in failures:
        print("\n" + "=" * 70 + "\n" + failure)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
