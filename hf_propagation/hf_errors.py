# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Failures that need distinct user-facing messages."""

class Cancelled(OSError):
    pass


class ClockUnset(OSError):
    pass


class TLSFailure(OSError):
    pass
