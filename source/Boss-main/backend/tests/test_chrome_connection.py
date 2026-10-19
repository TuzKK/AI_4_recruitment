import unittest
from unittest.mock import patch

from rpa.chrome_connection import normalize_endpoint, is_boss_url, find_chrome, browser_mode


class ConnectionTests(unittest.TestCase):
    def test_local_endpoint(self):
        self.assertEqual(normalize_endpoint('http://localhost:9222/'), 'http://127.0.0.1:9222')
        for value in ['http://example.com:9222', 'http://127.0.0.1:9222/path',
                      'http://user@localhost:9222', 'http://localhost:0',
                      'https://localhost:9222', 'http://127.0.0.1:9222/?x=y']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_endpoint(value)

    def test_boss_host_not_substring(self):
        self.assertTrue(is_boss_url('https://www.zhipin.com/web/chat/recommend'))
        self.assertFalse(is_boss_url('https://www.zhipin.com.evil.test/web/chat'))
        self.assertFalse(is_boss_url('https://evil.test/?zhipin.com'))

    def test_windows_runtime(self):
        with patch('rpa.chrome_connection.platform.system', return_value='Windows'):
            self.assertTrue(browser_mode({'rpa_mode': 'mac_app'}))

    def test_invalid_explicit_chrome_reports_error(self):
        with self.assertRaises(FileNotFoundError):
            find_chrome('Z:/missing/chrome.exe')


if __name__ == '__main__':
    unittest.main()
