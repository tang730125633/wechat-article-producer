import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import server
import wellbeing


class SharedDeskLogin(unittest.TestCase):
    def test_existing_login_migrates_and_upload_key_cannot_read_flow(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(server.library, 'DATA', Path(folder)), patch.object(server, 'PUBLIC_ORIGIN', 'https://example.com'), patch.object(server, 'keychain_get', return_value=''):
            cookie = server.library.login(server.library.login_code())
            upload = wellbeing.upload_key()
            http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            def get(path, headers=None):
                request = urllib.request.Request(f'http://127.0.0.1:{http.server_port}'+path, headers=headers or {})
                try:
                    response = urllib.request.urlopen(request)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    return response.status, response.headers, json.load(response)
            try:
                self.assertEqual(get('/api/access')[0], 401)
                self.assertEqual(get('/api/access', {'Authorization': 'Bearer '+upload})[0], 401)
                status, headers, body = get('/api/wechat/status', {'Cookie': 'tang_workbench='+cookie})
                self.assertEqual(status, 200)
                self.assertTrue(body['authenticated'])
                cookies = headers.get_all('Set-Cookie')
                self.assertIn('Path=/; Max-Age=', cookies[0])
                self.assertIn('HttpOnly; Secure; SameSite=Strict;', cookies[0])
                self.assertIn('Path=/wechat/; Max-Age=0', cookies[1])
                self.assertEqual(get('/api/access', {'Cookie': 'tang_workbench='+cookie})[0], 200)
                self.assertEqual(get('/api/access', {'Cookie': 'tang_workbench=invalid'})[0], 401)
            finally:
                http.shutdown(); http.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
