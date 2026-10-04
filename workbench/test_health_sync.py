import ctypes
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import health_sync as sync


class CacheSyncChecks(unittest.TestCase):
    def fixture(self):
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
        start = dt.datetime.combine(today, dt.time(1), tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp() - sync.APPLE_EPOCH
        def row(offset, hours, stage):
            return {'metric':'Sleep Analysis','unit':'hr','start':start+offset,'end':start+offset+hours*3600,
                    'totalSleep':0 if stage=='awake' else hours,stage:hours,'sources':[{'name':'Test watch'}]}
        return today.isoformat(), {'metric':'Sleep Analysis','sleepTimeZone':'Asia/Shanghai','date':start+22*3600,
                                  'data':[row(0,1,'core'),row(3600,.25,'awake'),row(4500,.5,'deep')]}

    def test_sums_sleep_excludes_awake_and_deduplicates_identical_segments(self):
        day, value=self.fixture()
        value['data'].append(value['data'][0].copy())
        result=sync.summarize_cache(value,day)
        self.assertEqual(result['totalSleep'],1.5)
        self.assertEqual(result['core'],1)
        self.assertEqual(result['deep'],.5)
        self.assertNotIn('rem',result)
        self.assertEqual(result['date'],day)
        self.assertIsNone(sync.summarize_cache({**value,'data':[]},day))

    def test_rejects_wrong_date_units_metric_and_overlapping_stages(self):
        day, value=self.fixture()
        with self.assertRaises(sync.SyncError):sync.summarize_cache(value,'2000-01-01')
        with self.assertRaises(sync.SyncError):sync.summarize_cache({**value,'metric':'Heart Rate'},day)
        value['data'][0]['unit']='min'
        with self.assertRaises(sync.SyncError):sync.summarize_cache(value,day)
        day,value=self.fixture()
        overlap=value['data'][0].copy();overlap.update(start=overlap['start']+100,end=overlap['end']+100)
        value['data'].append(overlap)
        with self.assertRaises(sync.SyncError):sync.summarize_cache(value,day)

    def test_reads_canonical_files_without_network_or_app_start(self):
        day,value=self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            name=day.replace('-','')
            Path(folder,name+'.hae').touch();Path(folder,name+' 2.hae').touch()
            with patch.object(sync,'decode_cache',return_value=value) as decode, patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('must not call MCP')):
                result=sync.read_sleep(folder)
                self.assertEqual(len(result['data']['metrics'][0]['data']),1)
                decode.assert_called_once_with(Path(folder,name+'.hae'))

    @unittest.skipUnless(sys.platform=='darwin','Uses the built-in Apple compression library')
    def test_native_lzfse_roundtrip_and_corrupt_data(self):
        day,value=self.fixture()
        raw=json.dumps(value).encode();lib=ctypes.CDLL('/usr/lib/libcompression.dylib')
        encode=lib.compression_encode_buffer
        encode.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_int]
        encode.restype=ctypes.c_size_t
        out=ctypes.create_string_buffer(len(raw)+65536)
        n=encode(out,len(out),ctypes.create_string_buffer(raw),len(raw),None,0x801)
        self.assertGreater(n,0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder,'sample.hae');path.write_bytes(out.raw[:n])
            self.assertEqual(sync.decode_cache(path),value)
            path.write_bytes(b'broken cache')
            with self.assertRaises(sync.SyncError):sync.decode_cache(path)


if __name__=='__main__':
    unittest.main()
