# SPDX-License-Identifier: GPL-3.0-only
import datetime
from pathlib import Path
import ssl
import tempfile
import unittest
import hf_certificate as certificate


class CertificateTests(unittest.TestCase):
    def test_reminder_boundaries_and_unknown_clock(self):
        expires = datetime.datetime.fromisoformat(certificate.CA_EXPIRES_UTC)
        start = expires - datetime.timedelta(days=90)
        self.assertIsNone(certificate.warning((start - datetime.timedelta(seconds=1)).timetuple()))
        self.assertEqual(certificate.warning(start.timetuple()), 'CA EXPIRES 2038-01-17')
        self.assertEqual(certificate.warning((expires - datetime.timedelta(seconds=1)).timetuple()),
                         'CA EXPIRES 2038-01-17')
        for date in (expires, expires + datetime.timedelta(days=365)):
            self.assertEqual(certificate.warning(date.timetuple()), 'CA EXPIRED 2038-01-17')
        self.assertIsNone(certificate.warning((2000, 1, 1, 0, 0, 0)))
        self.assertIsNone(certificate.warning((2026, 9, 28, 0, 0, 0)))

    def test_reminder_matches_bundled_certificate_expiry(self):
        path = Path(__file__).resolve().parents[1] / 'hf_propagation' / 'amazon-root-ca-1.der'
        with tempfile.NamedTemporaryFile(suffix='.pem') as pem:
            pem.write(ssl.DER_cert_to_PEM_cert(path.read_bytes()).encode('ascii'))
            pem.flush()
            actual = ssl._ssl._test_decode_cert(pem.name)['notAfter']
        expiry = datetime.datetime.fromtimestamp(ssl.cert_time_to_seconds(actual), datetime.timezone.utc)
        self.assertEqual(expiry.strftime('%Y-%m-%dT%H:%M:%S'), certificate.CA_EXPIRES_UTC)
