import base64
import subprocess
import time
import unittest
from unittest import mock

import server


class ServerTests(unittest.TestCase):
    def data_url(self, mime, payload):
        return f"data:{mime};base64," + base64.b64encode(payload).decode()

    def test_decode_png(self):
        mime, filename, payload = server.decode_image(self.data_url("image/png", b"\x89PNG\r\n\x1a\nTEST"))
        self.assertEqual((mime, filename), ("image/png", "article.png"))
        self.assertTrue(payload.startswith(b"\x89PNG"))

    def test_rejects_unsupported_format(self):
        with self.assertRaisesRegex(server.WeChatError, "JPG 或 PNG"):
            server.decode_image(self.data_url("image/gif", b"GIF89a"))

    def test_rejects_non_string_image_data(self):
        with self.assertRaisesRegex(server.WeChatError, "数据格式错误"):
            server.decode_image(123)

    def test_rejects_wrong_signature(self):
        with self.assertRaisesRegex(server.WeChatError, "格式与内容不一致"):
            server.decode_image(self.data_url("image/png", b"not-a-png"))

    def test_rejects_one_megabyte_or_larger(self):
        payload = b"\x89PNG\r\n\x1a\n" + b"0" * (1024 * 1024)
        with self.assertRaisesRegex(server.WeChatError, "小于 1 MB"):
            server.decode_image(self.data_url("image/png", payload))

    def test_multipart_contains_image_and_boundary(self):
        boundary, body = server.multipart_image("image/png", "article.png", b"image-bytes")
        self.assertIn(boundary.encode(), body)
        self.assertIn(b'filename="article.png"', body)
        self.assertIn(b"image-bytes", body)

    @mock.patch("server.subprocess.run")
    def test_keychain_write_is_noninteractive(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        server.keychain_set("appid", "test-value")
        args, kwargs = run.call_args
        self.assertEqual(args[0][-1], "-w")
        self.assertNotIn("test-value", args[0])
        self.assertEqual(kwargs["input"], "test-value\ntest-value\n")
        self.assertTrue(kwargs["start_new_session"])

    def test_origin_is_limited_to_local_workbench(self):
        self.assertTrue(server.allowed_origin(f"http://127.0.0.1:{server.PORT}"))
        self.assertTrue(server.allowed_origin(f"http://localhost:{server.PORT}"))
        self.assertFalse(server.allowed_origin("https://example.com"))

    def test_status_has_workbench_identity(self):
        self.assertEqual(server.APP_ID, "wechat-article-producer-workbench-v2")

    def test_access_token_uses_valid_memory_cache(self):
        previous = server.TOKEN_CACHE.copy()
        credentials = server.hashlib.sha256(b"test-appid\0test-secret").digest()
        server.TOKEN_CACHE.update(value="cached-token", expires_at=time.time() + 60, credentials=credentials)
        try:
            with mock.patch("server.keychain_get", side_effect=["test-appid", "test-secret"]) as keychain_get:
                self.assertEqual(server.access_token(), "cached-token")
                self.assertEqual(keychain_get.call_count, 2)
        finally:
            server.TOKEN_CACHE.update(previous)

    @mock.patch("server.api_json", return_value={"access_token": "new-token", "expires_in": 7200})
    @mock.patch("server.keychain_get", side_effect=["new-appid", "new-secret"])
    def test_access_token_does_not_cross_accounts(self, _keychain_get, api_json):
        previous = server.TOKEN_CACHE.copy()
        server.TOKEN_CACHE.update(value="old-token", expires_at=time.time() + 60, credentials=b"old-account")
        try:
            self.assertEqual(server.access_token(), "new-token")
            api_json.assert_called_once()
        finally:
            server.TOKEN_CACHE.update(previous)

    @mock.patch("server.urllib.request.urlopen")
    def test_wechat_ip_error_is_explained(self, urlopen):
        response = mock.MagicMock()
        response.read.return_value = b'{"errcode":40164,"errmsg":"invalid ip"}'
        urlopen.return_value.__enter__.return_value = response
        with self.assertRaisesRegex(server.WeChatError, "IP.*白名单"):
            server.api_json("https://api.weixin.qq.com/test")

    @mock.patch("server.api_json")
    @mock.patch("server.access_token")
    def test_upload_retries_once_with_fresh_token(self, access_token, api_json):
        access_token.side_effect = ["old-token", "new-token"]
        api_json.side_effect = [server.WeChatError("expired", 40001), {"url": "http://mmbiz.qpic.cn/test"}]
        image = self.data_url("image/png", b"\x89PNG\r\n\x1a\nTEST")
        self.assertEqual(server.upload_image(image), "http://mmbiz.qpic.cn/test")
        self.assertEqual(access_token.call_args_list, [mock.call(force=False), mock.call(force=True)])

    @mock.patch("server.keychain_set")
    @mock.patch("server.getpass.getpass", return_value="new-secret")
    @mock.patch("builtins.input", return_value="new-appid")
    @mock.patch("server.keychain_get", return_value="old-appid")
    def test_configure_can_replace_saved_appid(self, _get, _input, _secret, keychain_set):
        server.configure()
        self.assertEqual(keychain_set.call_args_list, [mock.call("appid", "new-appid"), mock.call("appsecret", "new-secret")])


if __name__ == "__main__":
    unittest.main()
