# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Offline reminder for the bundled HTTPS trust certificate."""
import time
from hf_data import stamp_seconds

# Update alongside amazon-root-ca-1.der. A regression test verifies this date
# against the actual certificate so a replacement cannot silently drift.
CA_EXPIRES_UTC = '2038-01-17T00:00:00'
WARNING_DAYS = 90


def warning(now=None):
    try:
        now = time.gmtime() if now is None else now
        if now[0] < 2025:
            return None  # An unset clock cannot establish certificate age.
        stamp = '%04d-%02d-%02dT%02d:%02d:%02d' % tuple(now[:6])
        remaining = stamp_seconds(CA_EXPIRES_UTC) - stamp_seconds(stamp)
        if remaining <= 0:
            return 'CA EXPIRED ' + CA_EXPIRES_UTC[:10]
        if remaining <= WARNING_DAYS * 86400:
            return 'CA EXPIRES ' + CA_EXPIRES_UTC[:10]
    except (ValueError, OverflowError, OSError):
        pass
    return None
