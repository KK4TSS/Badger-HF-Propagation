# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Small four-bar battery indicator for HF Propagation."""
from hf_settings import BATTERY_CHECK_MS

class Indicator:
    def __init__(self):
        self.value = (None, False)
        self.checked = None

    def update(self, badge, now, ticks_diff):
        if self.checked is not None and ticks_diff(now, self.checked) < BATTERY_CHECK_MS:
            return False
        self.checked = now
        try:
            level = max(0, min(100, float(badge.battery_level())))
            bars = 0 if level == 0 else min(4, int((level + 24.999) // 25))
            value = (bars, bool(badge.is_charging()))
        except (AttributeError, OSError, ValueError, TypeError):
            value = (None, False)
        changed = value != self.value
        self.value = value
        return changed

    def draw(self, screen, palette, inverted=False):
        old = screen.pen
        foreground = palette.white if inverted else palette.black
        background = palette.black if inverted else palette.white
        x, y = 242, 1
        try:
            screen.pen = background
            screen.rectangle(235, y, 27, 9)
            screen.pen = foreground
            screen.rectangle(x, y, 17, 9)
            screen.rectangle(x + 17, y + 3, 2, 3)
            screen.pen = background
            screen.rectangle(x + 1, y + 1, 15, 7)
            screen.pen = foreground
            bars, charging = self.value
            if bars is None:
                screen.rectangle(x + 6, y + 4, 5, 1)
            else:
                for i in range(bars):
                    screen.rectangle(x + 3 + i * 3, y + 2, 2, 5)
            if charging:
                for dx, dy, w in ((2, 0, 2), (1, 2, 2), (0, 4, 4), (1, 6, 2), (0, 8, 2)):
                    screen.rectangle(235 + dx, y + dy, w, 1)
        finally:
            screen.pen = old
