"""szl massed canary harness v0.1 - OFFLINE MOCK ONLY.
Per Kimi handler ruling 2026-11-20: no estate targeting, no network, MEASURED != PASS.
Every operation is in-memory mock; this module must never open a real socket."""
import re, secrets, time, json, hashlib

class HarnessError(Exception): pass

SECRET_PATTERNS = [re.compile(r'sk-[A-Za-z0-9_\-]{16,}'), re.compile(r'mc_sk_[A-Za-z0-9_\-]{16,}'), re.compile(r'hf_[A-Za-z0-9_\-]{16,}'), re.compile(r'Bearer\s+[A-Za-z0-9._\-]{16,}')]

def redact(text):
    for p in SECRET_PATTERNS:
        text = p.sub('[REDACTED:' + str(len(p.pattern)) + '-class]', text)
    return text

class MockSSHSession:
    """Records commands against an in-memory node state; refuses non-mock targets."""
    MOCK_HOSTS = ('localhost',)
    def __init__(self, host='localhost', run_id=None):
        if host not in self.MOCK_HOSTS:
            raise HarnessError('non-mock host refused: ' + redact(str(host)))
        self.host = host
        self.run_id = run_id or hashlib.sha256(secrets.token_hex(16).encode()).hexdigest()[:12]
        self.state = {}
        self.log = []
    def exec(self, cmd, timeout_s=30):
        entry = {'run_id': self.run_id, 'cmd': redact(str(cmd)), 't': round(time.time(), 3)}
        self.log.append(entry)
        if str(cmd).startswith('sleep '):
            d = float(str(cmd).split()[1])
            if d > timeout_s:
                entry['status'] = 'TIMEOUT'
                self.log[-1] = entry
                raise TimeoutError('watchdog fired at ' + str(timeout_s) + 's')
            time.sleep(min(d, 0.2))
        entry['status'] = 'MOCK_OK'
        self.log[-1] = entry
        return 'MOCK_OK ' + redact(str(cmd))
    def snapshot(self):
        return hashlib.sha256(json.dumps(self.state, sort_keys=True).encode()).hexdigest()[:12]
    def mutate(self, k, v):
        self.state[k] = v
    def rollback_check(self, before, after):
        return before == after
