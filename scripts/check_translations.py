#!/usr/bin/env python3
"""Check that all translation files have the same keys as en.json."""

import json
from pathlib import Path
import sys


def flatten_keys(obj: dict, prefix: str = "") -> set[str]:
    """Recursively flatten a nested dict into dot-separated key paths."""
    keys = set()
    for k, v in obj.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(flatten_keys(v, full))
        else:
            keys.add(full)
    return keys


def main() -> int:
    translations_dir = Path(__file__).resolve().parent.parent / "custom_components" / "hitachi_yutaki" / "translations"
    reference_file = translations_dir / "en.json"

    if not reference_file.exists():
        print(f"ERROR: Reference file not found: {reference_file}")
        return 1

    with open(reference_file) as f:
        reference_keys = flatten_keys(json.load(f))

    errors = 0
    translation_files = sorted(p for p in translations_dir.glob("*.json") if p.name != "en.json")

    if not translation_files:
        print("No translation files found besides en.json")
        return 0

    for path in translation_files:
        with open(path) as f:
            file_keys = flatten_keys(json.load(f))

        missing = reference_keys - file_keys
        extra = file_keys - reference_keys
        name = path.name

        if missing or extra:
            errors += 1
            print(f"\n{name}:")
            if missing:
                print(f"  Missing keys ({len(missing)}):")
                for key in sorted(missing):
                    print(f"    - {key}")
            if extra:
                print(f"  Extra keys ({len(extra)}):")
                for key in sorted(extra):
                    print(f"    + {key}")
        else:
            print(f"{name}: OK ({len(file_keys)} keys)")

    if errors:
        print(f"\n{errors} file(s) with mismatched keys")
        return 1

    print(f"\nAll {len(translation_files)} translation files match en.json ({len(reference_keys)} keys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
