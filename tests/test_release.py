# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Check install archive integrity and release tag/changelog safeguards."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseTests(unittest.TestCase):
    def test_install_archive_is_complete_clean_and_reproducible(self):
        package = load_script('package_app')
        with tempfile.TemporaryDirectory() as directory:
            first = package.build_archive(Path(directory) / 'first.zip')
            second = package.build_archive(Path(directory) / 'second.zip')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                for name in ('hf_propagation/__init__.py', 'hf_propagation/icon.png',
                             'hf_propagation/hf_settings.py', 'hf_propagation/hf_http.py',
                             'hf_propagation/hf_errors.py', 'hf_propagation/amazon-root-ca-1.der',
                             'THIRD_PARTY_NOTICES.md', 'VERSION', 'LICENSE',
                             'CHANGELOG.md', 'README.md', 'docs/images/screens-preview.png',
                             'docs/images/forecast-trends-native.png'):
                    self.assertIn(name, names)
                self.assertTrue(any(n.startswith('hf_propagation/type/') for n in names))
                for name in names:
                    self.assertFalse(any(part.startswith('.') or part == '__pycache__'
                                         for part in Path(name).parts), name)
                    self.assertNotEqual(Path(name).name, 'secrets.py')
                    self.assertNotIn(Path(name).suffix, ('.pyc', '.pyo'))
                    self.assertEqual(archive.read(name), (ROOT / name).read_bytes())

    def test_release_requires_matching_tag_and_changelog(self):
        release = load_script('prepare_release')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'VERSION').write_text('1.0.0\n')
            (root / 'CHANGELOG.md').write_text(
                '# Changelog\n\n## [1.0.0] - 2026-09-28\n\nFirst release.\n\n'
                '## [0.9.0] - 2026-09-27\n\nOld release.\n')
            with self.assertRaises(ValueError):
                release.prepare('v9.0.0', root)
            notes = release.prepare('v1.0.0', root)
            self.assertEqual(notes.read_text(), 'First release.\n')
            (root / 'CHANGELOG.md').write_text('# Changelog\n')
            with self.assertRaises(ValueError):
                release.prepare('v1.0.0', root)
