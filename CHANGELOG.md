# Changelog

## [1.0.0] - 2026-09-28

Initial release.

### Features

- Current NOAA SFI and Kp observations with UTC timestamps and geomagnetic status.
- Three-date Kp forecast and SFI/Kp trend screens.
- Saved snapshots, backup recovery, offline readings and save-failure labels.
- Automatic refresh at startup when data is stale, manual refresh and scheduled
  three-hour refresh attempts.
- Verified HTTPS downloads with a bundled trust certificate and an offline
  certificate-expiry reminder beginning 90 days before expiry.
- Distinct cancellation, clock, TLS and download-failure messages.
- Battery indicator, configurable brief Kp condition lights, editable settings
  and optional KK4TSS badge shortcut.
- Bundled icon and bitmap lettering for Badger 2350 / Badgeware v3.
- GPL v3 license with attribution to Chris Parrish (KK4TSS).

### Known limitations

- Desktop tests simulate the badge runtime. Wi-Fi/TLS, launcher, e-paper and
  RTC wake/sleep behavior require physical-device verification.
- Feed requests can block input for their network timeout; cancellation is
  checked during connection and between requests.
- Global observations and geomagnetic forecasts are not location-specific HF
  band predictions.
