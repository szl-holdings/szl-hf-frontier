import unittest, json
from massed_canary_harness import redact, MockSSHSession, HarnessError
class T(unittest.TestCase):
    def test_redaction(self):
        line = 'auth Bearer mc_sk_ABCDEFGHIJKLMNOP123 done'
        self.assertNotIn('mc_sk_ABCDEFGHIJKLMNOP123', redact(line))
        self.assertIn('[REDACTED', redact(line))
    def test_timeout(self):
        s = MockSSHSession()
        with self.assertRaises(TimeoutError): s.exec('sleep 5', timeout_s=1)
        self.assertEqual(s.log[-1]['status'], 'TIMEOUT')
    def test_attribution(self):
        s = MockSSHSession()
        s.exec('nvidia-smi')
        self.assertTrue(s.log[-1]['run_id'])
        self.assertEqual(len(set(e['run_id'] for e in s.log)), 1)
    def test_rollback(self):
        s = MockSSHSession()
        before = s.snapshot()
        s.mutate('ollama', 'installed')
        self.assertNotEqual(before, s.snapshot())
        s.state.pop('ollama')
        self.assertTrue(s.rollback_check(before, s.snapshot()))
    def test_mock_only(self):
        with self.assertRaises(HarnessError): MockSSHSession(host='vm.massedcompute.com')
    def test_log_never_carries_secret(self):
        s = MockSSHSession()
        s.exec('export K=hf_abcdefghijklmnop123')
        self.assertNotIn('hf_abcdefghijklmnop123', json.dumps(s.log))
if __name__ == '__main__':
    unittest.main(verbosity=2)
