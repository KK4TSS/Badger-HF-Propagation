# SPDX-License-Identifier: GPL-3.0-only
import unittest
from unittest.mock import Mock, patch
import hf_lights


class LightTests(unittest.TestCase):
    def setUp(self):
        self.output = Mock()
        self.lights = hf_lights.Indicator(self.output, lambda a, b: (a-b+32768) % 65536-32768)
        self.clock = patch.object(hf_lights.time, 'gmtime', return_value=(2026, 9, 28, 12, 0, 0))
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def show(self, kp, stamp='2026-09-28T12:00:00', event='button', now=0):
        self.lights.show({'kp': {'value': kp, 'time': stamp}}, now, event)

    def test_thresholds_and_timeout(self):
        for kp, count in ((0,1), (2.9,1), (3,2), (3.9,2), (4,3), (4.9,3), (5,4), (9,4)):
            self.show(kp)
            self.output.assert_called_with(*([0.50]*count+[0]*(4-count)))
            self.lights.update(1500)
            self.output.assert_called_with(0,0,0,0)

    def test_storm_flash_and_tick_wrap(self):
        self.show(5, now=65000)
        self.lights.update(65500)
        self.output.assert_called_with(0,0,0,0)
        self.lights.update(464)
        self.output.assert_called_with(.50,.50,.50,.50)
        self.lights.update(964)
        self.output.assert_called_with(0,0,0,0)

    def test_pause_preserves_storm_phase_across_tick_wrap(self):
        self.show(5, now=65000)
        self.lights.pause(100)  # 636 ms displayed: storm is in its off phase.
        self.lights.resume(3000)
        self.output.assert_called_with(0,0,0,0)
        self.lights.update(3364)  # 1000 ms total displayed.
        self.output.assert_called_with(.50,.50,.50,.50)
        self.lights.pause(3464)
        self.lights.resume(4000)
        self.lights.update(4399)
        self.output.assert_called_with(.50,.50,.50,.50)
        self.lights.update(4400)
        self.output.assert_called_with(0,0,0,0)

    def test_stop_cancels_paused_lights_and_expired_lights_do_not_resume(self):
        self.show(2)
        self.lights.pause(100)
        self.lights.stop()
        self.lights.resume(200)
        self.assertIsNone(self.lights.started)
        self.show(2)
        self.lights.pause(1500)
        self.lights.resume(2000)
        self.assertIsNone(self.lights.started)
        self.output.assert_called_with(0,0,0,0)

    def test_missing_invalid_stale_and_future_data_stay_off(self):
        for kp, stamp in ((10,'2026-09-28T12:00:00'), (float('nan'),'2026-09-28T12:00:00'),
                          (3,'bad'), (3,'2026-09-28T09:00:00'), (3,'2026-09-28T12:06:00')):
            self.show(kp, stamp)
            self.assertIsNone(self.lights.started)
        self.lights.show(None, 0, 'button')
        self.assertIsNone(self.lights.started)
        with patch.object(hf_lights.time, 'gmtime', return_value=(2000,1,1,0,0,0)):
            self.show(2)
            self.assertIsNone(self.lights.started)

    def test_settings_and_retrigger(self):
        for setting,event in (('LIGHTS_ENABLED','button'),('LIGHTS_ON_BUTTON','button'),('LIGHTS_ON_REFRESH','refresh')):
            with patch.object(hf_lights.settings, setting, False):
                self.show(2,event=event)
                self.assertIsNone(self.lights.started)
        with patch.object(hf_lights.settings,'LIGHTS_FRESH_ONLY',False), patch.object(hf_lights.settings,'LIGHTS_STORM_FLASH',False), patch.object(hf_lights.settings,'LIGHTS_BRIGHTNESS',.1), patch.object(hf_lights.settings,'LIGHTS_DURATION_MS',1000):
            self.show(5,'2020-01-01T00:00:00')
            self.lights.update(500)
            self.output.assert_called_with(.1,.1,.1,.1)
            self.show(5,now=900)
            self.lights.update(1000)
            self.output.assert_called_with(.1,.1,.1,.1)
            self.lights.update(1900)
            self.output.assert_called_with(0,0,0,0)
