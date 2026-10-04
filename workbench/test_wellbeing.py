import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch
import server
import wellbeing


class WellbeingChecks(unittest.TestCase):
    def test_automatic_check_is_not_a_fake_data_change_and_failures_remain_visible(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(server.library,'DATA',Path(folder)):
            payload={'sync_source':'mac-bridge','sync_interval':900,'data':{'metrics':[
                {'name':'sleep_analysis','units':'hr','data':[{'date':'2026-10-03','totalSleep':6.4}]}]}}
            with patch('wellbeing.time.time',return_value=1000):
                self.assertEqual(wellbeing.import_sleep(payload)['changed'],1)
            with patch('wellbeing.time.time',return_value=2000):
                self.assertEqual(wellbeing.import_sleep(payload)['changed'],0)
                current=wellbeing.health_snapshot()
                self.assertEqual(current['sleep'][0]['received'],1000)
                self.assertEqual(current['sync']['sources'][0]['checked'],2000)
                self.assertEqual(current['sync']['status'],'ok')
            with patch('wellbeing.time.time',return_value=3000):
                wellbeing.report_sync({'sync_source':'mac-bridge','sync_interval':900,'status':'error','error':'source_unavailable'})
                self.assertEqual(wellbeing.health_snapshot()['sync']['status'],'error')
                self.assertEqual(wellbeing.health_snapshot()['sync']['sources'][0]['success'],2000)
            with patch('wellbeing.time.time',return_value=10000):
                self.assertEqual(wellbeing.health_snapshot()['sync']['status'],'delayed')
                self.assertEqual(wellbeing.health_snapshot()['sleep'][0]['totalSleep'],6.4)

    def test_private_routes_upload_scope_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(server.library, 'DATA', Path(folder)), patch.object(server, 'PUBLIC_ORIGIN', 'https://example.com'):
            owner = server.library.owner_key()
            upload = wellbeing.upload_key()
            http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            def request(path, token='', body=None):
                req = urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,
                    None if body is None else json.dumps(body).encode(),
                    {'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(req) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as error:
                    return error.code, json.load(error)
            try:
                payload={'data':{'metrics':[{'name':'sleep_analysis','units':'hr','data':[
                    {'date':'2026-10-03','totalSleep':6.4,'core':4.1,'deep':1,'rem':1.3,'start':'2026-10-03 00:00:00 +0800'}]}]}}
                self.assertEqual(request('/api/wellbeing')[0],401)
                self.assertEqual(request('/api/health')[0],401)
                self.assertEqual(request('/api/health',upload)[0],401)
                self.assertEqual(request('/api/health/import','bad',payload)[0],401)
                self.assertEqual(request('/api/health/import',upload,payload),(200,{'imported':1,'changed':1}))
                self.assertEqual(request('/api/health/import',upload,payload)[0],200)
                self.assertEqual(request('/api/wellbeing',upload)[0],401)
                self.assertEqual(request('/api/articles',upload)[0],401)
                self.assertEqual(request('/api/health/setup',upload)[0],401)
                rpc={'jsonrpc':'2.0','id':1,'method':'tools/list'}
                self.assertEqual(request('/api/health/mcp',upload,rpc)[0],401)
                self.assertEqual(len(request('/api/health/mcp',owner,rpc)[1]['result']['tools']),3)
                self.assertEqual(request('/api/ideas',upload)[0],401)
                self.assertEqual(request('/api/keywords',upload,{'keyword':'灵感'})[0],401)
                self.assertEqual(request('/api/keywords',owner,{'keyword':'先有一个词'})[0],200)
                self.assertEqual(request('/api/ideas',owner)[1]['keywords'][0]['label'],'先有一个词')
                snapshot=request('/api/wellbeing',owner)[1]
                self.assertEqual(len(snapshot['sleep']),1)
                self.assertEqual(snapshot['sleep'][0]['totalSleep'],6.4)
                self.assertNotIn('sleepStart',snapshot['sleep'][0])
                self.assertEqual(request('/api/checkin',owner,{'mood':'tired'})[0],200)
                note={'id':str(uuid.uuid4()),'kind':'idea','text':'一个真实想法'}
                self.assertEqual(request('/api/notes',owner,note)[0],200)
                self.assertEqual(request('/api/notes',owner,note)[0],200)
                self.assertEqual(request('/api/notes',owner,{**note,'text':'不能覆盖'})[0],409)
                self.assertEqual(request('/api/ideas','',{'id':note['id'],'revision':0,'keywords':['创作']})[0],401)
                linked=request('/api/ideas',owner,{'id':note['id'],'revision':0,'keywords':['创作','创作','  长期迭代  '],
                    'source_url':'codex://threads/example','context':'真实场景'})
                self.assertEqual(linked[0],200)
                self.assertEqual(linked[1]['keywords'],['创作','长期迭代'])
                self.assertEqual(request('/api/ideas',owner,{'id':note['id'],'revision':0,'keywords':['过期修改']})[0],409)
                self.assertEqual(request('/api/ideas',owner,{'id':note['id'],'revision':1,'keywords':['创作'],'source_url':'javascript:alert(1)'})[0],400)
                idea=request('/api/ideas',owner)[1]['ideas'][0]
                self.assertEqual(idea['text'],note['text'])
                self.assertEqual(idea['revision'],1)
                self.assertEqual(idea['context'],'真实场景')
                snapshot=request('/api/wellbeing',owner)[1]
                self.assertEqual(len(snapshot['notes']),1)
                self.assertEqual(snapshot['checkins'][0]['mood'],'tired')
                self.assertEqual(server.library.list_articles(),[])
            finally:
                http.shutdown();http.server_close();thread.join()

    def test_bad_batch_is_atomic_and_non_sleep_data_is_not_stored(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(server.library,'DATA',Path(folder)):
            good={'date':'2026-10-03','totalSleep':6.4}
            for bad in ({**good,'totalSleep':float('nan')},{**good,'totalSleep':True},{**good,'date':'invalid'}):
                with self.assertRaises(ValueError):
                    wellbeing.import_sleep({'data':{'metrics':[{'name':'sleep_analysis','units':'hr','data':[good,bad]}]}})
                self.assertEqual(wellbeing.snapshot()['sleep'],[])
            wellbeing.import_sleep({'data':{'metrics':[{'name':'unsupported_metric','units':'count/min','data':[{'value':'private'}]},
                {'name':'sleep_analysis','units':'hr','data':[good]}]}})
            self.assertNotIn('private',json.dumps(wellbeing.snapshot()))

    def test_keywords_can_exist_without_quotes_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(server.library,'DATA',Path(folder)):
            first=wellbeing.save_keyword({'keyword':'  AI 创作  '})
            again=wellbeing.save_keyword({'keyword':'ai 创作'})
            self.assertEqual(first,again)
            self.assertEqual(len(wellbeing.keywords()),1)
            self.assertEqual(wellbeing.ideas(),[])
            self.assertEqual(wellbeing.snapshot()['notes'],[])
            with self.assertRaises(ValueError):wellbeing.save_keyword({'keyword':' '})


if __name__=='__main__':
    unittest.main()
