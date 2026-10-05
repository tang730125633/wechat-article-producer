#!/usr/bin/env python3
"""One bounded Health Auto Export -> private workbench sync, run by launchd."""
import argparse
import datetime as dt
import json
from pathlib import Path
import ctypes
import math
from zoneinfo import ZoneInfo
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


SOURCE_DIR = Path.home() / 'Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/AutoSync/HealthMetrics/sleep_analysis'
APPLE_EPOCH = 978307200


def decode_cache(path):
    """Health Auto Export 4.x cache: Apple LZFSE-compressed JSON, not a new API."""
    before = path.stat()
    raw = path.read_bytes()
    if path.stat().st_mtime_ns != before.st_mtime_ns:
        raise SyncError('source_unavailable')
    if len(raw) > 16 * 1024 * 1024 or raw[:4] not in (b'bvx1', b'bvx2', b'bvxn', b'bvx-'):
        raise SyncError('invalid_source_data')
    library = ctypes.CDLL('/usr/lib/libcompression.dylib')
    decode = library.compression_decode_buffer
    decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]
    decode.restype = ctypes.c_size_t
    target = ctypes.create_string_buffer(16 * 1024 * 1024)
    size = decode(target, len(target), ctypes.create_string_buffer(raw), len(raw), None, 0x801)
    if not 0 < size < len(target):
        raise SyncError('invalid_source_data')
    return json.loads(target.raw[:size])


def summarize_cache(value, day):
    if not isinstance(value, dict) or value.get('metric') != 'Sleep Analysis' or not isinstance(value.get('data'), list):
        raise SyncError('invalid_source_data')
    if not value['data']:
        return None
    timezone = ZoneInfo(value.get('sleepTimeZone', 'Asia/Shanghai'))
    if dt.datetime.fromtimestamp(value['date'] + APPLE_EPOCH, timezone).date().isoformat() != day:
        raise SyncError('invalid_source_data')
    fields = ('totalSleep', 'core', 'deep', 'rem')
    unique = {}
    names = set()
    for row in value['data']:
        if not isinstance(row, dict) or row.get('metric') != 'Sleep Analysis' or row.get('unit') != 'hr':
            raise SyncError('invalid_source_data')
        start, end = row['start'], row['end']
        numbers = [start, end, *(row.get(k, 0) for k in fields)]
        if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in numbers):
            raise SyncError('invalid_source_data')
        if end < start or any(not 0 <= row.get(k, 0) <= 24 for k in fields):
            raise SyncError('invalid_source_data')
        total = row.get('totalSleep', 0)
        if total and abs(total * 3600 - (end - start)) > 1:
            raise SyncError('invalid_source_data')
        if sum(row.get(k, 0) for k in fields[1:]) > total + 1e-6:
            raise SyncError('invalid_source_data')
        if total:
            unique[(start, end, *(row.get(k, 0) for k in fields))] = row
            names.update(source['name'] for source in row.get('sources', []) if isinstance(source.get('name'), str))
    rows = sorted(unique.values(), key=lambda r: r['start'])
    if not rows:
        return None
    # Conflicting overlapping stages must be reviewed, never silently double-counted.
    if any(a['end'] > b['start'] + .01 for a, b in zip(rows, rows[1:])):
        raise SyncError('invalid_source_data')
    summary = {'date': day, 'sources': ', '.join(sorted(names))}
    for field in fields:
        if any(field in row for row in rows):
            summary[field] = sum(row.get(field, 0) for row in rows)
    if summary['totalSleep'] > 24:
        raise SyncError('invalid_source_data')
    return summary


def read_sleep(folder=SOURCE_DIR):
    folder = Path(folder).expanduser()
    try:
        folder.stat()
    except OSError as error:
        raise SyncError('source_unavailable') from error
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    records = []
    try:
        for offset in range(7, -1, -1):
            day = now - dt.timedelta(days=offset)
            # Read only canonical yyyyMMdd.hae; iCloud conflict copies are not extra nights.
            path = folder / (day.strftime('%Y%m%d') + '.hae')
            if path.exists():
                record = summarize_cache(decode_cache(path), day.isoformat())
                if record:
                    records.append(record)
    except OSError as error:
        raise SyncError('source_unavailable') from error
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError):
        raise SyncError('invalid_source_data') from None
    return {'data': {'metrics': [{'name': 'sleep_analysis', 'units': 'hr', 'data': records}] if records else []}}


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
    parser.add_argument('--source-dir',default=str(SOURCE_DIR))
    parser.add_argument('--interval',type=int,default=900)
    args=parser.parse_args()
    result={'at':dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        config=private_json(args.config)
        identity={'sync_source':'mac-bridge','sync_interval':args.interval}
        try:
            payload=read_sleep(args.source_dir)
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
    except (OSError,ValueError,KeyError,SyncError) as error:
        result.update(status='error',code=str(error) if isinstance(error,SyncError) else type(error).__name__)
        if isinstance(error.__cause__, OSError):
            result['errno'] = error.__cause__.errno
        print(json.dumps(result),flush=True)
        return 1


if __name__=='__main__':
    sys.exit(main())
