# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""HF overview rendering; independent of networking and app controls."""

def condition(kp):
    if kp >= 5:
        return 'STORM'
    if kp >= 4:
        return 'ACTIVE'
    if kp >= 3:
        return 'UNSETTLED'
    return 'QUIET'


def draw_overview(data, status):
    from hf_type import draw_text, width
    screen.pen = color.white
    screen.clear()
    screen.pen = color.black

    def center(text, y, scale=1, cx=132, inverted=False):
        draw_text(screen, text, int(cx - width(text, scale) / 2), y, scale, inverted=inverted)

    center('HF PROPAGATION', 0)
    screen.rectangle(0, 28, 264, 56)
    screen.pen = color.white
    screen.font = font.sins
    state = '' if state_label(status) == 'NOAA' else ' / ' + state_label(status)
    screen.text('GEOMAGNETIC' + state, 7, 29)
    center(condition(data['kp']['value']) if data else 'NO DATA', 41, 2 if width(condition(data['kp']['value']) if data else 'NO DATA', 2) <= 250 else 1, inverted=True)
    screen.pen = color.black
    center('SFI', 85, cx=66)
    center('KP', 85, cx=198)
    screen.rectangle(131, 88, 1, 61)
    sfi_text = ('%.0f' % data['sfi']['value']) if data else '--'
    center(sfi_text, 105, 2 if width(sfi_text, 2) <= 124 else 1, cx=66)
    center(('%.1f' % data['kp']['value']) if data else '--', 105, 2, cx=198)
    screen.rectangle(0, 151, 264, 1)
    screen.font = font.sins
    if status == 'Clock unset':
        footer = 'Set UTC clock / press UP'
    elif status == 'TLS verification failed':
        footer = 'Check clock / CA / firmware'
    elif data:
        def stamp(item):
            t = item['time']
            return t[5:7] + '/' + t[8:10] + ' ' + t[11:16] + 'Z'
        footer = 'SFI ' + stamp(data['sfi']) + '  KP ' + stamp(data['kp'])
        if screen.measure_text(footer)[0] > 250:
            footer = 'S ' + stamp(data['sfi']) + '  K ' + stamp(data['kp'])
    else:
        footer = 'UPDATING...' if status.startswith('Fetching') else 'UP: FETCH DATA'
    screen.text(footer, 7, 158)


def state_label(status):
    if status.startswith('Cancelled'):
        return 'CANCELLED'
    if status == 'Clock unset':
        return 'SET CLOCK'
    if status == 'TLS verification failed':
        return 'TLS ERROR'
    if 'NOT SAVED' in status:
        return 'UNSAVED'
    if status.startswith('Fetching'):
        return 'UPDATING'
    if status.startswith('Fetch failed'):
        return 'FAILED'
    if status.startswith('Saved'):
        return 'SAVED'
    return 'NOAA'


def small_center(text, cx, y):
    screen.text(text, int(cx - screen.measure_text(text)[0] / 2), y)


def heading(title, status):
    from hf_type import draw_text
    screen.pen = color.white
    screen.clear()
    screen.pen = color.black
    screen.rectangle(0, 0, 264, 29)
    draw_text(screen, title, 7, 4, inverted=True)
    screen.pen = color.white
    screen.font = font.sins
    label = state_label(status)
    screen.text(label, int(257 - screen.measure_text(label)[0]), 10)
    screen.pen = color.black


def navigation(active):
    screen.pen = color.black
    screen.rectangle(0, 156, 264, 1)
    for page, text, x, w in ((0, 'A NOW', 4, 47), (1, 'B FCST', 54, 54),
                              (2, 'C TREND', 111, 61)):
        screen.pen = color.black
        if page == active:
            screen.rectangle(x, 159, w, 15)
            screen.pen = color.white
        small_center(text, x + w // 2, 161)
    screen.pen = color.black
    screen.text('UP REFRESH', 190, 161)


def draw_forecast(data, status):
    from hf_type import draw_text, width
    heading('FORECAST', status)
    days = (data or {}).get('forecast', [])
    failed = (data or {}).get('forecast_failed')
    subtitle = 'FETCH FAILED / SAVED DATES' if failed and days else 'DAILY PEAK KP / UTC'
    small_center(subtitle, 132, 35)
    if days:
        for index in range(3):
            x, cx = 6 + index * 86, 46 + index * 86
            screen.pen = color.light_grey
            screen.rectangle(x, 51, 80, 99)
            screen.pen = color.white
            screen.rectangle(x + 1, 52, 78, 97)
            screen.pen = color.black
            if index >= len(days):
                small_center('NO PERIOD', cx, 62)
                draw_text(screen, '--', cx - width('--', 2) // 2, 78, 2)
                continue
            day = days[index]
            date = day['date'][5:7] + '/' + day['date'][8:10]
            small_center(date, cx, 58)
            screen.pen = color.light_grey
            screen.rectangle(x + 9, 73, 62, 1)
            screen.pen = color.black
            value = '%.1f' % day['value']
            draw_text(screen, value, cx - width(value, 2) // 2, 79, 2)
            label = condition(day['value'])
            if day['value'] >= 5:
                screen.rectangle(x + 3, 115, 74, 15)
                screen.pen = color.white
            small_center(label, cx, 117)
            screen.pen = color.black
            kind = {'estimated': 'EST', 'predicted': 'PRED', 'mixed': 'EST/PRED'}
            small_center(kind[day['kind']], cx, 136)
    else:
        draw_text(screen, 'NO FORECAST', (264 - width('NO FORECAST')) // 2, 68)
        small_center('Press UP to fetch NOAA data', 132, 102)
        if failed:
            small_center('Forecast unavailable / retry UP', 132, 128)
    navigation(1)


def minutes(stamp):
    # Gregorian ordinal, independent of device clock and Unix epoch choice.
    year, month, day = int(stamp[:4]), int(stamp[5:7]), int(stamp[8:10])
    prior = year - 1
    days = 365 * prior + prior // 4 - prior // 100 + prior // 400
    months = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    days += sum(months[:month - 1]) + day
    if month > 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days += 1
    return days * 1440 + int(stamp[11:13]) * 60 + int(stamp[14:16])


def plot_line(x1, y1, x2, y2):
    # Portable raster line using the same rectangle API as the overview.
    steps = max(abs(x2 - x1), abs(y2 - y1), 1)
    for step in range(steps + 1):
        x = x1 + (x2 - x1) * step // steps
        y = y1 + (y2 - y1) * step // steps
        screen.rectangle(x, y, 1, 2)


def chart(points, title, cadence, y, fixed=None):
    from hf_type import draw_text
    screen.pen = color.black
    screen.text(title, 7, y)
    screen.text(cadence, 7, y + 42)
    if not points:
        draw_text(screen, '--', 7, y + 17)
        screen.text('No history saved', 98, y + 16)
        screen.text('UP to refresh', 98, y + 32)
        return
    values = [point['value'] for point in points]
    latest = ('%.1f' if fixed else '%.0f') % values[-1]
    draw_text(screen, latest, 7, y + 18)
    low, high = fixed if fixed else (max(0, int(min(values)) - 1), int(max(values)) + 1)
    left, right, top, height = 98, 253, y + 3, 32
    bottom = top + height
    screen.pen = color.light_grey
    for gy in (top, top + height // 2, bottom):
        screen.rectangle(left, gy, right - left + 1, 1)
    screen.pen = color.black
    for value, gy in ((high, top - 2), (low, bottom - 6)):
        label = '%.0f' % value
        screen.text(label, int(92 - screen.measure_text(label)[0]), gy)
    start, end = minutes(points[0]['time']), minutes(points[-1]['time'])
    previous = None
    for point in points:
        x = left + int((minutes(point['time']) - start) * (right - left) / max(1, end - start))
        py = bottom - int((point['value'] - low) * height / (high - low))
        if fixed:
            screen.rectangle(x - 1, py, 3, max(1, bottom - py))
        else:
            if previous:
                plot_line(previous[0], previous[1], x, py)
            screen.rectangle(x - 1, py - 1, 3, 3)
        previous = (x, py)
    def label(stamp):
        return stamp[5:7] + '/' + stamp[8:10] + ' ' + stamp[11:13] + 'Z'
    screen.text(label(points[0]['time']), left, y + 42)
    last_label = label(points[-1]['time'])
    screen.text(last_label, int(256 - screen.measure_text(last_label)[0]), y + 42)


def draw_trends(data, status):
    heading('TRENDS', status)
    chart((data or {}).get('sfi_history', []), 'SFI', 'DAILY', 36)
    screen.pen = color.light_grey
    screen.rectangle(7, 94, 250, 1)
    chart((data or {}).get('kp_history', []), 'KP', '3-HOUR', 101, (0, 9))
    navigation(2)


def draw(data, status, page=0):
    if page == 1:
        draw_forecast(data, status)
    elif page == 2:
        draw_trends(data, status)
    else:
        draw_overview(data, status)


def draw_certificate_notice(notice):
    # Persistent footer on every page. Buttons continue to work normally.
    screen.pen = color.black
    screen.rectangle(0, 152, 264, 24)
    screen.pen = color.white
    screen.font = font.sins
    small_center(notice, 132, 153)
    small_center('UPDATE HF APP / A B C: PAGES', 132, 165)


def draw_badge_notice(notice):
    # Keep the saved/offline indicator; only replace the timestamp footer.
    screen.pen = color.white
    screen.rectangle(0, 152, 264, 24)
    screen.pen = color.black
    screen.font = font.sins
    text = 'Install apps/kk4tss first' if notice == 'Badge not installed' else 'Badge switch failed - try again'
    screen.text(text, 7, 158)
