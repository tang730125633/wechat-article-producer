"""Run with python3 -m unittest discover -s skills/wechat-article-producer/scripts."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import wxwork


class ClientChecks(unittest.TestCase):
    def test_config_and_transport_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'url': 'https://example.com/wechat', 'token': 'private-test-token'}))
            path.chmod(0o644)
            with self.assertRaises(wxwork.Error):
                wxwork.read_config(path)
            path.chmod(0o600)
            client = wxwork.Client(*wxwork.read_config(path))
            self.assertIsNone(wxwork.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))
            path.write_text(json.dumps({'url': 'http://example.com/wechat', 'token': 'x'}))
            with self.assertRaises(wxwork.Error):
                wxwork.read_config(path)
            with patch('urllib.request.OpenerDirector.open', side_effect=TimeoutError('private-test-token')) as opening:
                with self.assertRaisesRegex(wxwork.Error, '勿重复提交') as caught:
                    client.request('articles', {'title': 'a'})
                self.assertNotIn('private-test-token', str(caught.exception))
                self.assertEqual(opening.call_count, 1)

    def test_save_preserves_assets_and_rejects_stale_revision(self):
        client = wxwork.Client('https://example.com/wechat', 'test')
        item = {'id': 'a', 'revision': 3, 'archived': True, 'document': {
            'title': '原标题', 'markdown': '原文', 'author': '作者', 'cover': 'original-cover',
            'images': {'slot': {'src': 'original-image'}}, 'theme': 'paper'}}
        args = argparse.Namespace(command='save', id='a', revision=3, file='-',
            title=None, author=None, byline=None, digest=None, theme=None, cover=None,
            archived=None, source='zelong/test')
        with patch.object(client, 'get', return_value=item), patch.object(client, 'request') as request:
            request.side_effect = lambda path, body: {**body, 'revision': 4}
            with patch('sys.stdin', io.StringIO('新正文')), contextlib.redirect_stderr(io.StringIO()):
                result = wxwork.run(args, client)
            payload = request.call_args.args[1]
            self.assertEqual(payload['document'], {**item['document'], 'markdown': '新正文'})
            self.assertTrue(payload['archived'])
            self.assertEqual(result['revision'], 4)
            request.reset_mock()
            args.revision = 2
            with self.assertRaisesRegex(wxwork.Error, '版本冲突'):
                wxwork.run(args, client)
            request.assert_not_called()

    def test_draft_authorization_and_receipt_conflict_never_resend(self):
        client = wxwork.Client('https://example.com/wechat', 'test')
        args = argparse.Namespace(command='draft', id='a', revision=3, confirm=False,
            request_id='operation-1', source='zelong/test')
        with patch.object(client, 'request') as request:
            with self.assertRaises(wxwork.Error):
                wxwork.run(args, client)
            request.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            args.html = str(Path(directory) / 'body.html')
            Path(args.html).write_text('<p>经审阅的正文</p>')
            args.confirm = True
            item = {'id': 'a', 'revision': 3, 'archived': False,
                    'document': {'title': '文章', 'cover': 'data'}}
            receipt = {'media_id': 'test-receipt', 'verified': True}
            with patch.object(client, 'get', return_value=item), patch.object(client, 'request', side_effect=[receipt, wxwork.Error('版本冲突')]) as request:
                result = wxwork.run(args, client)
                self.assertTrue(result['draft_created'])
                self.assertFalse(result['workbench_saved'])
                self.assertFalse(result['published'])
                self.assertEqual([call.args[0] for call in request.call_args_list], ['wechat/draft', 'articles'])


if __name__ == '__main__':
    unittest.main()
