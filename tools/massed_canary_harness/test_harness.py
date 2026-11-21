import unittest, json
from massed_canary_harness import redact, MockSSHSession, HarnessError
class T(unittest.TestCase):
    def test_redaction(self):
        line = 'auth Bearer mc_sk_ABCDEFGHIJKLMNOP123 done'
        self.assertNotIn('mc_sk_ABCDEFGHIJKLMNOP123', redact(line))
        self.assertIn('[REDACTED', redact(line))
    def test_redaction_bearer_full_alphabet(self):
        # Codex P2 fix: bearer tokens containing +, /, ~, = must redact whole
        line = 'Authorization: Bearer abcdefghij+klmnopqrstuvwxyz0123456789='
        out = redact(line)
        self.assertNotIn('abcdefghij+klmnopqrstuvwxyz0123456789', out)
        self.assertNotIn('klmnopqrstuvwxyz0123456789', out)
        self.assertIn('[REDACTED', out)
    def test_redaction_bearer_special_before_sixteenth(self):
        # special characters occurring before the sixteenth character
        line = 'Authorization: Bearer ab+defghijklm/qrstuv~wxyz0123=='
        out = redact(line)
        self.assertNotIn('ab+defghijklm/qrstuv~wxyz0123', out)
        self.assertNotIn('defghijklm/qrstuv~wxyz0123', out)
        self.assertIn('[REDACTED', out)
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
    def test_log_never_carries_bearer_special_alphabet(self):
        s = MockSSHSession()
        s.exec('Authorization: Bearer abcdefghij+klmnopqrstuvwxyz0123456789= pull image')
        self.assertNotIn('abcdefghij+klmnopqrstuvwxyz0123456789', json.dumps(s.log))
if __name__ == '__main__':
    unittest.main(verbosity=2)
