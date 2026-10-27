import csv,datetime,json,pathlib,tempfile,unittest
import archive,collector

FIXTURE=pathlib.Path(__file__).parent/'fixtures/current.html'

class ArchiveTests(unittest.TestCase):
    def capture(self,root,hour,body=None):
        now=datetime.datetime(2026,10,27,hour,tzinfo=collector.TZ)
        return collector.collect(root,fetcher=lambda url:(body or FIXTURE.read_bytes()),now=now)

    def test_repeated_captures_become_one_station_time_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);self.capture(root,9);self.capture(root,17)
            result=archive.build(root,datetime.datetime(2026,10,27,18,tzinfo=collector.TZ))
            self.assertEqual(result['station_time_records'],8)
            payload=json.loads((root/'data/2026-10/HRC.json').read_text('utf-8'))
            record=next(value[0] for value in payload.values() if value[0]['station']=='息县')
            self.assertEqual(record['source_occurrences'],2)

    def test_conflicting_same_time_values_are_not_averaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);self.capture(root,9)
            changed=FIXTURE.read_text('utf-8').replace('37.09','39.09',1).encode('utf-8')
            self.capture(root,17,changed);archive.build(root)
            payload=json.loads((root/'data/2026-10/HRC.json').read_text('utf-8'))
            record=next(value[0] for value in payload.values() if value[0]['station']=='息县')
            self.assertIsNone(record['water_level_m'])
            self.assertEqual(record['quality']['water_level_m'],'conflict')
            self.assertEqual(record['raw_variants']['water_level_m'],[37.09,39.09])

    def test_observation_month_controls_archive_and_csv_schema_is_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);self.capture(root,17);archive.build(root)
            self.assertTrue((root/'data/2026-10/HRC.json').exists())
            station=next(path for path in (root/'data/2026-10').glob('*.csv') if path.name!='月统计.csv')
            with station.open(encoding='utf-8-sig',newline='') as handle:
                physical=list(csv.reader(handle))
            self.assertTrue(all(len(row)==len(physical[0]) for row in physical[1:]))
            self.assertIn('quality',physical[0]);self.assertIn('raw_variants',physical[0])

    def test_latest_uses_last_successful_capture_and_reports_staleness(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);self.capture(root,9);self.capture(root,17)
            archive.build(root,datetime.datetime(2026,10,30,17,tzinfo=collector.TZ))
            latest=json.loads((root/'latest/data.json').read_text('utf-8'))
            self.assertEqual(latest['captured_at'],'2026-10-27T17:00:00+08:00')
            self.assertFalse(latest['fresh']);self.assertEqual(latest['stale_station_rows'],8)

    def test_month_index_lists_archive_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);self.capture(root,17);archive.build(root)
            with (root/'data/index.csv').open(encoding='utf-8-sig',newline='') as handle:
                rows=list(csv.DictReader(handle))
            self.assertEqual(rows[0]['month'],'2026-10')
            self.assertEqual(rows[0]['station_keys'],'8')
            self.assertEqual(rows[0]['station_time_records'],'8')

if __name__=='__main__':unittest.main()
