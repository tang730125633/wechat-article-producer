import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import wellbeing
from health_metrics import timestamp


class SleepDetailChecks(unittest.TestCase):
    def test_real_cross_midnight_segments_are_idempotent_and_replace_corrections(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(wellbeing.library, 'DATA', Path(folder)):
            summary={'date':'2026-10-05','totalSleep':1.75,'core':1,'deep':.75,
                     'sleepStart':'2026-10-04 23:30:00 +0800','sleepEnd':'2026-10-05 01:30:00 +0800'}
            wellbeing.import_sleep({'sync_source':'iphone','data':{'metrics':[{'name':'sleep_analysis','units':'hr','data':[summary]}]}})
            def part(start,end,value):
                return {'startDate':start,'endDate':end,'value':value,'source':'Test Watch'}
            rows=[part('2026-10-04 23:30:00 +0800','2026-10-05 00:30:00 +0800','核心'),
                  part('2026-10-05 00:30:00 +0800','2026-10-05 00:45:00 +0800','清醒'),
                  part('2026-10-05 00:45:00 +0800','2026-10-05 01:30:00 +0800','深度')]
            payload={'sync_source':'iphone-sleep','data':{'metrics':[{'name':'sleep_analysis','units':'hr','data':rows+[rows[0]]}]}}
            with patch('wellbeing.time.time',return_value=1000):
                self.assertEqual(wellbeing.import_sleep(payload)['imported'],3)
            with patch('wellbeing.time.time',return_value=2000):
                self.assertEqual(wellbeing.import_sleep(payload)['changed'],0)
                detail=wellbeing.sleep_day_detail('2026-10-05')
                self.assertEqual(detail['received'],1000)
                self.assertEqual(len(detail['segments']),3)
                self.assertEqual(detail['sleep']['totalSleep'],1.75)
                self.assertEqual(detail['window']['start'],timestamp(summary['sleepStart']))
                rows[2]['startDate']='2026-10-05 00:50:00 +0800'
                self.assertGreater(wellbeing.import_sleep(payload)['changed'],0)
                detail=wellbeing.sleep_day_detail('2026-10-05')
                self.assertEqual(len(detail['segments']),3)
                self.assertEqual(next(r for r in detail['segments'] if r['stage']=='deep')['start'],timestamp(rows[2]['startDate']))
            rows.append(part('2026-10-05 01:00:00 +0800','2026-10-05 00:30:00 +0800','核心'))
            payload['data']['metrics'][0]['data']=rows
            with self.assertRaises(ValueError):wellbeing.import_sleep(payload)
            self.assertEqual(len(wellbeing.sleep_day_detail('2026-10-05')['segments']),3)


if __name__=='__main__':unittest.main()
