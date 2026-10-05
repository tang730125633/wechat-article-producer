import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wellbeing
import health_mcp
from health_metrics import metric_record, workout_record


class PhoneHealthChecks(unittest.TestCase):
    def test_phone_payload_units_idempotency_and_no_location_storage(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(wellbeing.library,'DATA',Path(folder)):
            payload={'sync_source':'iphone','data':{'metrics':[
                {'name':'step_count','units':'count','data':[{'date':'2026-10-04 00:00:00 +0800','qty':8500}]},
                {'name':'active_energy','units':'kJ','data':[{'date':'2026-10-04','qty':418.4}]},
                {'name':'heart_rate','units':'bpm','data':[{'date':'2026-10-04','Avg':72,'Min':50,'Max':140}]}]}}
            self.assertEqual(wellbeing.import_sleep(payload)['changed'],3)
            self.assertEqual(wellbeing.import_sleep(payload)['changed'],0)
            values={r['name']:r for r in wellbeing.health_snapshot()['metrics']}
            self.assertEqual(values['active_energy']['value'],100)
            self.assertEqual(values['step_count']['value'],8500)
            self.assertEqual(wellbeing.health_snapshot()['sync']['primary'],'iphone')
            workout={'id':'550e8400-e29b-41d4-a716-446655440000','name':'Running',
                'start':'2026-10-04 07:00:00 +0800','end':'2026-10-04 07:30:00 +0800','duration':1700,
                'activeEnergyBurned':{'qty':418.4,'units':'kJ'},'distance':{'qty':1,'units':'mi'},'route':[{'latitude':'private'}]}
            self.assertEqual(wellbeing.import_sleep({'sync_source':'iphone-workouts','data':{'workouts':[workout]}})['changed'],1)
            row=wellbeing.health_snapshot()['workouts'][0]
            self.assertEqual(row['energy_kcal'],100)
            self.assertEqual(row['distance_km'],1.609344)
            self.assertEqual(row['duration_seconds'],1700)
            self.assertNotIn('route',row)
            self.assertEqual(wellbeing.import_sleep({'sync_source':'iphone-workouts','data':{'workouts':[]}})['changed'],0)
            result=health_mcp.handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
                'name':'get_health_history','arguments':{'metric':'step_count','start':'2026-10-04','end':'2026-10-04'}}})
            self.assertFalse(result['result']['isError'])
            self.assertEqual(json.loads(result['result']['content'][0]['text'])['records'][0]['value'],8500)

    def test_bad_quantities_and_dates_are_rejected(self):
        with self.assertRaises(ValueError):metric_record('step_count','count',{'date':'2026-10-04','qty':float('nan')})
        with self.assertRaises(ValueError):metric_record('heart_rate','bpm',{'date':'2026-10-04','Avg':72,'Min':100,'Max':120})
        with self.assertRaises(ValueError):metric_record('active_energy','wrong',{'date':'2026-10-04','qty':5})
        self.assertEqual(health_mcp.handle({'jsonrpc':'2.0','id':1,'method':'tools/list'})['result']['tools'][0]['annotations']['readOnlyHint'],True)
        self.assertIsNone(health_mcp.handle({'jsonrpc':'2.0','method':'notifications/initialized'}))


if __name__=='__main__':unittest.main()
