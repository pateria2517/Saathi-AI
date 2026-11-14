from __future__ import annotations
import argparse, asyncio, hashlib, json, re, sqlite3
from pathlib import Path
from typing import Iterable
from config import settings
from providers import embed_texts

PF_RE=re.compile(r"\b(pf|epf|provident fund|epfo|uan|passbook|epfigms)\b",re.I)
ESIC_RE=re.compile(r"\b(esic|esi|employee state insurance)\b",re.I)
URL_RE=re.compile(r"https?://[^\s)\]>]+",re.I)

def extract(path:Path)->str:
    ext=path.suffix.lower()
    if ext in {'.txt','.md','.csv','.json'}: return path.read_text(encoding='utf-8',errors='ignore')
    if ext in {'.html','.htm'}:
        from html.parser import HTMLParser
        class T(HTMLParser):
            def __init__(self): super().__init__(); self.parts=[]; self.skip=0
            def handle_starttag(self,tag,attrs):
                if tag in {'script','style','noscript'}: self.skip+=1
            def handle_endtag(self,tag):
                if tag in {'script','style','noscript'} and self.skip: self.skip-=1
            def handle_data(self,data):
                if not self.skip: self.parts.append(data)
        p=T();p.feed(path.read_text(encoding='utf-8',errors='ignore'));return '\n'.join(p.parts)
    if ext=='.pdf':
        from pypdf import PdfReader
        return '\n'.join(page.extract_text() or '' for page in PdfReader(str(path)).pages)
    if ext=='.docx':
        from docx import Document
        d=Document(str(path));return '\n'.join(p.text for p in d.paragraphs)
    if ext=='.xlsx':
        from openpyxl import load_workbook
        w=load_workbook(path,read_only=True,data_only=True); out=[]
        for s in w:
            for row in s.iter_rows(values_only=True):
                vals=[str(v) for v in row if v is not None]
                if vals: out.append(' | '.join(vals))
        return '\n'.join(out)
    raise ValueError(f'Unsupported file type: {ext}')

def chunks(text:str,size=1100,overlap=180):
    text=re.sub(r'\s+',' ',text).strip(); out=[]; start=0
    while start<len(text):
        end=min(len(text),start+size)
        if end<len(text):
            cut=text.rfind('. ',start+size//2,end)
            if cut>start: end=cut+1
        part=text[start:end].strip()
        if len(part)>80: out.append(part)
        if end>=len(text): break
        start=max(end-overlap,start+1)
    return out

async def ingest(paths:list[Path], reviewed:bool=False):
    records=[]
    for path in paths:
        text=extract(path)
        for ix,chunk in enumerate(chunks(text)):
            pf=bool(PF_RE.search(chunk)); esic=bool(ESIC_RE.search(chunk))
            if not (pf or esic): continue
            domain='PF' if pf and not esic else 'ESIC' if esic and not pf else 'PF/ESIC'
            urls=URL_RE.findall(chunk)
            did=hashlib.sha256(f'{path.name}:{ix}:{chunk}'.encode()).hexdigest()[:24]
            records.append({'id':did,'source_name':path.name,'chunk_index':ix,'domain':domain,'content':chunk,'source_urls':urls,'review_status':'reviewed_by_admin' if reviewed else 'unverified','verification_date':None})
    Path(settings.database_path).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(settings.database_path) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_chunks (id TEXT PRIMARY KEY, source_name TEXT, chunk_index INTEGER, domain TEXT, content TEXT, source_urls TEXT, review_status TEXT, verification_date TEXT, embedding TEXT, embedding_model TEXT)''')
        for r in records:
            c.execute('INSERT OR REPLACE INTO knowledge_chunks (id,source_name,chunk_index,domain,content,source_urls,review_status,verification_date,embedding,embedding_model) VALUES (?,?,?,?,?,?,?,?,?,?)',(r['id'],r['source_name'],r['chunk_index'],r['domain'],r['content'],json.dumps(r['source_urls']),r['review_status'],r['verification_date'],None,None))
        c.commit()
    if settings.embedding_provider!='none' and settings.embedding_api_key:
        batch=64
        for i in range(0,len(records),batch):
            batch_records=records[i:i+batch]
            try: vectors=await embed_texts([x['content'] for x in batch_records])
            except Exception as e: print('Embedding batch failed:',e);break
            with sqlite3.connect(settings.database_path) as c:
                for r,v in zip(batch_records,vectors): c.execute('UPDATE knowledge_chunks SET embedding=?,embedding_model=? WHERE id=?',(json.dumps(v),settings.embedding_model,r['id']))
                c.commit()
    print(f'Ingested {len(records)} PF/ESIC knowledge chunks from {len(paths)} files.')
    print('Uploaded material remains unverified until reviewed by an authorised HR/policy owner.' if not reviewed else 'Marked reviewed_by_admin; this is an admin assertion, not independent legal verification.')


async def embed_faq_records():
    records=json.loads(Path(settings.knowledge_path).read_text(encoding='utf-8'))
    if isinstance(records,dict): records=records.get('records',[])
    rows=[]
    for r in records:
        q=r.get('question_en','')
        a=r.get('answers',{}).get('en','')
        rows.append((r.get('id'),q+'\n'+a))
    with sqlite3.connect(settings.database_path) as c:
        c.execute('CREATE TABLE IF NOT EXISTS kb_embeddings (faq_id TEXT PRIMARY KEY, vector TEXT NOT NULL, model TEXT NOT NULL)')
    for i in range(0,len(rows),64):
        batch=rows[i:i+64]
        vectors=await embed_texts([x[1] for x in batch])
        with sqlite3.connect(settings.database_path) as c:
            for (fid,_),v in zip(batch,vectors): c.execute('INSERT OR REPLACE INTO kb_embeddings (faq_id,vector,model) VALUES (?,?,?)',(fid,json.dumps(v),settings.embedding_model))
            c.commit()
    print(f'Embedded {len(rows)} FAQ records using {settings.embedding_model}.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('files',nargs='*');ap.add_argument('--reviewed',action='store_true');ap.add_argument('--embed-faqs',action='store_true');args=ap.parse_args()
    if args.files: asyncio.run(ingest([Path(x) for x in args.files],args.reviewed))
    if args.embed_faqs: asyncio.run(embed_faq_records())
    if not args.files and not args.embed_faqs: ap.error('Provide files to ingest or --embed-faqs')
