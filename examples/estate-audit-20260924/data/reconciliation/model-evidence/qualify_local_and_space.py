"""Bounded reproducible witnesses; no training or release eligibility implied."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, sys, subprocess
import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work/model-resolution'
OUT = ROOT / 'outputs/model-resolution'
SOURCE = WORK / 'repos/szl-khipu'
sys.path.insert(0, str(SOURCE))
from szl_khipu.train import mini_embed, moons, receipt_agent, tiny_khipu

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
record = {'schema':'szl.model-local-runtime-witness/v1', 'observed_at':datetime.now(timezone.utc).isoformat(),
          'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip(),
          'evidence_label':'LOCAL_SYNTHETIC_AND_PUBLIC_RUNTIME_WITNESS', 'production_qualified':False,
          'training_reproduced':False, 'nanos':[], 'runtime':[]}
provider = json.loads((WORK/'small_artifact_bytes.json').read_text())
provider_rows = provider['files']
for name, fname in [('MiniEmbed-Nano','mini_embed.npz'),('Moons-Nano','moons.npz'),('ReceiptAgent-Nano','receipt_agent.npz'),('TinyKhipu-Nano','tiny_khipu.npz')]:
    path=WORK/'hf'/name/fname
    receipt=json.loads((path.parent/'TRAINING_RECEIPT.json').read_text())
    with np.load(path,allow_pickle=False) as z:
        arrays={k:{'shape':list(z[k].shape),'dtype':str(z[k].dtype),'finite':bool(np.isfinite(z[k]).all())} for k in z.files}
    item={'repository':'SZLHOLDINGS/'+name,'artifact':fname,'sha256':sha(path),'bytes':path.stat().st_size,
          'training_receipt_hash_matches':receipt['artifacts'][fname]['sha256']==sha(path),
          'canonical_source_blob_matches':(SOURCE/'artifacts'/fname).exists() and sha(SOURCE/'artifacts'/fname)==sha(path),
          'arrays':arrays, 'training_verified':False, 'production_qualified':False}
    matching=[r for r in provider_rows if r['repository']==item['repository'] and r['path']==fname]
    assert len(matching)==1 and matching[0]['sha256']==sha(path) and matching[0]['provider_byte_identity_verified']
    item['provider_revision']=matching[0]['revision']; item['provider_byte_identity_verified']=True
    if name=='MiniEmbed-Nano':
        v=mini_embed.load_npz(str(path)).embed('bounded synthetic witness')
        item['inference']={'vector_shape':list(v.shape),'norm':float(np.linalg.norm(v)),'finite':bool(np.isfinite(v).all())}
    elif name=='Moons-Nano':
        w=moons.load_npz(str(path)); x,y=moons.two_moons(n=200,seed=20260925)
        item['inference']={'synthetic_seed':20260925,'samples':len(y),'accuracy':float(moons.accuracy(w,x,y)),'predictions_shape':list(moons.predict(w,x).shape)}
    elif name=='ReceiptAgent-Nano':
        w=receipt_agent.load_npz(str(path)); x,y=receipt_agent.synth_features(n=400,seed=20260925)
        valid=np.zeros(24); valid[[0,2,3,4,5,7,9,13]]=1
        cases=[]
        for i in range(24):
            for bad in (np.nan,np.inf,-np.inf):
                v=valid.copy();v[i]=bad;cases.append(receipt_agent.decide(v,w)['decision']=='BLOCKED')
        item['inference']={'synthetic_seed':20260925,'samples':len(y),'advisory_agreement':float(receipt_agent.agree(w,x,y)),
                           'valid_decision':receipt_agent.decide(valid,w)['decision'],'nonfinite_cases':len(cases),'nonfinite_blocked':sum(cases)}
        assert all(cases)
    else:
        w=tiny_khipu.load_npz(str(path)); d=tiny_khipu.synth_curriculum(n=80,seed=20260925)
        item['inference']={'synthetic_seed':20260925,'samples':len(d),'metrics':tiny_khipu.evaluate(w,d)}
    item['load_and_inference_verified']=True
    record['nanos'].append(item)

base='https://szlholdings-szl-khipu.hf.space'
for path,body in [('/api/build-info',None),('/.well-known/szl-source.json',None),('/healthz',None),('/api/infer',{'kind':'receipt_agent'}),('/api/infer',{'kind':'receipt_agent','hard_deny':True}),('/api/infer',{'kind':'receipt_agent','break_chain':True})]:
    r=requests.get(base+path,timeout=20,allow_redirects=False) if body is None else requests.post(base+path,json=body,timeout=20,allow_redirects=False)
    try: data=r.json()
    except ValueError: data={'body_sha256':hashlib.sha256(r.content).hexdigest()}
    record['runtime'].append({'url':base+path,'request':body,'status_code':r.status_code,'body':data,'body_sha256':hashlib.sha256(r.content).hexdigest()})
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'nano-and-space-witness.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(json.dumps({'nanos':len(record['nanos']),'runtime':[(r['url'],r['status_code'],r['body'].get('decision')) for r in record['runtime']]}))
