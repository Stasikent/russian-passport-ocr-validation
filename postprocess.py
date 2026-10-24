#!/usr/bin/env python3
"""Baseline + multipass + two field models. Inference requires no labels/internet."""
import argparse,collections,json,sys
from pathlib import Path
import numpy as np
from catboost import CatBoostClassifier
from _passport_rules import inspect
from multipass import flags
from field_features_v029 import field_features,TARGETS

def main():
    ap=argparse.ArgumentParser();ap.add_argument('predictions');ap.add_argument('output');ap.add_argument('--model-dir',default=str(Path(__file__).resolve().parent/'models_v029'));ap.add_argument('--threshold',type=float,default=.05);ap.add_argument('--no-ml',action='store_true');args=ap.parse_args()
    models={}
    if not args.no_ml:
        folder=Path(args.model_dir)
        for k in TARGETS:
            model=CatBoostClassifier();model.load_model(str(folder/(k+'.cbm')));models[k]=model
    counts=collections.Counter();results=[];pending=[]
    with open(args.predictions,encoding='utf8') as f:
        for line in f:
            if not line.strip():continue
            doc=json.loads(line);fields,reason=inspect(doc);ans={'doc_id':doc['doc_id'],'decision':'reject'}
            if fields is None:counts['pass1_reject']+=1
            elif flags(fields):counts['pass2_reject']+=1
            else:
                ans={'doc_id':doc['doc_id'],'decision':'accept','fields':fields};pending.append((len(results),doc));counts['accept']+=1
            results.append(ans)
    if models and pending:
        scores=[]
        for k in TARGETS:
            X=np.asarray([field_features(doc,k) for _,doc in pending],dtype=np.float32)
            scores.append(models[k].predict_proba(X)[:,1])
        risk=np.maximum.reduce(scores)
        for (idx,_),r in zip(pending,risk):
            if r>=args.threshold:
                results[idx]={'doc_id':results[idx]['doc_id'],'decision':'reject'}
                counts['pass3_reject']+=1;counts['accept']-=1
    with open(args.output,'w',encoding='utf8') as f:
        for a in results:f.write(json.dumps(a,ensure_ascii=False)+'\n')
    print(dict(counts),file=sys.stderr)
if __name__=='__main__':main()
