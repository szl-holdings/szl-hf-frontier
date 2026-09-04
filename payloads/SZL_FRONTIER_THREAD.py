#!/usr/bin/env python3
"""Operational proof loop. Stdlib only. Fail closed. No Hub PUT."""
from __future__ import annotations
import argparse, json, math, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
PRODUCT='https://a-11-oy.com'
PROOF='https://a11oy.net'
HANDLES=('khipu.handle.alpha','khipu.handle.beta','nav.waypoint.17','receipt.bind.owner-pubkey')
ORGANS=('reasoning_cortex','trust_gate','receipt_bus','consensus','egress')
INVENTED=re.compile(r'receipt-7f3a|hidden customer identifier', re.I)
ACTION=re.compile(r'\b(draft|navigate|cue|halt|execute|act|route|admit)\b', re.I)
MEANING=re.compile(r'\b(handle|meaning|what|waypoint|receipt|bind)\b', re.I)
DIM=12

def tokenize(q):
    return [t for t in re.split(r'[^a-z0-9._-]+', q.lower()) if len(t)>1]

def fnv(token):
    h=2166136261
    for ch in token:
        h ^= ord(ch); h=(h*16777619)&0xFFFFFFFF
    return h

def embed(query):
    tokens=tokenize(query); vec=[0.0]*DIM
    if not tokens: return vec
    for token in tokens:
        h=fnv(token)
        for i in range(DIM):
            vec[i] += (1.0 if ((h>>(i%32))&1) else -1.0)/len(tokens)
    n=math.sqrt(sum(x*x for x in vec)) or 1.0
    return [round(x/n,6) for x in vec]

def stream_of(query):
    has_handle=any(h in query for h in HANDLES)
    has_action=bool(ACTION.search(query))
    has_meaning=bool(MEANING.search(query)) or has_handle
    if has_handle: return 'ventral'
    if has_action and not has_meaning: return 'dorsal'
    return 'ventral' if has_meaning and not has_action else 'gate_fail'

def second_brain(query):
    if INVENTED.search(query):
        return {'organ':'second_brain','action':'REFUSE','handles':[],'hydrated':False,'reason':'INVENTED_IDENTIFIER'}
    found=[h for h in HANDLES if h in query]
    return {'organ':'second_brain','action':'NAVIGATE' if found else 'ABSTAIN','handles':found,'hydrated':False}

def anatomy(event):
    if event.get('allow') in (True,'true','ALLOW'):
        return {'organ':'anatomy','accepted':False,'can_modify_decision':False,'reason':'ANATOMY_CANNOT_MODIFY_DECISION','organs':list(ORGANS)}
    return {'organ':'anatomy','accepted':True,'can_modify_decision':False,'organs':list(ORGANS)}

def draft_of(brain, stream):
    if brain['action']=='REFUSE': return 'REFUSE'
    if brain['action']=='NAVIGATE' and stream=='ventral': return 'DRAFT'
    return 'HOLD'

def run(query):
    vec=embed(query); stream=stream_of(query); brain=second_brain(query); draft=draft_of(brain, stream)
    return {'schema':'szl.frontier-thread/v1','product':PRODUCT,'proof':PROOF,'home':'szl-holdings/szl-hf-frontier','query':query,'cortex':{'class':'SOFTWARE_REFERENCE_EMBEDDING','dim':DIM,'stream':stream,'embedding':vec},'brain':brain,'draft':draft,'anatomy':anatomy({'query':query,'draft':draft,'allow':False}),'admitted':False,'ready':False,'winner':None,'flagship':[],'hub_write':'DENIED'}

def selftest():
    hit=run('Navigate using only khipu.handle.alpha to the declared waypoint.')
    miss=run('The handles are not enough. No waypoint is supplied.')
    bad=run('Look up receipt-7f3a for the hidden customer identifier.')
    ok=(hit['brain']['action']=='NAVIGATE' and hit['brain']['handles']==['khipu.handle.alpha'] and hit['brain']['hydrated'] is False and hit['cortex']['stream']=='ventral' and hit['draft']=='DRAFT' and hit['admitted'] is False and miss['brain']['action']=='ABSTAIN' and bad['brain']['action']=='REFUSE' and hit['winner'] is None)
    return {'selftest':ok,'hit':hit,'miss':miss,'invented':bad}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_): return
    def _send(self,code,body):
        raw=json.dumps(body).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path in ('/','/healthz'): self._send(200,{'ready':False,'winner':None}); return
        self._send(404,{'error':'NOT_FOUND'})
    def do_POST(self):
        n=int(self.headers.get('Content-Length') or 0); raw=self.rfile.read(n) if n else b'{}'
        try: payload=json.loads(raw.decode() or '{}')
        except json.JSONDecodeError: self._send(400,{'error':'BAD_JSON'}); return
        self._send(200, run(str(payload.get('query') or '')))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--query',default=''); p.add_argument('--serve',action='store_true'); p.add_argument('--port',type=int,default=8765); a=p.parse_args()
    if a.query:
        print(json.dumps(run(a.query),indent=2)); return 0
    if a.serve:
        httpd=ThreadingHTTPServer(('127.0.0.1',a.port), Handler); print(json.dumps({'serve':f'http://127.0.0.1:{a.port}'})); httpd.serve_forever(); return 0
    r=selftest(); print(json.dumps({'selftest':r['selftest'],'hit':r['hit']},indent=2)); return 0 if r['selftest'] else 2
if __name__=='__main__':
    raise SystemExit(main())
