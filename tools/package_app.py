# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Build the standalone install ZIP using only this project's files."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def build_archive(output=None):
    output = Path(output) if output else ROOT / 'dist' / 'HF-Propagation.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = [path for path in (ROOT / 'hf_propagation').rglob('*')
             if path.is_file() and path.suffix in ('.py', '.png', '.der')
             and not any(part.startswith('.') or part == '__pycache__'
                         for part in path.relative_to(ROOT).parts)
             and path.name != 'secrets.py']
    paths += [ROOT / name for name in ('README.md', 'LICENSE', 'VERSION',
                                       'CHANGELOG.md', 'THIRD_PARTY_NOTICES.md', 'docs/images/screens-preview.png',
                                       'docs/images/forecast-trends-native.png')]
    # Fixed metadata makes identical source trees produce identical ZIPs.
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            info = ZipInfo(path.relative_to(ROOT).as_posix(), (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return output


if __name__ == '__main__':
    print(build_archive())
