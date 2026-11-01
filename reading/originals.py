"""Daily discovery of public-domain originals. No model/API key or generated interpretation."""
import copy,datetime,hashlib,html,json,re
from pathlib import Path
from urllib.parse import urlencode,quote
from publish import read_url,fetch_source,normalize
ROOT=Path(__file__).resolve().parent
KINDS=['诗词','明代历史','王阳明','禅宗','金刚经','声学 / NVH']
NOTICE='每天联网发现并发布一篇未发布过的原文，按原文内容去重；不自动生成翻译或解读。现有12篇详解保留。来源失败或暂未发现新篇时保留上次内容，不循环冒充新篇。手机仅缓存最近内容，历史去重记录保存在网站任务中。'
def mw(**params):
 return json.loads(read_url('https://zh.wikisource.org/w/api.php?'+urlencode({'format':'json',**params})))
def clean(text):
 text=re.sub(r'<!--.*?-->','',text,flags=re.S)
 text=re.sub(r'<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>','',text,flags=re.S|re.I)
 text=re.sub(r'\{\{(?:異文|异文|另)\|([^|{}]*)\|[^{}]*\}\}',r'\1',text)
 for _ in range(12):text=re.sub(r'\{\{[^{}]*\}\}','',text)
 text=re.sub(r'\[\[(?:Category|分類|分类):[^]]*\]\]','',text,flags=re.I)
 text=re.sub(r'\[\[(?:[^]|]*\|)?([^]|]+)\]\]',r'\1',text)
 text=re.sub(r'-\{([^{}]*)\}-',r'\1',text)
 text=re.sub(r'<[^>]*>','',text)
 text=html.unescape(text).replace("'''","").replace("''","")
 text=re.sub(r'[ \t\u3000]+',' ',text)
 return text.strip()
def digest(text):return hashlib.sha256(normalize(text).encode()).hexdigest()
def prose(raw,limit=1400):
 section='正文';parts=[]
 for piece in re.split(r'(?m)^(={2,6}[^\n]+={2,6})\s*$',raw):
  if re.match(r'^={2,6}',piece):section=clean(piece.strip('=').strip());continue
  for block in re.split(r'\n\s*\n',piece):
   text=clean(block)
   if len(text)<90 or '{{'in text or '}}'in text or '| title'in text or text.startswith(('|','[[','#REDIRECT')):continue
   chunk=''
   for sentence in re.split(r'(?<=[。！？])',text):
    if len(chunk)+len(sentence)>limit:
     if len(chunk)>=90:parts.append((section,chunk.strip()))
     chunk=''
    if len(sentence)>limit:continue
    chunk+=sentence
   if len(chunk)>=90:parts.append((section,chunk.strip()))
 return parts
def author_from(raw):
 m=re.search(r'\|\s*author\s*=\s*([^\n|}]+)',raw)
 return clean(m.group(1)).strip()if m else ''
def wiki_titles(prefix):
 data=mw(action='query',list='allpages',apprefix=prefix,apnamespace=0,apfilterredir='nonredirects',aplimit=500)
 return [p['title']for p in data.get('query',{}).get('allpages',[])]
def source_for(page):
 return {'type':'wikisource','page':page,'url':'https://zh.wikisource.org/wiki/'+quote(page,safe='/'),'label':'维基文库 · 古籍电子转录','license':'古代原文属公有领域；电子转录与页面信息依维基文库许可'}
def make_card(category,title,author,work,original,source,proof,day,now):
 h=digest(original)
 return {'id':'original-'+h[:20],'kind':'original','category':category,'title':title[:180],'author':author or '原文页未明确题署','work':work[:250],'era':'古籍电子转录，具体时代与版本请核对来源'if category!='声学 / NVH'else'OpenStax 现代物理教材','original':original,'translation':[],'sections':[],'editedAt':day.isoformat(),'commentaryAuthor':'原文自动选编','commentaryNotice':'此页仅摘取来源原文，未生成翻译、解读或名家评论。','question':'','minutes':max(1,round(len(original)/350)),'source':{**source,**proof,'verifiedAt':now,'quoteSHA256':hashlib.sha256(original.encode()).hexdigest()},'contentHash':h}
def discover(category,cursors,seen,day,now):
 offset=cursors.get(category,0)
 if category=='诗词':
  links=mw(action='parse',page='唐詩三百首',prop='links')['parse']['links']
  pages=list(dict.fromkeys(p['*']for p in links if p.get('ns')==0 and ':'not in p['*'] and p['*']!='唐詩三百首'))
 elif category=='明代历史':pages=wiki_titles('明史/卷')
 elif category=='王阳明':pages=wiki_titles('傳習錄/')
 elif category=='禅宗':pages=wiki_titles('六祖壇經/')
 elif category=='金刚经':pages=['金剛般若波羅蜜經 (鳩摩羅什)']
 else:
  base='https://openstax.org/books/university-physics-volume-1/pages/'
  landing=read_url(base+'17-2-speed-of-sound')
  names=re.findall(r'(?:/books/university-physics-volume-1/pages/|href=")((?:16|17)-[a-z0-9-]+)',landing)
  pages=list(dict.fromkeys(['17-1-sound','17-2-speed-of-sound','17-3-sound-intensity',*names]))
 if not pages:return None
 # The cursor is a page counter; every page is eventually revisited for newly added content.
 for turn in range(min(8,len(pages))):
  page=pages[(offset+turn)%len(pages)]
  try:
   if category=='声学 / NVH':
    url='https://openstax.org/books/university-physics-volume-1/pages/'+page
    text=landing if page=='17-2-speed-of-sound'else read_url(url)
    candidates=[(page,clean(p))for p in re.findall(r'<p\b[^>]*id="fs-id[^"]*"[^>]*>(.*?)</p>',text,flags=re.S)if '<math'not in p and 180<=len(clean(p))<=1500]
    source={'type':'html','url':url,'label':'OpenStax · University Physics Volume 1','license':'CC BY 4.0；Samuel J. Ling、Jeff Sanny、William Moebs'}
    proof={'revision':None,'sourceUpdatedAt':None,'snapshotURL':url};author='Samuel J. Ling、Jeff Sanny、William Moebs';work='University Physics Volume 1 · '+page
   else:
    source=source_for(page);raw,proof=fetch_source(source)
    if category=='诗词':
     poems=re.findall(r'<poem\b[^>]*>(.*?)</poem>',raw,flags=re.S|re.I)
     candidates=[(page,clean(p))for p in poems if 15<=len(clean(p))<=1800]
     author=author_from(raw);work=page
     if not author:continue
    else:
     candidates=prose(raw)
     author={'明代历史':'张廷玉等奉敕编修（清修《明史》）','王阳明':'王守仁及门人；该段具体题署见原书','禅宗':'传统题慧能说法；具体版本见原文页','金刚经':'鸠摩罗什译'}[category]
     work=page+'（节选）'
   for section,original in candidates:
    h=digest(original)
    if h in seen:continue
    title=(page if category=='诗词'else work+' · '+section)
    card=make_card(category,title,author,work,original,source,proof,day,now)
    # Keep this page until all its passages have been used.
    cursors[category]=(offset+turn)%len(pages)
    return card
  except Exception:
   # Another source/category can still provide a fresh verified passage.
   continue
 cursors[category]=(offset+min(8,len(pages)))%len(pages)
 return None
def produce_originals(catalog,old,state,day,discoverer=discover):
 state=copy.deepcopy(state);state.setdefault('schemaVersion',1);state.setdefault('seen',{});state.setdefault('editions',{});state.setdefault('cursors',{})
 date=day.isoformat()
 if date in state['editions']:
  current=state['editions'][date]
  if any(c['id']==current for c in old.get('cards',[])):
   return {**old,'currentId':current,'publishedFor':date},state
  raise ValueError('Existing edition missing from feed; refusing to republish a duplicate.')
 # Include the twelve old originals in deduplication without pretending they were new daily publications.
 for c in catalog['cards']:state['seen'].setdefault(digest(c['original']),{'id':c['id'],'date':c['editedAt'],'seed':True})
 now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
 start=len(state['editions'])%len(KINDS);card=None
 for n in range(len(KINDS)):
  try:card=discoverer(KINDS[(start+n)%len(KINDS)],state['cursors'],set(state['seen']),day,now)
  except Exception:card=None
  if card:break
 if not card:raise ValueError('No unpublished original available from reachable approved sources; keeping last successful edition.')
 h=card['contentHash']
 if h in state['seen']:raise ValueError('Duplicate original rejected.')
 state['seen'][h]={'id':card['id'],'date':date};state['editions'][date]=card['id']
 annotated=[c for c in old.get('cards',[])if c.get('kind')!='original']
 archive=[c for c in old.get('cards',[])if c.get('kind')=='original'and c['id']!=card['id']]
 feed={'schemaVersion':2,'mode':'daily-originals','publishedFor':date,'publishedAt':now,'currentId':card['id'],'isReview':False,'libraryNotice':NOTICE,'cards':[card,*archive[:47],*annotated],'verificationErrors':[],'totalOriginalsPublished':len(state['editions'])}
 return feed,state
def publish_daily(catalog,target,day):
 state_path=ROOT/'state.json'
 state=json.loads(state_path.read_text(encoding='utf-8'))if state_path.exists()else{}
 old=json.loads(target.read_text(encoding='utf-8'))if target.exists()else{}
 feed,state=produce_originals(catalog,old,state,day)
 for p,value in [(target,feed),(state_path,state)]:
  p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(p)
 print(json.dumps({'publishedFor':feed['publishedFor'],'currentId':feed['currentId'],'newOriginalsTotal':feed['totalOriginalsPublished'],'cachedCards':len(feed['cards'])},ensure_ascii=False))
