# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import hf_data as p

class PropagationTests(unittest.TestCase):
    def test_latest_not_array_order(self):
        rows=[{'time_tag':'2026-09-28T00:00:00','Kp':0.67},
              {'time_tag':'2026-09-27T21:00:00','Kp':2},
              {'time_tag':'2026-09-29T00:00:00','Kp':None}]
        self.assertEqual(p.latest(rows,'Kp',0,9)['value'],0.67)
        self.assertEqual(p.latest(list(reversed(rows)),'Kp',0,9)['value'],0.67)

    def test_legacy_table_and_invalid(self):
        self.assertEqual(p.latest([['time_tag','Kp'],['2026-09-28 00:00:00','3.33']],'Kp',0,9)['value'],3.33)
        for value in (-1,10,None,'NaN'):
            with self.assertRaises(ValueError):
                p.latest([{'time_tag':'2026-09-28T00:00:00','Kp':value}],'Kp',0,9)

    def test_fetch_uses_verified_client(self):
        with patch('hf_http.get_json', return_value={'ok': True}) as fetch:
            self.assertEqual(p.get_json('/test'), {'ok': True})
            fetch.assert_called_once_with(p.BASE + '/test', timeout=p.HTTP_TIMEOUT_SECONDS)

    def test_threshold(self):
        self.assertIn('Storm level',p.summary(5))
        self.assertIn('Active',p.summary(4))
        self.assertIn('Below',p.summary(3))

if __name__=='__main__':unittest.main()
