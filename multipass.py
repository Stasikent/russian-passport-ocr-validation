#!/usr/bin/env python3
"""Second-pass conservative validator, pure standard library. Keep baseline unchanged."""
import json,re,sys,collections,hashlib
from pathlib import Path

def norm(s):return ' '.join(str(s or '').upper().split())

def flags(fields):
    b=norm(fields.get('Birth_place_ru','')); o=norm(fields.get('Issue_organization_ru',''))
    f=[]
    # Suspicious unfinished grammatical constructions, not blanket minimum lengths.
    if re.search(r'\b(?:ПО|В|НА|И|ОТ|ПРИ|ДЛЯ)\s*$',o):f.append('org_dangling_end')
    # birth-end prepositions are common legitimate OCR strings; disabled
    if re.search(r'^(?:Р-НА|Р-НЕ|РАЙОНА|РАЙОНЕ|ОБЛ\.?|ОБЛАСТИ|КРАЯ|РОССИИ\b|ПО\b|В\b)',b):f.append('birth_dangling_start')
    if re.search(r'^(?:РОССИИ\b|ПО\b|В\b|ОБЛ\.?|ОБЛАСТИ\b)',o):f.append('org_dangling_start')
    return f

def load(path):return {r['doc_id']:r for r in map(json.loads,open(path,encoding='utf8'))}

def split(doc_id):return 'validation' if int(hashlib.sha256(doc_id.encode()).hexdigest()[:8],16)%5==0 else 'development'

def compare(a,l):
    return all(norm(a['fields'].get(k))==norm(l.get(k)) for k in l)

def audit(answers,labels):
    rows=[]
    for id,a in answers.items():
        if a['decision']!='accept':continue
        wrong=not compare(a,labels[id]); fs=flags(a['fields'])
        rows.append((id,split(id),wrong,fs))
    for group in ('development','validation','all'):
        r=[x for x in rows if group=='all' or x[1]==group]
        base_good=sum(not x[2] for x in r);base_bad=sum(x[2] for x in r)
        kept=[x for x in r if not x[3]]
        good=sum(not x[2] for x in kept);bad=sum(x[2] for x in kept)
        print(f'{group}: baseline good={base_good} bad={base_bad}; pass2 good={good} bad={bad}; prevented_bad={base_bad-bad} lost_good={base_good-good}')
    for flag in ('org_dangling_end','birth_dangling_end','birth_dangling_start','org_dangling_start'):
        r=[x for x in rows if flag in x[3]]
        print(f'{flag}: rejected={len(r)}, bad={sum(x[2] for x in r)}, good={sum(not x[2] for x in r)}')

def run(pred_path,base_path,out_path):
    base=load(base_path);counts=collections.Counter()
    with open(pred_path,encoding='utf8') as fi,open(out_path,'w',encoding='utf8') as fo:
        for line in fi:
            if not line.strip():continue
            d=json.loads(line);id=d['doc_id'];a=base[id].copy()
            if a['decision']=='accept':
                fs=flags(a['fields'])
                if fs:
                    a={'doc_id':id,'decision':'reject'}
                    counts.update(fs)
            fo.write(json.dumps(a,ensure_ascii=False)+'\n')
    print('Second-pass rejection reasons:',dict(counts))

if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='audit':
        audit(load(sys.argv[2]),{k:v['fields'] for k,v in load(sys.argv[3]).items()})
    elif len(sys.argv)==5 and sys.argv[1]=='run':run(*sys.argv[2:])
    else:sys.exit('Usage: python multipass.py audit train_answers.jsonl train_labels.jsonl\n       python multipass.py run predictions.jsonl baseline_answers.jsonl multipass_answers.jsonl')
