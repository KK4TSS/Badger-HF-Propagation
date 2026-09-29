# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Chris Parrish (KK4TSS)
"""Small verified HTTPS JSON client for MicroPython; no insecure fallback."""
import json
import socket
import ssl
import time
from hf_errors import ClockUnset, TLSFailure
from hf_settings import TLS_CA_FILE, HTTP_MAX_BYTES


def milliseconds():
    if hasattr(time, 'ticks_ms'):
        return time.ticks_ms()
    return int(time.monotonic() * 1000)


def elapsed(now, then):
    if hasattr(time, 'ticks_diff'):
        return time.ticks_diff(now, then)
    return now - then


def verified_context(ca_file):
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.verify_mode = ssl.CERT_REQUIRED
        if hasattr(context, 'check_hostname'):
            context.check_hostname = True
        with open(ca_file, 'rb') as f:
            context.load_verify_locations(cadata=f.read())
        return context
    except (OSError, ValueError, AttributeError, TypeError) as error:
        raise TLSFailure('TLS verification unavailable') from error


class Reader:
    def __init__(self, stream, budget):
        self.stream = stream
        self.budget = budget

    def read(self, amount):
        self.budget()
        chunk = self.stream.read(amount)
        self.budget()
        return chunk or b''

    def exact(self, amount):
        result = bytearray()
        while len(result) < amount:
            chunk = self.read(min(1024, amount - len(result)))
            if not chunk:
                raise OSError('Truncated response')
            result.extend(chunk)
        return result

    def line(self):
        result = bytearray()
        while len(result) <= 1024:
            char = self.read(1)
            if not char:
                raise OSError('Truncated HTTP headers')
            result.extend(char)
            if char == b'\n':
                return bytes(result)
        raise OSError('HTTP line too long')


def response_json(reader, maximum):
    status = reader.line().split()
    if len(status) < 2 or status[0] not in (b'HTTP/1.0', b'HTTP/1.1') or status[1] != b'200':
        raise OSError('HTTP response not OK')  # Redirects are deliberately not followed.
    headers = {}
    total = 0
    while True:
        line = reader.line()
        total += len(line)
        if total > 8192:
            raise OSError('HTTP headers too large')
        if line == b'\r\n':
            break
        if b':' not in line:
            raise OSError('Malformed HTTP header')
        key, value = line.split(b':', 1)
        key, value = key.strip().lower(), value.strip().lower()
        if key in headers:
            raise OSError('Duplicate HTTP header')
        headers[key] = value
    if headers.get(b'content-encoding', b'identity') != b'identity':
        raise OSError('Unsupported response encoding')
    transfer = headers.get(b'transfer-encoding')
    length = headers.get(b'content-length')
    body = bytearray()
    if transfer:
        if transfer != b'chunked' or length is not None:
            raise OSError('Unsupported HTTP framing')
        while True:
            size = int(reader.line().split(b';', 1)[0].strip(), 16)
            if size < 0 or size > maximum - len(body):
                raise OSError('Response too large')
            if size == 0:
                trailer_size = 0
                while True:
                    line = reader.line()
                    trailer_size += len(line)
                    if trailer_size > 8192:
                        raise OSError('HTTP trailers too large')
                    if line == b'\r\n':
                        break
                break
            body.extend(reader.exact(size))
            if reader.exact(2) != b'\r\n':
                raise OSError('Malformed HTTP chunk')
    elif length is not None:
        size = int(length)
        if size < 0 or size > maximum:
            raise OSError('Response too large')
        body = reader.exact(size)
    else:
        while True:
            chunk = reader.read(min(1024, maximum - len(body) + 1))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > maximum:
                raise OSError('Response too large')
    return json.loads(body.decode('utf-8'))


def get_json(url, timeout=8, ca_file=None):
    # Never allow a settings change or redirect to silently remove TLS.
    if not url.startswith('https://'):
        raise TLSFailure('HTTPS required')
    host, separator, path = url[8:].partition('/')
    if (not host or len(host) > 253 or
            any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in host)
            or any(ord(c) <= 32 or ord(c) >= 127 for c in path)):
        raise ValueError('Invalid HTTPS URL')
    if time.gmtime()[0] < 2025:
        raise ClockUnset('Set device UTC clock')
    context = verified_context(ca_file or TLS_CA_FILE)
    address = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)[0]
    raw = socket.socket(address[0], socket.SOCK_STREAM, address[2])
    stream = None
    started = milliseconds()

    def budget():
        remaining = timeout - elapsed(milliseconds(), started) / 1000
        if remaining <= 0:
            raise OSError('HTTP deadline exceeded')
        target = stream if stream is not None and hasattr(stream, 'settimeout') else raw
        target.settimeout(remaining)

    try:
        budget()
        raw.connect(address[-1])
        budget()
        try:
            # CERT_REQUIRED plus server_hostname performs chain and hostname
            # checks on Badgeware's mbedTLS port. Never retry with CERT_NONE.
            stream = context.wrap_socket(raw, server_hostname=host)
        except (OSError, ValueError) as error:
            raise TLSFailure('Certificate or TLS handshake failed') from error
        request = ('GET /' + path + ' HTTP/1.0\r\nHost: ' + host +
                   '\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n').encode()
        offset = 0
        while offset < len(request):
            budget()
            written = stream.write(request[offset:])
            if not written:
                raise OSError('HTTP write failed')
            offset += written
        return response_json(Reader(stream, budget), HTTP_MAX_BYTES)
    finally:
        try:
            if stream is not None:
                stream.close()
        finally:
            raw.close()
