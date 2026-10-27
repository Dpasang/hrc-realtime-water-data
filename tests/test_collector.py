import datetime,json,pathlib,tempfile,unittest
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
        self.assertIsNone(zhengyang['flow_m3_s'])
        self.assertEqual(zhengyang['quality']['flow_m3_s'],'missing')

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

if __name__=='__main__':unittest.main()
