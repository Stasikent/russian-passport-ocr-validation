#!/usr/bin/env python3
"""Conservative, offline OCR passport acceptance baseline. No external dependencies."""
import json,sys,re,datetime,collections,math
FIELDS=('Last_name_ru','First_name_ru','Middle_name_ru','Sex_ru','Birth_date','Birth_place_ru','Issue_date','Issue_organisation_code','Licence_number','Issue_organization_ru')
CHECK_DATE=datetime.date(2026,10,1)
WEIGHTS=(7,3,1)

def checksum(s):
    def val(c):
        if c.isdigit():return int(c)
        if 'A'<=c<='Z':return ord(c)-55
        if c=='<':return 0
        return -1000
    return str(sum(val(c)*WEIGHTS[i%3] for i,c in enumerate(s))%10)

def field_data(doc,k):
    x=doc.get('viz',{}).get(k)
    if not x:return '',0.0,0.0
    lines=x.get('lines') or []
    confs=[float(v) for line in lines for v in (line.get('char_conf') or [])]
    return ' '.join(line.get('text','') for line in lines).strip(),float(x.get('conf',0)),min(confs) if confs else 0.0

def parse_date(s):
    try:return datetime.datetime.strptime(s,'%d.%m.%Y').date()
    except ValueError:return None

def mrz_data(doc):
    lines=(doc.get('mrz') or {}).get('lines') or []
    if len(lines)<2:return None
    a,b=(x.get('text','') for x in lines[:2])
    if len(a)!=44 or len(b)!=44 or not a.startswith('PNRUS'):return None
    return a,b

def mrz_date(s,century=None):
    if not re.fullmatch(r'\d{6}',s):return None
    yy=int(s[:2]); mm=int(s[2:4]); dd=int(s[4:6]); years=([1900+yy,2000+yy] if century is None else [century+yy])
    for year in years:
        try:
            d=datetime.date(year,mm,dd)
            if d<=CHECK_DATE:return d
        except ValueError:pass
    return None

def valid_passport_dates(birth,issue):
    if not birth or not issue or issue>CHECK_DATE or birth>issue:return False
    # Russian internal passports are issued from age 14; at ages 20 and 45 replacement is required.
    age=issue.year-birth.year-((issue.month,issue.day)<(birth.month,birth.day))
    if age<14 or age>110:return False
    return True

# Conservative cross-check; nonstandard transliterations are rejected, never corrected.
MRZ_TRANSLIT=dict(zip('АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЫЬЭЮЯ',
                     'ABVGDEEJZIQKLMNOPRSTUFHC346Y9E78'))
def name_mrz_consistent(values, mrz_line):
    parts=mrz_line[5:].split('<<',1)
    if len(parts)!=2:return False
    components=[parts[0]]+parts[1].split('<')
    for idx,key in enumerate(('Last_name_ru','First_name_ru','Middle_name_ru')):
        if idx>=len(components):return False
        name=values[key].replace(' ','').replace('-','')
        trans=''.join(MRZ_TRANSLIT.get(ch,'?') for ch in name)
        if trans!=components[idx]:return False
    return True

def replacement_screen(birth,issue):
    """Screen for mandatory replacement at ages 20 and 45 (90-day grace)."""
    for age in (20,45):
        try: anniversary=birth.replace(year=birth.year+age)
        except ValueError: anniversary=birth.replace(year=birth.year+age,day=28)
        if issue<anniversary and CHECK_DATE>anniversary+datetime.timedelta(days=90):
            return False
    return True

def inspect(doc,field_conf=0.995,char_conf=0.95,require_mrz=True):
    values={}; low=False
    for k in FIELDS:
        v,c,m=field_data(doc,k);values[k]=v
        if not v or c<field_conf or m<char_conf:low=True
    if low:return None,'low_or_missing'
    if values['Sex_ru'] not in ('МУЖ.','ЖЕН.'):return None,'sex'
    if not re.fullmatch(r'\d{2} \d{2} \d{6}',values['Licence_number']):return None,'number_format'
    if not re.fullmatch(r'\d{3}-\d{3}',values['Issue_organisation_code']):return None,'code_format'
    for k in ('Last_name_ru','First_name_ru','Middle_name_ru'):
        if not re.fullmatch(r'[А-ЯЁ][А-ЯЁ\- ]*',values[k]):return None,'name_charset'
    birth=parse_date(values['Birth_date']);issue=parse_date(values['Issue_date'])
    if not valid_passport_dates(birth,issue):return None,'dates'
    m=mrz_data(doc)
    if require_mrz and not m:return None,'mrz_missing'
    if m:
        a,b=m
        if not b[9].isdigit() or checksum(b[:9])!=b[9]:return None,'mrz_number_checksum'
        if not b[19].isdigit() or checksum(b[13:19])!=b[19]:return None,'mrz_birth_checksum'
        # Check only reliably identified MRZ elements; do not enforce approximate name transliteration.
        serial=values['Licence_number'].replace(' ','')
        if b[:9]!=serial[:3]+serial[4:]:return None,'mrz_number_mismatch'
        if b[13:19]!=birth.strftime('%y%m%d'):return None,'mrz_birth_mismatch'
        if b[20] != ('M' if values['Sex_ru']=='МУЖ.' else 'F'):return None,'mrz_sex_mismatch'
        if not re.fullmatch(r'\d{6}',b[29:35]) or b[29:35]!=issue.strftime('%y%m%d'):return None,'mrz_issue_mismatch'
        if b[35:41]!=values['Issue_organisation_code'].replace('-',''):return None,'mrz_code_mismatch'
    if m and not name_mrz_consistent(values,m[0]):return None,'mrz_name_mismatch'
    if not replacement_screen(birth,issue):return None,'replacement_age'
    return values,'accept'

def run(inp,out,conf=0.995,char=0.95):
    counts=collections.Counter()
    with open(inp,encoding='utf-8') as fi,open(out,'w',encoding='utf-8') as fo:
        for line in fi:
            if not line.strip():continue
            doc=json.loads(line)
            fields,reason=inspect(doc,conf,char)
            ans={'doc_id':doc['doc_id'],'decision':'accept' if fields else 'reject'}
            if fields:ans['fields']=fields
            fo.write(json.dumps(ans,ensure_ascii=False)+'\n');counts[reason]+=1
    print(json.dumps(dict(counts),ensure_ascii=False),file=sys.stderr)
if __name__=='__main__':
    if len(sys.argv)!=3:sys.exit('Usage: python postprocess.py predictions.jsonl answers.jsonl')
    run(sys.argv[1],sys.argv[2])
