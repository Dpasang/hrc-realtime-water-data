import csv,datetime,io,json,pathlib,tempfile,unittest
from unittest.mock import patch
import collector

FIXTURE=pathlib.Path(__file__).parent/'fixtures/current.html'

class CollectorTests(unittest.TestCase):
    def test_selects_realtime_water_table_and_parses_eight_rows(self):
        rows=collector.parse_water_table(FIXTURE.read_text('utf-8'))
        self.assertEqual(len(rows),8)
        self.assertEqual(rows[0]['river'],'淮河')
        self.assertEqual(rows[0]['station'],'息县')
        self.assertEqual(rows[-1]['station'],'杨河滩闸')

    def test_preserves_observation_time_and_missing_flow(self):
        rows=collector.parse_water_table(FIXTURE.read_text('utf-8'))
        zhengyang=next(row for row in rows if row['station']=='正阳关')
        self.assertEqual(zhengyang['observed_at'],'2026-10-27 08:00:00')
        self.assertIsNone(zhengyang['flow_value'])
        self.assertEqual(zhengyang['quality']['flow_value'],'missing')
        self.assertEqual(zhengyang['units'],{'water_level_value':None,'flow_value':None})
        self.assertEqual(zhengyang['unit_status'],'not_stated_on_page')

    def test_mixed_limit_column_is_not_overinterpreted(self):
        rows=collector.parse_water_table(FIXTURE.read_text('utf-8'))
        river=next(row for row in rows if row['station']=='息县')
        lake=next(row for row in rows if row['station']=='蒋坝')
        self.assertEqual(river['limit_value_raw'],'-4.41')
        self.assertEqual(river['limit_value_semantics'],'difference_below_threshold')
        self.assertEqual(lake['limit_value_raw'],'13.6')
        self.assertEqual(lake['limit_value_semantics'],'positive_value_semantics_unconfirmed')

    def test_failed_collection_does_not_replace_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);latest=root/'latest/data.json';latest.parent.mkdir(parents=True)
            latest.write_text(json.dumps({'captured_at':'2026-10-27T17:00:00+08:00'}),encoding='utf-8')
            with self.assertRaises(ValueError):
                collector.collect(root,fetcher=lambda url:b'<html>no table</html>',now=datetime.datetime(2026,10,27,18,tzinfo=collector.TZ))
            self.assertEqual(json.loads(latest.read_text('utf-8'))['captured_at'],'2026-10-27T17:00:00+08:00')
            attempt=json.loads((root/'status/latest_attempt.json').read_text('utf-8'))
            self.assertEqual(attempt['status'],'failed')
            evidence=root/attempt['snapshot_directory']/'raw_evidence.zip'
            self.assertTrue(evidence.exists())

    def test_manifest_records_schedule_and_github_trigger(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
                'os.environ',{'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123456'},clear=False):
            root=pathlib.Path(directory)
            manifest=collector.collect(
                root,
                fetcher=lambda url:FIXTURE.read_bytes(),
                now=datetime.datetime(2026,10,27,17,tzinfo=collector.TZ))
            self.assertEqual(manifest['scheduled_time'],'17:00 Asia/Shanghai')
            self.assertEqual(manifest['trigger'],'workflow_dispatch')
            self.assertEqual(manifest['github_run_id'],'123456')

    def test_clean_projection_has_exact_fields_and_blank_missing_flow(self):
        rows=collector.parse_water_table(FIXTURE.read_text('utf-8'))
        clean=collector.clean_rows(rows)
        expected=['river','station','observed_at','water_level_value','flow_value']
        self.assertEqual(list(clean[0]),expected)
        zhengyang=next(row for row in clean if row['station']=='正阳关')
        self.assertIsNone(zhengyang['flow_value'])
        table=list(csv.DictReader(io.StringIO(collector.clean_csv_bytes(rows).decode('utf-8-sig'))))
        self.assertEqual(list(table[0]),expected)
        self.assertEqual(next(row for row in table if row['station']=='正阳关')['flow_value'],'')

    def test_collection_writes_capture_and_data_latest_clean_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            manifest=collector.collect(
                root,
                fetcher=lambda url:FIXTURE.read_bytes(),
                now=datetime.datetime(2026,10,28,17,tzinfo=collector.TZ))
            capture=root/manifest['snapshot_directory']
            capture_rows=json.loads((capture/'water_clean.json').read_text('utf-8'))
            latest_rows=json.loads((root/'data/latest/water_clean.json').read_text('utf-8'))
            self.assertEqual(capture_rows,latest_rows)
            self.assertTrue((capture/'water_clean.csv').exists())
            self.assertTrue((root/'data/latest/water_clean.csv').exists())

if __name__=='__main__':unittest.main()
