# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Editable HF Propagation settings. Restart the app after changes.

Keep a copy of this file before replacing the app during an update.
Wi-Fi credentials stay in Badgeware's secrets.py.
"""

# Timing (positive values; RTC refresh interval is in whole hours, 1–23).
REFRESH_HOURS = 3
IDLE_SLEEP_MS = 30_000
BADGE_HOLD_MS = 800
BATTERY_CHECK_MS = 60_000
UPDATE_POLL_MS = 10

# Brief rear-light condition indicator (1 quiet, 2 unsettled, 3 active,
# 4 storm). Restart the app after editing. Lights stop before sleep/exit.
LIGHTS_ENABLED = True
LIGHTS_ON_REFRESH = True       # After a successful NOAA observation refresh.
LIGHTS_ON_BUTTON = True        # After A/B/C or a short Down press.
LIGHTS_BRIGHTNESS = 0.50        # 0.0 off to 1.0 full brightness.
LIGHTS_DURATION_MS = 1500      # Display duration; limited to 0–30000 ms.
LIGHTS_STORM_FLASH = True      # False makes all four storm lights steady.
LIGHTS_FLASH_MS = 500          # Time per on/off phase; minimum 100 ms.
LIGHTS_FRESH_ONLY = True       # Suppress old Kp or an unknown device clock.

# Network timeouts and polling.
HTTP_TIMEOUT_SECONDS = 8
HTTP_MAX_BYTES = 256 * 1024
TLS_CA_FILE = "/system/apps/hf_propagation/amazon-root-ca-1.der"
WIFI_TIMEOUT_MS = 15_000
WIFI_POLL_MS = 50

# Saved observations are stale after these ages, in seconds.
KP_MAX_AGE = 3 * 60 * 60
SFI_MAX_AGE = 36 * 60 * 60
CLOCK_SKEW_SECONDS = 300

# History retained for the trend charts.
SFI_HISTORY_DAYS = 7
KP_HISTORY_POINTS = 24

# Advanced: destinations and storage. Changing CACHE does not move old data.
BADGE_APP = "/system/apps/callsign_badger"
CACHE = "/state/hf-propagation.json"
BASE = "https://services.swpc.noaa.gov"
SFI_FEED = "/json/f107_cm_flux.json"
KP_FEED = "/products/noaa-planetary-k-index.json"
FORECAST_FEED = "/products/noaa-planetary-k-index-forecast.json"
