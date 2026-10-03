#!/usr/bin/env python3
"""One bounded Health Auto Export -> private workbench sync, run by launchd."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


class SyncError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def private_json(path):
    path = Path(path).expanduser()
    if path.stat().st_mode & 0o077:
        raise SyncError('private_config_permissions')
    return json.loads(path.read_text())


def sleep_payload(response):
    if response.get('error') or response.get('result', {}).get('isError'):
        raise SyncError('source_rejected')
    try:
        value = json.loads(next(x['text'] for x in response['result']['content'] if x.get('type') == 'text'))
        metrics = [x for x in value['data']['metrics'] if x.get('name') == 'sleep_analysis' and x.get('data')]
        return {'data': {'metrics': metrics}}
    except (KeyError, TypeError, ValueError, StopIteration):
        raise SyncError('invalid_source_data') from None


def read_sleep(headers):
    local = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    headers = {**headers, 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    def call(payload):
        request = urllib.request.Request('http://127.0.0.1:9000/mcp', json.dumps(payload).encode(), headers)
        try:
            with local.open(request, timeout=15) as response:
                if response.headers.get('Mcp-Session-Id'):
                    headers['Mcp-Session-Id'] = response.headers['Mcp-Session-Id']
                body = response.read().decode()
                if not body:
                    return {}
                if response.headers.get_content_type() == 'text/event-stream':
                    body = next(line[5:].strip() for line in body.splitlines() if line.startswith('data:'))
                return json.loads(body)
        except urllib.error.HTTPError:
            raise SyncError('source_rejected') from None
        except OSError:
            raise SyncError('source_unavailable') from None
        except (ValueError, StopIteration):
            raise SyncError('invalid_source_data') from None
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    try:
        init = call({'jsonrpc':'2.0','id':1,'method':'initialize','params':{
            'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'zelong-health-sync','version':'1.0'}}})
        if init.get('error'):
            raise SyncError('source_rejected')
        call({'jsonrpc':'2.0','method':'notifications/initialized'})
        result = call({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_health_metrics','arguments':{
            'metrics':'sleep_analysis','start':(now-dt.timedelta(days=7)).isoformat(),
            'end':(now+dt.timedelta(days=1)).isoformat(),'interval':'days','aggregate':True}}})
        return sleep_payload(result)
    finally:
        if headers.get('Mcp-Session-Id'):
            try:
                with local.open(urllib.request.Request('http://127.0.0.1:9000/mcp',headers=headers,method='DELETE'),timeout=3):
                    pass
            except OSError:
                pass


def send(config, path, body):
    parsed = urllib.parse.urlsplit(config['url'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SyncError('invalid_destination')
    request = urllib.request.Request(config['url'].rstrip('/')+'/api/health/'+path,
        json.dumps(body, ensure_ascii=False).encode(),
        {'Content-Type':'application/json','Authorization':'Bearer '+config['token']})
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=20) as response:
            return json.load(response)
    except (OSError, ValueError):
        raise SyncError('server_unreachable_or_rejected') from None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='~/.config/health-auto-export/workbench.json')
    parser.add_argument('--headers',default='~/.config/health-auto-export/mcp-headers.json')
    parser.add_argument('--interval',type=int,default=900)
    args=parser.parse_args()
    result={'at':dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        config=private_json(args.config)
        if sys.platform=='darwin':
            subprocess.run(['/usr/bin/open','-gj','-a','Health Auto Export'],capture_output=True,timeout=10)
        identity={'sync_source':'mac-bridge','sync_interval':args.interval}
        try:
            payload=read_sleep(private_json(args.headers))
        except SyncError as error:
            code=str(error)
            if code in ('source_rejected','source_unavailable','invalid_source_data'):
                send(config,'sync',{**identity,'status':'error','error':code})
            raise
        if not payload['data']['metrics']:
            send(config,'sync',{**identity,'status':'empty','error':'no_records'})
            result.update(status='empty')
        else:
            receipt=send(config,'import',{**payload,**identity})
            result.update(status='ok',imported=receipt['imported'],changed=receipt['changed'])
        print(json.dumps(result),flush=True)
        return 0
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired,SyncError) as error:
        result.update(status='error',code=str(error) if isinstance(error,SyncError) else type(error).__name__)
        print(json.dumps(result),flush=True)
        return 1


if __name__=='__main__':
    sys.exit(main())
