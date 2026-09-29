# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Nonblocking, short Kp condition display on the four rear lights."""
import time
import hf_settings as settings
from hf_data import stamp_seconds, valid_stamp


class Indicator:
    def __init__(self, output, ticks_diff):
        self.output = output
        self.diff = ticks_diff
        self.started = None
        self.last = None
        self.stop()

    def emit(self, values):
        if values != self.last:
            self.output(*values)
            self.last = values

    def stop(self):
        self.started = None
        self.paused = False
        self.displayed = 0
        self.emit((0, 0, 0, 0))

    def pause(self, now):
        self.update(now)
        if self.started is not None:
            self.displayed += self.diff(now, self.started)
            self.started = None
            self.paused = True
            self.emit((0, 0, 0, 0))

    def resume(self, now):
        if self.paused:
            self.paused = False
            self.started = now
            self.update(now)

    def show(self, data, now, event):
        self.stop()
        if not settings.LIGHTS_ENABLED:
            return
        if event == 'button' and not settings.LIGHTS_ON_BUTTON:
            return
        if event == 'refresh' and not settings.LIGHTS_ON_REFRESH:
            return
        try:
            kp = data['kp']['value']
            if not 0 <= kp <= 9:
                return
            if settings.LIGHTS_FRESH_ONLY:
                stamp = data['kp']['time']
                clock = time.gmtime()
                if clock[0] < 2025 or not valid_stamp(stamp):
                    return
                age = stamp_seconds('%04d-%02d-%02dT%02d:%02d:%02d' % tuple(clock[:6])) - stamp_seconds(stamp)
                if age < -settings.CLOCK_SKEW_SECONDS or age >= settings.KP_MAX_AGE:
                    return
            self.count = 4 if kp >= 5 else 3 if kp >= 4 else 2 if kp >= 3 else 1
            self.brightness = max(0.0, min(1.0, float(settings.LIGHTS_BRIGHTNESS)))
            self.duration = max(0, min(30000, int(settings.LIGHTS_DURATION_MS)))
            self.flash = max(100, int(settings.LIGHTS_FLASH_MS))
            self.blink = self.count == 4 and settings.LIGHTS_STORM_FLASH
        except (KeyError, TypeError, ValueError, OSError, OverflowError):
            return
        self.started = now
        self.update(now)

    def update(self, now):
        if self.started is None:
            return
        elapsed = self.displayed + self.diff(now, self.started)
        if elapsed >= self.duration:
            self.stop()
            return
        on = not self.blink or (elapsed // self.flash) % 2 == 0
        self.emit(tuple(self.brightness if on and i < self.count else 0 for i in range(4)))
