import pathlib,unittest

ROOT=pathlib.Path(__file__).parents[1]

class AutomationTests(unittest.TestCase):
    def test_daily_schedule_is_beijing_1700_and_pipeline_preserves_failures(self):
        workflow=(ROOT/'.github/workflows/collect.yml').read_text('utf-8')
        self.assertIn("cron: '0 9 * * *'",workflow)
        self.assertIn('continue-on-error: true',workflow)
        self.assertIn('python archive.py',workflow)
        self.assertIn('git add data snapshots latest status history',workflow)

if __name__=='__main__':unittest.main()
