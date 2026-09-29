# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import hf_data as data


class CacheTests(unittest.TestCase):
    def read(self, value):
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, 'CACHE', str(Path(tmp) / 'cache.json')):
            Path(data.CACHE).write_text(json.dumps(value))
            return data.read_cache()

    def snapshot(self):
        return {'sfi': {'value': 150, 'time': '2026-09-28T00:00:00'},
                'kp': {'value': 2, 'time': '2026-09-28T03:00:00'}}

    def test_numeric_strings_are_normalized(self):
        saved = self.snapshot()
        saved['kp']['value'] = '2.33'
        self.assertEqual(self.read(saved)['kp']['value'], 2.33)

    def test_invalid_core_data_is_rejected(self):
        for value in ('NaN', 'inf', -1, 10, None):
            saved = self.snapshot()
            saved['kp']['value'] = value
            self.assertIsNone(self.read(saved))
        saved = self.snapshot()
        saved['sfi']['time'] = 'x' * 19
        self.assertIsNone(self.read(saved))

    def test_bad_optional_data_does_not_break_good_snapshot(self):
        saved = self.snapshot()
        saved.update(sfi_history=[None, {'time': 'bad', 'value': 140}],
                     kp_history='bad', forecast=[{'date': '2026-09-28', 'value': 'NaN', 'kind': 'predicted'}])
        result = self.read(saved)
        self.assertEqual(result['kp']['value'], 2)
        self.assertEqual(result['sfi_history'], [])
        self.assertEqual(result['kp_history'], [])
        self.assertEqual(result['forecast'], [])

    def test_invalid_calendar_dates_are_rejected(self):
        for stamp in ('2026-02-30T00:00:00', '2026-09-28T00:00:99', '0000-09-28T00:00:00'):
            self.assertEqual(data.records([{'time_tag': stamp, 'Kp': 2}], 'Kp', 0, 9), [])
        self.assertEqual(len(data.records([{'time_tag': '2024-02-29T00:00:00', 'Kp': 2}], 'Kp', 0, 9)), 1)
