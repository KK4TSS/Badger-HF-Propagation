# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""NOAA observations for Badgeware. No location-based band predictions."""
import json
import time
from hf_errors import Cancelled, ClockUnset, TLSFailure

from hf_settings import (
    BASE, CACHE, KP_MAX_AGE, SFI_MAX_AGE,
    HTTP_TIMEOUT_SECONDS, WIFI_TIMEOUT_MS, WIFI_POLL_MS, CLOCK_SKEW_SECONDS,
    SFI_HISTORY_DAYS, KP_HISTORY_POINTS, SFI_FEED, KP_FEED, FORECAST_FEED,
)


def valid_stamp(stamp):
    if not isinstance(stamp, str) or len(stamp) != 19:
        return False
    if (stamp[4] != '-' or stamp[7] != '-' or stamp[10] != 'T'
            or stamp[13] != ':' or stamp[16] != ':'):
        return False
    parts = (stamp[:4], stamp[5:7], stamp[8:10], stamp[11:13], stamp[14:16], stamp[17:19])
    if not all(part.isdigit() for part in parts):
        return False
    year, month, day, hour, minute, second = [int(part) for part in parts]
    if not (1 <= year <= 9999 and 1 <= month <= 12):
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return 1 <= day <= days[month - 1] and hour < 24 and minute < 60 and second < 60


def table_rows(rows):
    if not isinstance(rows, list):
        return []
    if rows and isinstance(rows[0], list):
        header = rows[0]
        if not all(isinstance(key, str) for key in header):
            return []
        return [dict(zip(header, row)) for row in rows[1:] if isinstance(row, list)]
    return rows


def records(rows, key, low, high):
    valid = {}
    for row in table_rows(rows):
        try:
            value = float(row[key])
            stamp = row['time_tag'].replace(' ', 'T')[:19]
            if low <= value <= high and valid_stamp(stamp):
                valid[stamp] = value
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            continue
    return [{'time': stamp, 'value': valid[stamp]} for stamp in sorted(valid)]


def latest(rows, key, low, high):
    values = records(rows, key, low, high)
    if not values:
        raise ValueError('No valid observations')
    return values[-1]


def parse(sfi, kp):
    solar = records(sfi, 'flux', 1, 1000)
    planetary = records(kp, 'Kp', 0, 9)
    if not solar or not planetary:
        raise ValueError('No valid observations')
    # One latest observation per UTC day keeps the solar trend compact.
    daily = {}
    for item in solar:
        daily[item['time'][:10]] = item
    return {'sfi': solar[-1], 'kp': planetary[-1],
            'sfi_history': [daily[day] for day in sorted(daily)[-SFI_HISTORY_DAYS:]],
            'kp_history': planetary[-KP_HISTORY_POINTS:]}


def parse_forecast(rows):
    days = {}
    for row in table_rows(rows):
        if not isinstance(row, dict) or row.get('observed') not in ('estimated', 'predicted'):
            continue
        points = records([row], 'kp', 0, 9)
        if not points:
            continue
        point = points[0]
        day = point['time'][:10]
        if day not in days:
            days[day] = {'date': day, 'value': point['value'], 'kind': row['observed']}
        else:
            days[day]['value'] = max(days[day]['value'], point['value'])
            if days[day]['kind'] != row['observed']:
                days[day]['kind'] = 'mixed'
    result = [days[day] for day in sorted(days)[:3]]
    if not result:
        raise ValueError('No forecast periods')
    return result


def summary(kp):
    if kp >= 5:
        return 'Storm level: HF may be disrupted'
    if kp >= 4:
        return 'Active geomagnetic conditions'
    return 'Below geomagnetic storm level'


def cached_points(items, low, high):
    if not isinstance(items, list):
        return []
    rows = [{'time_tag': item.get('time'), 'value': item.get('value')}
            for item in items if isinstance(item, dict)]
    return records(rows, 'value', low, high)


def read_cache_file(path):
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        result = {}
        for key, low, high, limit in (('sfi', 1, 1000, SFI_HISTORY_DAYS), ('kp', 0, 9, KP_HISTORY_POINTS)):
            current = cached_points([data.get(key)], low, high)
            if not current:
                return None
            result[key] = current[0]
            history_key = key + '_history'
            if history_key in data:
                result[history_key] = cached_points(data[history_key], low, high)[-limit:]
        if 'forecast' in data:
            days = {}
            for item in data['forecast'] if isinstance(data['forecast'], list) else []:
                try:
                    day, value, kind = item['date'], float(item['value']), item['kind']
                    if (valid_stamp(day + 'T00:00:00') and 0 <= value <= 9
                            and kind in ('estimated', 'predicted', 'mixed')):
                        days[day] = {'date': day, 'value': value, 'kind': kind}
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
            result['forecast'] = [days[day] for day in sorted(days)[:3]]
        if 'forecast_failed' in data:
            result['forecast_failed'] = bool(data['forecast_failed'])
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def read_cache():
    # A previous good snapshot survives interrupted writes and app replacement.
    for path in (CACHE, CACHE + '.bak', CACHE + '.tmp'):
        data = read_cache_file(path)
        if data is not None:
            return data
    return None


def save_cache(data):
    import os
    try:
        parent = CACHE.rsplit('/', 1)[0] if '/' in CACHE else ''
        if parent:
            try:
                os.stat(parent)
            except OSError:
                os.mkdir(parent)
        # Never truncate the only valid snapshot recovered from an interrupted
        # first save. Promote it before reusing the temporary filename.
        if (read_cache_file(CACHE) is None and read_cache_file(CACHE + '.bak') is None
                and read_cache_file(CACHE + '.tmp') is not None):
            try:
                os.remove(CACHE)
            except OSError:
                pass
            os.rename(CACHE + '.tmp', CACHE)
            sync = getattr(os, 'sync', None)
            if sync:
                sync()
        with open(CACHE + '.tmp', 'w') as f:
            json.dump(data, f)
            f.flush()
        sync = getattr(os, 'sync', None)
        if sync:
            sync()
        if read_cache_file(CACHE + '.tmp') is None:
            return False
        # FAT does not consistently allow renaming over an existing file.
        # Rotate only a validated primary so an interrupted save retains backup.
        if read_cache_file(CACHE) is not None:
            try:
                os.remove(CACHE + '.bak')
            except OSError:
                pass
            os.rename(CACHE, CACHE + '.bak')
        else:
            try:
                os.remove(CACHE)
            except OSError:
                pass
        os.rename(CACHE + '.tmp', CACHE)
        if sync:
            sync()
        return read_cache_file(CACHE) is not None
    except (OSError, ValueError, TypeError):
        return False


def stamp_seconds(stamp):
    year, month, day = int(stamp[:4]), int(stamp[5:7]), int(stamp[8:10])
    prior = year - 1
    days = 365 * prior + prior // 4 - prior // 100 + prior // 400
    months = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    days += sum(months[:month - 1]) + day
    if month > 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days += 1
    return days * 86400 + int(stamp[11:13]) * 3600 + int(stamp[14:16]) * 60 + int(stamp[17:19])


def needs_refresh(data, now=None):
    if not data:
        return True
    try:
        if now is None:
            clock = time.gmtime()
            now = '%04d-%02d-%02dT%02d:%02d:%02d' % clock[:6]
        if not valid_stamp(now) or int(now[:4]) < 2025:
            return True  # Unknown clock: try once, retaining saved readings.
        current = stamp_seconds(now)
        for key, maximum_age in (('kp', KP_MAX_AGE), ('sfi', SFI_MAX_AGE)):
            stamp = data[key]['time']
            if not valid_stamp(stamp):
                return True
            age = current - stamp_seconds(stamp)
            if age < -CLOCK_SKEW_SECONDS or age >= maximum_age:
                return True
        if (not data.get('forecast') or data.get('forecast_failed')
                or not data.get('sfi_history') or not data.get('kp_history')):
            return True
        return max(day['date'] for day in data['forecast']) < now[:10]
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return True


def get_json(path):
    from hf_http import get_json as verified_get_json
    return verified_get_json(BASE + path, timeout=HTTP_TIMEOUT_SECONDS)


def refresh(cancel, previous=None):
    import network
    import secrets
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        ssid = getattr(secrets, 'WIFI_SSID', '')
        password = getattr(secrets, 'WIFI_PASSWORD', '')
        if not ssid:
            raise OSError('Set Wi-Fi in secrets.py')
        wlan.connect(ssid, password)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if cancel():
                raise Cancelled('Cancelled')
            if time.ticks_diff(time.ticks_ms(), start) > WIFI_TIMEOUT_MS:
                raise OSError('Wi-Fi timeout')
            time.sleep_ms(WIFI_POLL_MS)
    if cancel():
        raise Cancelled('Cancelled')
    sfi = get_json(SFI_FEED)
    if cancel():
        raise Cancelled('Cancelled')
    kp = get_json(KP_FEED)
    data = parse(sfi, kp)
    if cancel():
        raise Cancelled('Cancelled')
    try:
        data['forecast'] = parse_forecast(get_json(FORECAST_FEED))
        data['forecast_failed'] = False
    except (Cancelled, ClockUnset, TLSFailure):
        raise
    except Exception:
        # A forecast outage must not discard newly fetched observations.
        data['forecast'] = (previous or {}).get('forecast', [])
        data['forecast_failed'] = True
    if cancel():
        raise Cancelled('Cancelled')
    if not save_cache(data):
        data['save_failed'] = True
    return data
