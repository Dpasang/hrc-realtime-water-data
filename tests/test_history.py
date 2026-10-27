import gzip,json,pathlib,tempfile,unittest
import archive,recover_history

FIXTURE=pathlib.Path(__file__).parent/'fixtures/current.html'

class HistoryTests(unittest.TestCase):
    def test_cdx_deduplicates_identical_digests(self):
        payload=json.dumps([['timestamp','original','statuscode','digest'],
                            ['20200101000000','http://www.hrc.gov.cn/swj/','200','same'],
                            ['20200102000000','http://www.hrc.gov.cn/swj/','200','same'],
                            ['20200201000000','http://www.hrc.gov.cn/swj/','200','other']]).encode()
        rows=recover_history.parse_cdx(payload)
        self.assertEqual([row['timestamp'] for row in rows],['20200101000000','20200201000000'])

    def test_recovery_keeps_archive_and_observation_times_separate(self):
        payload=json.dumps([['timestamp','original','statuscode','digest'],
                            ['20261027010000','http://www.hrc.gov.cn/swj/','200','one']]).encode()
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            result=recover_history.recover(root,payload,fetcher=lambda url:FIXTURE.read_bytes())
            self.assertEqual(result['recovered_snapshots'],1)
            record=json.loads(next((root/'history/wayback/recovered').glob('*/water.json')).read_text('utf-8'))[0]
            self.assertEqual(record['observed_at'],'2026-10-27 08:00:00')
            self.assertEqual(record['captured_at'],'2026-10-27T09:00:00+08:00')
            archived=archive.successful_batches(root)
            self.assertEqual(len(archived),1);self.assertEqual(archived[0]['kind'],'historical_wayback')

    def test_snapshot_without_water_table_is_excluded_with_reason(self):
        payload=json.dumps([['timestamp','original','statuscode','digest'],
                            ['20200101000000','http://www.hrc.gov.cn/swj/','200','one']]).encode()
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            result=recover_history.recover(root,payload,fetcher=lambda url:b'<html>news only</html>')
            self.assertEqual(result['recovered_snapshots'],0);self.assertEqual(result['excluded_snapshots'],1)
            summary=json.loads((root/'history/wayback/verified_summary.json').read_text('utf-8'))
            self.assertIn('expected headers',summary['snapshots'][0]['reason'])

    def test_gzip_wayback_response_is_decoded_before_parsing(self):
        payload=json.dumps([['timestamp','original','statuscode','digest'],
                            ['20200315141626','http://www.hrc.gov.cn/swj/','200','one']]).encode()
        with tempfile.TemporaryDirectory() as directory:
            result=recover_history.recover(pathlib.Path(directory),payload,
                                           fetcher=lambda url:gzip.compress(FIXTURE.read_bytes()))
            self.assertEqual(result['recovered_snapshots'],1)

if __name__=='__main__':unittest.main()
