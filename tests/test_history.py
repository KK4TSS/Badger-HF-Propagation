# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hf_data as data


class HistoryTests(unittest.TestCase):
    def test_forecast_excludes_observed_and_groups_peak_by_date(self):
        rows = [
            {'time_tag': '2026-09-28T00:00:00', 'kp': 9, 'observed': 'observed'},
            {'time_tag': '2026-09-29T00:00:00', 'kp': 2, 'observed': 'predicted'},
            {'time_tag': '2026-09-28T06:00:00', 'kp': 3, 'observed': 'estimated'},
            {'time_tag': '2026-09-28T09:00:00', 'kp': 4, 'observed': 'estimated'},
            {'time_tag': '2026-09-30T00:00:00', 'kp': 1, 'observed': 'predicted'},
            {'time_tag': '2026-10-01T00:00:00', 'kp': 5, 'observed': 'predicted'},
            {'time_tag': '2026-09-29T03:00:00', 'kp': 'NaN', 'observed': 'predicted'}]
        result = data.parse_forecast(list(reversed(rows)))
        self.assertEqual([day['value'] for day in result], [4, 2, 1])
        self.assertEqual(result[0]['kind'], 'estimated')
        self.assertEqual(result[-1]['date'], '2026-09-30')

    def test_history_is_sorted_bounded_and_daily_solar_uses_latest(self):
        sfi = [{'time_tag': '2026-09-%02dT12:00:00' % day, 'flux': 100 + day} for day in range(1, 10)]
        sfi.append({'time_tag': '2026-09-09T18:00:00', 'flux': 155})
        kp = [['time_tag', 'Kp']] + [['2026-09-%02dT00:00:00' % day, 2] for day in range(1, 29)]
        result = data.parse(list(reversed(sfi)), kp)
        self.assertEqual(len(result['sfi_history']), 7)
        self.assertEqual(result['sfi_history'][-1]['value'], 155)
        self.assertEqual(len(result['kp_history']), 24)
        self.assertEqual(result['kp_history'][0]['time'], '2026-09-05T00:00:00')

    def test_forecast_failure_keeps_new_observations_and_old_forecast(self):
        wlan = SimpleNamespace(active=lambda _: None, isconnected=lambda: True)
        network = SimpleNamespace(WLAN=lambda _: wlan, STA_IF=0)
        old = [{'date': '2026-09-28', 'value': 3, 'kind': 'predicted'}]
        feeds = [[{'time_tag': '2026-09-28T12:00:00', 'flux': 150}],
                 [['time_tag', 'Kp'], ['2026-09-28 12:00:00', '2']], OSError('forecast down')]
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, 'CACHE', str(Path(tmp) / 'cache.json')), patch.dict('sys.modules', {'network': network, 'secrets': SimpleNamespace()}), patch.object(data, 'get_json', side_effect=feeds):
            result = data.refresh(lambda: False, {'forecast': old})
            self.assertEqual(result['sfi']['value'], 150)
            self.assertEqual(result['forecast'], old)
            self.assertTrue(result['forecast_failed'])
            self.assertEqual(data.read_cache(), result)

    def test_old_cache_remains_usable(self):
        old = {'sfi': {'time': '2026-09-28T00:00:00', 'value': 150},
               'kp': {'time': '2026-09-28T00:00:00', 'value': 2}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, 'CACHE', str(Path(tmp) / 'cache.json')):
            Path(data.CACHE).write_text(json.dumps(old))
            self.assertEqual(data.read_cache(), old)

    def test_table_forecast_and_no_predicted_periods(self):
        result = data.parse_forecast([['time_tag', 'kp', 'observed'],
            ['2026-09-29 03:00:00', '4.33', 'predicted']])
        self.assertEqual(result[0]['value'], 4.33)
        with self.assertRaises(ValueError):
            data.parse_forecast([{'time_tag': '2026-09-29T03:00:00',
                                  'kp': 3, 'observed': 'observed'}])

    def test_cancellation_leaves_cache_untouched(self):
        wlan = SimpleNamespace(active=lambda _: None, isconnected=lambda: True)
        network = SimpleNamespace(WLAN=lambda _: wlan, STA_IF=0)
        feeds = [[{'time_tag': '2026-09-28T12:00:00', 'flux': 150}],
                 [['time_tag', 'Kp'], ['2026-09-28 12:00:00', '2']]]
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, 'CACHE', str(Path(tmp) / 'cache.json')), patch.dict('sys.modules', {'network': network, 'secrets': SimpleNamespace()}), patch.object(data, 'get_json', side_effect=feeds) as fetch:
            Path(data.CACHE).write_text('previous cache')
            cancel = iter((False, False, True))
            with self.assertRaisesRegex(OSError, 'Cancelled'):
                data.refresh(lambda: next(cancel))
            self.assertEqual(Path(data.CACHE).read_text(), 'previous cache')
            self.assertEqual(fetch.call_count, 2)
