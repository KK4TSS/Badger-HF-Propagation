# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Standalone HF Propagation for Badger 2350 / Badgeware v3."""
import time
import powman
from hf_settings import REFRESH_HOURS, IDLE_SLEEP_MS, BADGE_HOLD_MS, BADGE_APP, UPDATE_POLL_MS
import hf_data
import hf_certificate
from hf_errors import Cancelled, ClockUnset, TLSFailure
import hf_screen
from badge_battery import Indicator
battery = Indicator()
from hf_lights import Indicator as LightIndicator
lights = LightIndicator(badge.caselights, time.ticks_diff)

data = hf_data.read_cache()
status = "Saved snapshot" if data else "UP refresh"
dirty = True
startup_pending = badge.wake_reason() == powman.WAKE_RTC or hf_data.needs_refresh(data)
# Clear the latched wake interrupt before arming the next refresh. The RTC
# alarm also works while awake (including when USB prevents idle sleep).
rtc.clear_alarm()
rtc.set_alarm(hours=REFRESH_HOURS)
startup_shown = False
page = 0
last_input = time.ticks_ms()
down_started = None
down_blocked = False
notice = None
certificate_notice = None
certificate_checked = None


def on_exit():
    lights.stop()
    rtc.clear_alarm()


def open_callsign_badge():
    # Follow Badgeware's launcher: save the destination and reset into it.
    # reset() waits for button release, avoiding a held key in the next app.
    if not (file_exists(BADGE_APP + "/__init__.py") or
            file_exists(BADGE_APP + "/__init__.mpy")):
        return "Badge not installed"
    try:
        menu_state = {"active": 0, "running": BADGE_APP}
        State.load("menu", menu_state)
        menu_state["running"] = BADGE_APP
        State.modify("menu", menu_state)
        # Badgeware State.save can silently fail (for example on a full disk).
        # Do not reset unless the destination was actually persisted.
        saved_state = {}
        State.load("menu", saved_state)
        if saved_state.get("running") != BADGE_APP:
            return "Badge switch failed"
        on_exit()
        reset()
    except OSError:
        return "Badge switch failed"
    return None


def cancelled():
    badge.poll()
    return badge.pressed(BUTTON_DOWN) or badge.held(BUTTON_DOWN)


def update():
    global data, status, dirty, last_input, page, down_started, down_blocked, notice
    global startup_pending, startup_shown
    global certificate_notice, certificate_checked
    badge.poll()
    light_event = 'button' if any(badge.pressed(button) for button in
                                 (BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_DOWN)) else None
    now = time.ticks_ms()
    lights.update(now)
    if certificate_checked is None or time.ticks_diff(now, certificate_checked) >= 60000:
        next_notice = hf_certificate.warning()
        if next_notice != certificate_notice:
            certificate_notice = next_notice
            dirty = True
        certificate_checked = now
    if battery.update(badge, time.ticks_ms(), time.ticks_diff):
        dirty = True
    if badge.pressed():
        last_input = time.ticks_ms()
        if notice:
            notice = None
            dirty = True

    next_page = page
    if badge.pressed(BUTTON_A):
        next_page = 0
    elif badge.pressed(BUTTON_B):
        next_page = 1
    elif badge.pressed(BUTTON_C):
        next_page = 2
    if next_page != page:
        down_started = None
        down_blocked = badge.pressed(BUTTON_DOWN) or badge.held(BUTTON_DOWN)
        page = next_page
        dirty = True

    down = badge.pressed(BUTTON_DOWN) or badge.held(BUTTON_DOWN)
    if badge.pressed(BUTTON_DOWN):
        startup_pending = False
    if not down:
        down_started = None
        down_blocked = False
    elif page != 0:
        down_started = None
        down_blocked = True
    elif not down_blocked:
        if down_started is None and badge.pressed(BUTTON_DOWN):
            down_started = time.ticks_ms()
        if down_started is not None and time.ticks_diff(time.ticks_ms(), down_started) >= BADGE_HOLD_MS:
            down_started = None
            down_blocked = True
            failure = open_callsign_badge()
            if failure:
                notice = failure
                dirty = True
            else:
                return

    scheduled = rtc.alarm_status()
    if scheduled:
        rtc.clear_alarm()
        rtc.set_alarm(hours=REFRESH_HOURS)
    if badge.pressed(BUTTON_UP) or ((scheduled or (startup_pending and startup_shown)) and not down):
        lights.stop()
        light_event = None
        startup_pending = False  # One attempt per launch, even if Wi-Fi fails.
        # A Down press used to cancel refresh must be released before it can
        # start a badge-navigation hold, even if the HTTP request blocks.
        down_started = None
        down_blocked = True
        hf_screen.draw(data, "Fetching NOAA observations...", page)
        if certificate_notice:
            hf_screen.draw_certificate_notice(certificate_notice)
        battery.draw(screen, color, inverted=(page != 0))
        badge.update()
        previous_status = status
        try:
            data = hf_data.refresh(cancelled, data)
            light_event = 'refresh'
            status = "NOAA snapshot / NOT SAVED" if data.get("save_failed") else "NOAA snapshot"
        except Cancelled:
            status = "Cancelled / " + previous_status.split("Cancelled / ")[-1]
        except ClockUnset:
            status = "Clock unset"
        except TLSFailure:
            status = "TLS verification failed"
        except Exception:
            status = "Fetch failed"
        # Retry on the next interval even after failure or cancellation.
        rtc.clear_alarm()
        rtc.set_alarm(hours=REFRESH_HOURS)
        dirty = True
        last_input = time.ticks_ms()

    if dirty:
        lights.pause(time.ticks_ms())
        hf_screen.draw(data, status, page)
        if certificate_notice:
            hf_screen.draw_certificate_notice(certificate_notice)
        if notice and page == 0:
            hf_screen.draw_badge_notice(notice)
        battery.draw(screen, color, inverted=(page != 0))
        badge.update()
        dirty = False
        lights.resume(time.ticks_ms())
    startup_shown = True
    if light_event:
        lights.show(data, time.ticks_ms(), light_event)
    lights.update(time.ticks_ms())

    if time.ticks_diff(time.ticks_ms(), last_input) >= IDLE_SLEEP_MS and not badge.usb_connected():
        lights.stop()
        badge.sleep()
        last_input = time.ticks_ms()
    time.sleep_ms(UPDATE_POLL_MS)


run(update)
