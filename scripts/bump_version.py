#!/usr/bin/env python3
"""Bump the integration version in manifest.json and pyproject.toml.

Usage: python scripts/bump_version.py [patch|minor|major|beta]

- patch (default): 2.1.0 → 2.1.1, or 2.1.0-beta.4 → 2.1.0 (promotes to release)
- minor: 2.1.0 → 2.2.0
- major: 2.1.0 → 3.0.0
- beta: 2.1.0 → 2.1.0-beta.1, or 2.1.0-beta.4 → 2.1.0-beta.5
"""

import json
import re
import sys

MANIFEST = "custom_components/hitachi_yutaki/manifest.json"
PYPROJECT = "pyproject.toml"

part = sys.argv[1] if len(sys.argv) > 1 else "patch"
if part not in ("patch", "minor", "major", "beta"):
    print(f'Error: invalid part "{part}" — use patch, minor, major, or beta')
    sys.exit(1)

with open(MANIFEST) as f:
    manifest = json.load(f)

old = manifest["version"]
match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?$", old)
if not match:
    print(f'Error: cannot parse version "{old}"')
    sys.exit(1)

major, minor, patch_v = int(match[1]), int(match[2]), int(match[3])
beta = int(match[4]) if match[4] else None

if part == "beta":
    beta = (beta or 0) + 1
    new = f"{major}.{minor}.{patch_v}-beta.{beta}"
elif part == "major":
    new = f"{major + 1}.0.0"
elif part == "minor":
    new = f"{major}.{minor + 1}.0"
# patch: promote beta to release, or increment patch
elif beta is not None:
    new = f"{major}.{minor}.{patch_v}"
else:
    new = f"{major}.{minor}.{patch_v + 1}"

# Update manifest.json
manifest["version"] = new
with open(MANIFEST, "w") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")

# Update pyproject.toml
with open(PYPROJECT) as f:
    content = f.read()
content = content.replace(f'version = "{old}"', f'version = "{new}"', 1)
with open(PYPROJECT, "w") as f:
    f.write(content)

print(f"Bumped {old} → {new} ({part})")
