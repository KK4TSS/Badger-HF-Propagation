# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Validate a release tag and extract its checked-in changelog entry."""
from pathlib import Path
import re
import sys


def prepare(tag, root):
    version = (root / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or tag != 'v' + version:
        raise ValueError('Release tag must equal v plus the MAJOR.MINOR.PATCH in VERSION')
    changelog = (root / 'CHANGELOG.md').read_text()
    match = re.search(r'^## \[' + re.escape(version) + r'\] - \d{4}-\d{2}-\d{2}\n(.*?)(?=^## |\Z)',
                      changelog, re.M | re.S)
    if not match or not match.group(1).strip():
        raise ValueError('Missing dated changelog entry for ' + version)
    output = root / 'dist' / 'release-notes.md'
    output.parent.mkdir(exist_ok=True)
    output.write_text(match.group(1).strip() + '\n')
    return output


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python tools/prepare_release.py vMAJOR.MINOR.PATCH')
    print(prepare(sys.argv[1], Path(__file__).resolve().parents[1]))
