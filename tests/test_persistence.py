# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
import json
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import hf_data as data


def snapshot(kp=2):
    solar = {'time': '2026-09-28T00:00:00', 'value': 150}
    planetary = {'time': '2026-09-28T03:00:00', 'value': kp}
    return {'sfi': solar, 'kp': planetary, 'sfi_history': [solar],
            'kp_history': [planetary], 'forecast': [
                {'date': '2026-09-29', 'value': 3, 'kind': 'predicted'}]}


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        mock = patch.object(data, 'CACHE', str(self.root / 'state' / 'hf.json'))
        mock.start()
        self.addCleanup(mock.stop)

    def test_repeated_saves_and_restart_read_from_another_directory(self):
        self.assertTrue(data.save_cache(snapshot(1)))
        self.assertTrue(data.save_cache(snapshot(2)))
        cwd = os.getcwd()
        try:
            os.chdir(self.root)
            self.assertEqual(data.read_cache(), snapshot(2))
        finally:
            os.chdir(cwd)
        self.assertEqual(data.read_cache_file(data.CACHE + '.bak'), snapshot(1))

    def test_fresh_module_after_restart_loads_all_three_screens(self):
        self.assertTrue(data.save_cache(snapshot()))
        spec = importlib.util.spec_from_file_location('restarted_hf_data', data.__file__)
        restarted = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(restarted)
        restarted.CACHE = data.CACHE
        restored = restarted.read_cache()
        self.assertEqual(restored, snapshot())
        self.assertTrue(restored['forecast'])
        self.assertTrue(restored['sfi_history'])
        self.assertTrue(restored['kp_history'])

    def test_recovers_previous_snapshot_if_primary_is_corrupted(self):
        data.save_cache(snapshot(1))
        data.save_cache(snapshot(2))
        Path(data.CACHE).write_text('{interrupted')
        self.assertEqual(data.read_cache(), snapshot(1))

    def test_failed_commit_preserves_previous_cache(self):
        data.save_cache(snapshot(1))
        original = os.rename
        def fail_commit(source, target):
            if source.endswith('.tmp'):
                raise OSError('interrupted commit')
            return original(source, target)
        with patch.object(os, 'rename', side_effect=fail_commit):
            self.assertFalse(data.save_cache(snapshot(2)))
        self.assertEqual(data.read_cache(), snapshot(1))

    def test_rename_works_when_filesystem_refuses_overwrite(self):
        original = os.rename
        def fat_rename(source, target):
            if Path(target).exists():
                raise OSError('destination exists')
            return original(source, target)
        with patch.object(os, 'rename', side_effect=fat_rename):
            for value in (1, 2, 3):
                self.assertTrue(data.save_cache(snapshot(value)))
        self.assertEqual(data.read_cache(), snapshot(3))

    def test_recovers_completed_temporary_first_save(self):
        Path(data.CACHE).parent.mkdir()
        Path(data.CACHE + '.tmp').write_text(json.dumps(snapshot()))
        self.assertEqual(data.read_cache(), snapshot())

    def test_recovered_temp_survives_another_failed_write(self):
        Path(data.CACHE).parent.mkdir()
        Path(data.CACHE + '.tmp').write_text(json.dumps(snapshot(1)))
        self.assertEqual(data.read_cache(), snapshot(1))
        def interrupted(obj, file):
            file.write('{')
            raise OSError('disk full')
        with patch.object(data.json, 'dump', side_effect=interrupted):
            self.assertFalse(data.save_cache(snapshot(2)))
        self.assertEqual(data.read_cache(), snapshot(1))

    def test_failed_temp_promotion_does_not_destroy_recovered_data(self):
        Path(data.CACHE).parent.mkdir()
        Path(data.CACHE + '.tmp').write_text(json.dumps(snapshot(1)))
        with patch.object(os, 'rename', side_effect=OSError('cannot rename')):
            self.assertFalse(data.save_cache(snapshot(2)))
        self.assertEqual(data.read_cache(), snapshot(1))


class FreshnessTests(unittest.TestCase):
    def test_three_hour_kp_boundary(self):
        self.assertFalse(data.needs_refresh(snapshot(), '2026-09-28T05:59:59'))
        self.assertTrue(data.needs_refresh(snapshot(), '2026-09-28T06:00:00'))

    def test_daily_solar_flux_has_separate_threshold(self):
        saved = snapshot()
        saved['sfi']['time'] = '2026-09-27T00:00:00'
        self.assertFalse(data.needs_refresh(saved, '2026-09-28T05:00:00'))
        saved['sfi']['time'] = '2026-09-26T00:00:00'
        self.assertTrue(data.needs_refresh(saved, '2026-09-28T05:00:00'))

    def test_unknown_or_backward_clock_and_missing_data_refresh(self):
        self.assertTrue(data.needs_refresh(None, '2026-09-28T05:00:00'))
        for now in ('2000-01-01T00:00:00', '2026-09-27T00:00:00', 'invalid'):
            self.assertTrue(data.needs_refresh(snapshot(), now))
        saved = snapshot()
        saved.pop('forecast')
        self.assertTrue(data.needs_refresh(saved, '2026-09-28T05:00:00'))

    def test_clock_uses_calendar_fields_not_platform_epoch(self):
        with patch.object(data.time, 'gmtime', return_value=(2026, 9, 28, 5, 0, 0, 0, 0)):
            self.assertFalse(data.needs_refresh(snapshot()))
