import io
import ssl
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import hf_http as http
from hf_errors import ClockUnset, TLSFailure

CA = Path(__file__).resolve().parents[1] / 'hf_propagation' / 'amazon-root-ca-1.der'


class HttpTests(unittest.TestCase):
    def parse(self, wire, maximum=100):
        return http.response_json(http.Reader(io.BytesIO(wire), lambda: None), maximum)

    def test_content_length_chunked_and_connection_close(self):
        for wire in (b'HTTP/1.0 200 OK\r\nContent-Length: 11\r\n\r\n{"ok":true}',
                     b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nB\r\n{"ok":true}\r\n0\r\n\r\n',
                     b'HTTP/1.0 200 OK\r\n\r\n{"ok":true}'):
            self.assertEqual(self.parse(wire), {'ok': True})

    def test_rejects_oversized_truncated_compressed_and_redirect_responses(self):
        for wire in (b'HTTP/1.0 200 OK\r\nContent-Length: 1000\r\n\r\n',
                     b'HTTP/1.0 200 OK\r\nContent-Length: 11\r\n\r\n{}',
                     b'HTTP/1.0 200 OK\r\nContent-Encoding: gzip\r\n\r\n',
                     b'HTTP/1.0 302 Found\r\nLocation: http://example.org\r\n\r\n',
                     b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nFFFF\r\n',
                     b'HTTP/1.0 200 OK\r\n\r\n' + b'x' * 101,
                     b'HTTP/1.0 200 OK\r\nX: ' + b'x' * 1025):
            with self.assertRaises(OSError): self.parse(wire)

    def test_context_requires_ca_and_hostname_validation(self):
        context = http.verified_context(str(CA))
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.cert_store_stats()['x509_ca'], 1)
        with self.assertRaises(TLSFailure): http.verified_context('/missing-certificate.der')

    def test_no_http_or_header_injection(self):
        for url in ('http://example.com/test', 'https://example.com/test\r\nBad: yes',
                    'https://name@evil.com/test'):
            with self.assertRaises((TLSFailure, ValueError)):
                http.get_json(url)

    def test_unknown_clock_fails_before_connecting(self):
        with patch.object(http.time, 'gmtime', return_value=(2000,1,1,0,0,0)), patch.object(http.socket, 'getaddrinfo') as dns:
            with self.assertRaises(ClockUnset): http.get_json('https://example.com/a')
            dns.assert_not_called()

    def test_socket_closed_after_success_or_rejected_certificate(self):
        for reject in (False, True):
            raw = Mock()
            stream = Mock()
            body = io.BytesIO(b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\n{}')
            stream.read.side_effect = body.read
            stream.write.side_effect = len
            context = Mock()
            context.wrap_socket.side_effect = TLSFailure('untrusted') if reject else None
            context.wrap_socket.return_value = stream
            with patch.object(http, 'verified_context', return_value=context), patch.object(http.socket,'getaddrinfo',return_value=[(2,1,0,'',('127.0.0.1',443))]), patch.object(http.socket,'socket',return_value=raw):
                if reject:
                    with self.assertRaises(TLSFailure): http.get_json('https://services.swpc.noaa.gov/test')
                    stream.write.assert_not_called()
                else:
                    self.assertEqual(http.get_json('https://services.swpc.noaa.gov/test'), {})
                    stream.close.assert_called_once()
                raw.close.assert_called_once()
                context.wrap_socket.assert_called_once_with(raw,server_hostname='services.swpc.noaa.gov')

    def test_expired_total_budget_aborts_even_if_reads_return_data(self):
        with patch.object(http, 'milliseconds', side_effect=(0, 9000)):
            raw = Mock()
            with patch.object(http, 'verified_context'), patch.object(http.socket,'getaddrinfo',return_value=[(2,1,0,'',('127.0.0.1',443))]), patch.object(http.socket,'socket',return_value=raw):
                with self.assertRaisesRegex(OSError,'deadline'): http.get_json('https://example.com/a',timeout=8)
                raw.close.assert_called_once()
