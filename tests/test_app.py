# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Exercise the actual standalone entry point with a simulated badge runtime."""
import hf_lights
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from hf_errors import Cancelled, ClockUnset, TLSFailure

APP = Path(__file__).resolve().parents[1] / 'hf_propagation' / '__init__.py'


class AppTests(unittest.TestCase):
    def test_lights_stop_before_network_sleep_and_exit(self):
        with patch('hf_settings.LIGHTS_FRESH_ONLY', False):
            update = self.launch({'kp': {'value': 4}})
            self.pressed = {'b'}
            update()
            self.badge.caselights.assert_called_with(0.50, 0.50, 0.50, 0)
            def refresh(*args):
                self.badge.caselights.assert_called_with(0, 0, 0, 0)
                return {'kp': {'value': 2}}
            self.data.refresh.side_effect = refresh
            self.pressed = {'up'}
            update()
            self.badge.caselights.assert_called_with(0.50, 0, 0, 0)
            self.pressed = set()
            self.now = 30001
            update()
            self.badge.caselights.assert_called_with(0, 0, 0, 0)
            self.badge.sleep.assert_called_once()
            self.pressed = {'a'}
            update()
            update.__globals__['on_exit']()
            self.badge.caselights.assert_called_with(0, 0, 0, 0)

    def test_battery_redraw_preserves_remaining_light_time(self):
        with patch('hf_settings.LIGHTS_FRESH_ONLY', False):
            update = self.launch({'kp': {'value': 2}}, usb=True)
            self.pressed = {'a'}
            update()
            self.pressed = set()
            self.now = 100
            def redraw():
                self.badge.caselights.assert_called_with(0, 0, 0, 0)
                self.now += 2000  # Blocking e-paper refresh exceeds light duration.
            self.badge.update.side_effect = redraw
            with patch.object(update.__globals__['battery'], 'update', return_value=True):
                update()
            self.badge.caselights.assert_called_with(0.50, 0, 0, 0)
            self.now = 3499
            update()
            self.badge.caselights.assert_called_with(0.50, 0, 0, 0)
            self.now = 3500
            update()
            self.badge.caselights.assert_called_with(0, 0, 0, 0)

    def test_custom_refresh_and_idle_settings(self):
        with patch('hf_settings.REFRESH_HOURS', 1), patch('hf_settings.IDLE_SLEEP_MS', 5000):
            update = self.launch()
        self.rtc.set_alarm.assert_called_once_with(hours=1)
        self.now = 4999
        update()
        self.badge.sleep.assert_not_called()
        self.now = 5000
        update()
        self.badge.sleep.assert_called_once()

    def launch(self, cached=None, stale=False, rtc_wake=False, usb=False):
        self.pressed = set()
        self.held = set()
        self.now = 0
        self.badge = SimpleNamespace(
            caselights=Mock(), poll=Mock(), pressed=lambda button=None: bool(self.pressed) if button is None else button in self.pressed,
            held=lambda button: button in self.held or button in self.pressed, update=Mock(),
            usb_connected=lambda: usb, sleep=Mock(), wake_reason=lambda: 1 if rtc_wake else 0)
        self.rtc = SimpleNamespace(clear_alarm=Mock(), set_alarm=Mock(), alarm_status=Mock(return_value=False))
        self.data = SimpleNamespace(read_cache=Mock(return_value=cached), needs_refresh=Mock(return_value=stale), refresh=Mock())
        self.screen = SimpleNamespace(draw=Mock(), draw_badge_notice=Mock(), draw_certificate_notice=Mock())
        self.certificate = SimpleNamespace(warning=Mock(return_value=None))
        self.clock = SimpleNamespace(ticks_ms=lambda: self.now, ticks_diff=lambda a, b: a-b, sleep_ms=Mock())
        self.runtime = patch.dict('sys.modules', {'hf_data': self.data, 'hf_screen': self.screen, 'time': self.clock,
                                                'hf_certificate': self.certificate,
                                                'powman': SimpleNamespace(WAKE_RTC=1)})
        self.runtime.start()
        self.addCleanup(self.runtime.stop)
        self.files = Mock(return_value=True)
        self.saved_menu = {'active': 4, 'running': '/system/apps/hf_propagation'}
        self.menu_state = SimpleNamespace(
            load=Mock(side_effect=lambda key, state: state.update(self.saved_menu)),
            modify=Mock(side_effect=lambda key, state: self.saved_menu.update(state)))
        self.reset = Mock()
        state = runpy.run_path(str(APP), init_globals={
            'screen': SimpleNamespace(pen=0, rectangle=Mock()), 'color': SimpleNamespace(white=255, black=0),
            'file_exists': self.files, 'State': self.menu_state, 'reset': self.reset, 'rtc': self.rtc,
            'badge': self.badge, 'BUTTON_A': 'a', 'BUTTON_B': 'b', 'BUTTON_C': 'c', 'BUTTON_UP': 'up', 'BUTTON_DOWN': 'down', 'run': lambda update: None})
        return state['update']

    def test_certificate_reminder_starts_offline_and_follows_pages(self):
        update = self.launch(usb=True)
        self.certificate.warning.return_value = 'CA EXPIRES 2038-01-17'
        for button in ('a', 'b', 'c'):
            self.pressed = {button}
            update()
            self.screen.draw_certificate_notice.assert_called_with('CA EXPIRES 2038-01-17')
        self.assertEqual(self.screen.draw_certificate_notice.call_count, 3)
        self.certificate.warning.assert_called_once()
        self.data.refresh.assert_not_called()
        self.pressed = set()
        self.now = 60000
        self.certificate.warning.return_value = 'CA EXPIRED 2038-01-17'
        update()
        self.screen.draw_certificate_notice.assert_called_with('CA EXPIRED 2038-01-17')
        self.now = 120000
        self.certificate.warning.return_value = None
        self.screen.draw.reset_mock()
        self.screen.draw_certificate_notice.reset_mock()
        update()
        self.screen.draw.assert_called_once()
        self.screen.draw_certificate_notice.assert_not_called()

    def test_alarm_wake_refreshes_even_if_saved_readings_look_fresh(self):
        update = self.launch({'kp': {'value': 2}}, rtc_wake=True)
        self.data.refresh.return_value = {'kp': {'value': 3}}
        update()
        self.data.refresh.assert_not_called()
        update()
        self.data.refresh.assert_called_once()
        self.rtc.set_alarm.assert_called_with(hours=3)
        self.now = 30001
        update()
        self.badge.sleep.assert_called_once()

    def test_scheduled_refresh_on_usb_preserves_page_and_rearms_after_failure(self):
        saved = {'kp': {'value': 2}}
        update = self.launch(saved, usb=True)
        self.pressed = {'c'}
        update()
        self.pressed = set()
        self.data.refresh.side_effect = OSError('offline')
        self.rtc.alarm_status.return_value = True
        update()
        self.screen.draw.assert_called_with(saved, 'Fetch failed', 2)
        self.rtc.set_alarm.assert_called_with(hours=3)
        self.rtc.alarm_status.return_value = False
        self.now = 30001
        update()
        self.data.refresh.assert_called_once()
        self.badge.sleep.assert_not_called()

    def test_down_skips_scheduled_refresh_and_rearms(self):
        update = self.launch()
        self.rtc.alarm_status.return_value = True
        self.pressed = {'down'}
        update()
        self.data.refresh.assert_not_called()
        self.rtc.set_alarm.assert_called_with(hours=3)

    def test_exit_clears_wake_alarm(self):
        update = self.launch()
        self.rtc.clear_alarm.reset_mock()
        update.__globals__['on_exit']()
        self.rtc.clear_alarm.assert_called_once()

    def test_standalone_start_does_not_fetch_or_need_badge_artwork(self):
        update = self.launch()
        update()
        self.screen.draw.assert_called_once_with(None, 'UP refresh', 0)
        self.data.refresh.assert_not_called()
        update()
        self.assertEqual(self.badge.update.call_count, 1)

    def test_saved_start_and_failed_refresh_preserve_observations(self):
        saved = {'sfi': {'value': 130}, 'kp': {'value': 2}}
        update = self.launch(saved)
        update()
        self.screen.draw.assert_called_with(saved, 'Saved snapshot', 0)
        self.data.refresh.side_effect = OSError('offline')
        self.pressed = {'up'}
        update()
        self.screen.draw.assert_called_with(saved, 'Fetch failed', 0)

    def test_successful_refresh_and_idle_sleep(self):
        update = self.launch()
        fresh = {'sfi': {'value': 150}, 'kp': {'value': 3}}
        self.data.refresh.return_value = fresh
        self.pressed = {'up'}
        update()
        self.screen.draw.assert_called_with(fresh, 'NOAA snapshot', 0)
        cancel = self.data.refresh.call_args.args[0]
        self.pressed = {'down'}
        self.assertTrue(cancel())
        self.pressed = set()
        self.now = 30001
        update()
        self.badge.sleep.assert_called_once()

    def test_navigation_is_offline_and_refresh_preserves_page(self):
        update = self.launch()
        update()
        for button, page in (('b', 1), ('c', 2), ('a', 0)):
            self.pressed = {button}
            update()
            self.screen.draw.assert_called_with(None, 'UP refresh', page)
            count = self.badge.update.call_count
            update()
            self.assertEqual(self.badge.update.call_count, count)
        self.data.refresh.assert_not_called()
        self.pressed = {'b'}
        update()
        self.data.refresh.return_value = {'forecast': []}
        self.pressed = {'up'}
        update()
        self.screen.draw.assert_called_with({'forecast': []}, 'NOAA snapshot', 1)

    def hold_down(self, update, duration=800):
        self.pressed = {'down'}
        update()
        self.pressed = set()
        self.held = {'down'}
        self.now += duration
        update()

    def test_long_down_opens_badge_only_once(self):
        update = self.launch()
        update()
        self.hold_down(update, 799)
        self.reset.assert_not_called()
        self.now += 1
        update()
        self.menu_state.modify.assert_called_once_with('menu', {'active': 4, 'running': '/system/apps/kk4tss'})
        self.reset.assert_called_once()
        update()
        self.reset.assert_called_once()

    def test_short_taps_do_not_accumulate(self):
        update = self.launch()
        for _ in range(3):
            self.hold_down(update, 300)
            self.held = set()
            update()
        self.reset.assert_not_called()

    def test_hold_on_other_pages_and_across_page_change_does_not_open_badge(self):
        for button in ('b', 'c'):
            update = self.launch()
            self.pressed = {button}
            update()
            self.hold_down(update, 1000)
            self.pressed = {'a'}
            update()
            self.pressed = set()
            self.now += 1000
            update()
            self.reset.assert_not_called()
            self.held = set()
            update()
            self.hold_down(update)
            self.reset.assert_called_once()

    def test_missing_badge_keeps_app_open(self):
        update = self.launch()
        self.files.return_value = False
        self.hold_down(update)
        self.screen.draw.assert_called_with(None, 'UP refresh', 0)
        self.screen.draw_badge_notice.assert_called_once_with('Badge not installed')
        self.menu_state.modify.assert_not_called()
        self.reset.assert_not_called()

    def test_cancelling_refresh_does_not_start_a_navigation_hold(self):
        update = self.launch()
        def refresh(cancel, previous):
            self.pressed = {'down'}
            self.held = {'down'}
            self.now += 1000
            self.assertTrue(cancel())
            raise Cancelled('Cancelled')
        self.data.refresh.side_effect = refresh
        self.pressed = {'up'}
        update()
        self.pressed = set()
        self.now += 1000
        update()
        self.reset.assert_not_called()
        self.held = set()
        update()
        self.hold_down(update)
        self.reset.assert_called_once()

    def test_failed_state_write_does_not_reset(self):
        update = self.launch()
        self.menu_state.modify.side_effect = lambda *args: None
        self.hold_down(update)
        self.reset.assert_not_called()
        self.screen.draw_badge_notice.assert_called_once_with('Badge switch failed')

    def test_missing_badge_preserves_saved_status_and_notice_clears(self):
        saved = {'sfi': {'value': 150}, 'kp': {'value': 2}}
        update = self.launch(saved)
        self.files.return_value = False
        self.hold_down(update)
        self.screen.draw.assert_called_with(saved, 'Saved snapshot', 0)
        self.screen.draw_badge_notice.assert_called_once_with('Badge not installed')
        self.held = set()
        self.pressed = {'a'}
        update()
        self.screen.draw.assert_called_with(saved, 'Saved snapshot', 0)
        self.screen.draw_badge_notice.assert_called_once()

    def test_startup_shows_saved_data_then_refreshes_once(self):
        old = {'kp': {'value': 2}}
        fresh = {'kp': {'value': 3}}
        update = self.launch(old, stale=True)
        self.data.refresh.return_value = fresh
        update()
        self.screen.draw.assert_called_with(old, 'Saved snapshot', 0)
        self.data.refresh.assert_not_called()
        update()
        self.screen.draw.assert_called_with(fresh, 'NOAA snapshot', 0)
        self.data.refresh.assert_called_once()
        update()
        self.data.refresh.assert_called_once()

    def test_failed_startup_refresh_keeps_cache_and_does_not_loop(self):
        old = {'kp': {'value': 2}}
        update = self.launch(old, stale=True)
        self.data.refresh.side_effect = OSError('offline')
        update()
        update()
        self.screen.draw.assert_called_with(old, 'Fetch failed', 0)
        for _ in range(5):
            update()
        self.data.refresh.assert_called_once()

    def test_no_cache_triggers_startup_fetch(self):
        update = self.launch(stale=True)
        self.data.refresh.return_value = {'kp': {'value': 3}}
        update()
        self.data.refresh.assert_not_called()
        update()
        self.data.refresh.assert_called_once()

    def test_down_cancels_pending_startup_refresh(self):
        update = self.launch(stale=True)
        update()
        self.pressed = {'down'}
        update()
        self.pressed = set()
        update()
        self.data.refresh.assert_not_called()

    def test_storage_failure_is_visible_without_discarding_new_data(self):
        update = self.launch(stale=True)
        fresh = {'kp': {'value': 3}, 'save_failed': True}
        self.data.refresh.return_value = fresh
        update()
        update()
        self.screen.draw.assert_called_with(fresh, 'NOAA snapshot / NOT SAVED', 0)

    def test_cancel_is_not_reported_as_offline(self):
        update = self.launch({'kp': {'value': 2}})
        self.data.refresh.side_effect = Cancelled('Cancelled')
        self.pressed = {'up'}
        update()
        self.screen.draw.assert_called_with({'kp': {'value': 2}}, 'Cancelled / Saved snapshot', 0)
        update()
        self.screen.draw.assert_called_with({'kp': {'value': 2}}, 'Cancelled / Saved snapshot', 0)

    def test_tls_and_clock_failures_keep_saved_data_with_specific_message(self):
        for error, status in ((ClockUnset('clock'), 'Clock unset'), (TLSFailure('tls'), 'TLS verification failed')):
            saved = {'kp': {'value': 2}}
            update = self.launch(saved)
            self.data.refresh.side_effect = error
            self.pressed = {'up'}
            update()
            self.screen.draw.assert_called_with(saved, status, 0)


if __name__ == '__main__':
    unittest.main()
