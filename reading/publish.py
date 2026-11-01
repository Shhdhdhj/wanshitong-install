import argparse,datetime,hashlib,html,json,re,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlparse
ROOT=Path(__file__).resolve().parent
UA='WanshitongReading/1.0 (+https://shhdhdhj.github.io/wanshitong-install/)'
def normalize(text):
 text=html.unescape(text)
 text=re.sub(r'<ref\b[^>]*>.*?</ref>','',text,flags=re.S|re.I)
 text=re.sub(r'\{\{(?:異文|异文|另)\|([^|{}]*)\|[^{}]*\}\}',r'\1',text)
 for _ in range(6):text=re.sub(r'\{\{[^{}]*\}\}','',text)
 text=re.sub(r'<[^>]*>','',text)
 return re.sub(r'[\W_]+','',text,flags=re.U).casefold()
def read_url(url):
 if urlparse(url).hostname not in ['zh.wikisource.org','openstax.org']:raise ValueError('Source host is not approved')
 last=None
 for attempt in range(3):
  try:
   with urlopen(Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/html'}),timeout=25)as r:
    body=r.read(4*1024*1024+1)
    if len(body)>4*1024*1024:raise ValueError('Source exceeds size limit')
    return body.decode('utf-8')
  except Exception as e:last=e;time.sleep(attempt+1)
 raise last
def fetch_source(source):
 if source['type']=='wikisource':
  url='https://zh.wikisource.org/w/api.php?'+urlencode({'action':'query','prop':'revisions','rvprop':'ids|timestamp|content','rvslots':'main','titles':source['page'],'format':'json'})
  data=json.loads(read_url(url));pages=data.get('query',{}).get('pages',{})
  page=next(iter(pages.values()),{});revision=page.get('revisions',[{}])[0]
  text=revision.get('slots',{}).get('main',{}).get('*')
  if not text:raise ValueError('Missing source text: '+source['page'])
  return text,{'revision':str(revision['revid']),'sourceUpdatedAt':revision['timestamp'],'snapshotURL':'https://zh.wikisource.org/w/index.php?oldid='+str(revision['revid'])}
 return read_url(source['url']),{'revision':None,'sourceUpdatedAt':None,'snapshotURL':source['url']}
def choose_index(day,start,total):
 n=(day-start).days
 if n<0:raise ValueError('Recommendation date predates catalog')
 return n%total,n//total+1
def produce(catalog,old,today,fetcher=fetch_source,all_entries=False):
 cards=catalog['cards'];index,cycle=choose_index(today,datetime.date.fromisoformat(catalog['startDate']),len(cards))
 now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
 previous={c['id']:c for c in old.get('cards',[])};result=[];errors=[];fetched={}
 for number,card in enumerate(cards):
  row=dict(card);key=row['source']['url']
  needs=all_entries or number==index or row['id']not in previous or previous[row['id']].get('editedAt')!=row['editedAt']
  if needs:
   try:
    if key not in fetched:fetched[key]=fetcher(row['source'])
    text,proof=fetched[key]
    if normalize(row['original'])not in normalize(text):raise ValueError('Quoted original not found in current source: '+row['id'])
    row['source']={**row['source'],**proof,'verifiedAt':now,'quoteSHA256':hashlib.sha256(row['original'].encode()).hexdigest()}
    result.append(row)
   except Exception as error:
    errors.append(row['id']+': '+str(error))
    if number==index:raise ValueError('Today source verification failed; previous feed must be retained. '+str(error))
    if row['id']in previous:result.append(previous[row['id']])
  else:result.append(previous[row['id']])
 if not any(c['id']==cards[index]['id']for c in result):raise ValueError('No verified daily recommendation')
 return {'schemaVersion':1,'mode':'curated','publishedFor':today.isoformat(),'publishedAt':now,'currentId':cards[index]['id'],'cycle':cycle,'isReview':cycle>1,'libraryNotice':'首批12篇详解按日轮换推荐；原文联网核验。翻译与解读为预先整理内容，不是每天由AI自动新写。后续可扩充内容库。','cards':result,'verificationErrors':errors}
def main():
 p=argparse.ArgumentParser();p.add_argument('--all',action='store_true');p.add_argument('--date');p.add_argument('--output',default=str(ROOT/'daily.json'));args=p.parse_args()
 catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
 target=Path(args.output);old=json.loads(target.read_text(encoding='utf-8'))if target.exists()else{}
 day=datetime.date.fromisoformat(args.date)if args.date else datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
 result=produce(catalog,old,day,all_entries=args.all)
 target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(target)
 print(json.dumps({'publishedFor':result['publishedFor'],'cards':len(result['cards']),'currentId':result['currentId'],'verificationErrors':result['verificationErrors']},ensure_ascii=False))
if __name__=='__main__':main()
