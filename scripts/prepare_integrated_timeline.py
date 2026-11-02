"""Offline, deterministic MD -> server template conversion. No DB, network or auth changes."""
import argparse
import hashlib
import html
import re
from pathlib import Path

FIELDS = ('날짜','경과','관련 규정','쟁점')
SOURCE_CODE = r'[A-E][0-9]{2}(?:변경)?'


def parse_document(text):
    if '{{' in text or '{%' in text or '{#' in text:
        raise ValueError('원문에 템플릿 구문이 포함돼 있습니다. 수동 검토가 필요합니다.')
    sections = text.split('## 통합 사건 열람\n',1)
    if len(sections)!=2: raise ValueError('통합 사건 열람 절을 확인하세요.')
    timeline = re.split(r'^## ',sections[1],maxsplit=1,flags=re.M)[0]
    matches = list(re.finditer(r'^### ([0-9]{2}) (.+)\n',timeline,re.M))
    if [int(m[1]) for m in matches] != list(range(1,71)):
        raise ValueError('01~70번의 누락·중복·순서를 확인하세요.')
    bibliography = text.split('## 근거 자료 목록\n',1)[1]
    sources = {}
    for match in re.finditer(r'^- \*\*('+SOURCE_CODE+r')\*\*: (.+) — ([0-9]+)쪽\s*$',bibliography,re.M):
        code,filename,pages=match.groups()
        if code in sources: raise ValueError('중복 자료 코드')
        sources[code] = {'filename':filename, 'pages':int(pages)}
    if len(sources)!=28: raise ValueError('근거 자료 목록 28개를 확인하세요.')
    entries=[]
    for i,match in enumerate(matches):
        body=timeline[match.end():matches[i+1].start() if i+1<len(matches) else len(timeline)].strip()
        category=re.search(r'^사건 구분: (.+)$',body,re.M)
        labels=list(re.finditer(r'^\*\*([^\n]+)\*\*: ',body,re.M))
        if not category or [m[1] for m in labels]!=list(FIELDS): raise ValueError('사건 필드 구성을 확인하세요.')
        reference=re.search(r'^근거 자료: (.+)$',body,re.M)
        if not reference: raise ValueError('사건 근거 자료가 없습니다.')
        entry={'key':'T'+match[1], 'number':match[1], 'title':match[2], 'category':category[1]}
        for j,label in enumerate(labels):
            end=labels[j+1].start() if j+1<len(labels) else reference.start()
            entry[FIELDS[j]]=body[label.end():end].strip()
            if not entry[FIELDS[j]]: raise ValueError('빈 필드가 있습니다.')
        entry['references']=reference[1]
        refs=[]
        for part in re.split(r',\s*(?='+SOURCE_CODE+r'\b)',reference[1]):
            ref=re.fullmatch('('+SOURCE_CODE+r')\s+(PDF|JPG)\s+(.+)',part)
            if not ref or ref[1] not in sources: raise ValueError('출처 코드나 형식을 확인하세요.')
            if Path(sources[ref[1]]['filename']).suffix.lower()!='.'+ref[2].lower(): raise ValueError('자료 형식과 목록 불일치')
            numbers=[int(n) for n in re.findall('[0-9]+',ref[3])]
            if not numbers or min(numbers)<1 or max(numbers)>sources[ref[1]]['pages']: raise ValueError('자료 목록의 쪽수 범위 불일치')
            refs.append({'code':ref[1],'locator':ref[3],'kind':ref[2],**sources[ref[1]]})
        entry['source_refs']=refs
        entries.append(entry)
    return entries,sources


def render(entries, digest):
    escape=lambda value: html.escape(value,quote=True)
    lines=['{% load discussion_tags timeline_tags %}', '{# Source MD SHA-256: '+digest+'; original PDFs were not supplied for this implementation. #}']
    for entry in entries:
        key=entry['key'];codes=' '.join(dict.fromkeys(ref['code'] for ref in entry['source_refs']))
        lines += ["{% if selected_key == '"+key+"' %}",
            '<article class="case-group direct-case" id="material-'+key+'" data-key="'+key+'" data-title="'+escape(entry['title'])+'" data-date="'+escape(entry['날짜'])+'" data-category="'+escape(entry['category'])+'" data-sources="'+codes+'">',
            '<h2>'+key+' · '+escape(entry['title'])+'</h2>', '<p class="eyebrow">사건 구분: '+escape(entry['category'])+'</p>']
        for i,field in enumerate(FIELDS):
            lines += ['<section class="reading-area" data-area="'+field+'"><h3>'+('①','②','③','④')[i]+' '+field+'</h3>',
                      '<p data-content="'+field+'">'+escape(entry[field])+'</p>']
            if field=='쟁점':
                lines += ['<h4>근거 자료</h4><p class="source-original">'+escape('근거 자료: '+entry['references'])+'</p>',
                          '<p class="eyebrow">PDF 쪽수는 봉투·표지를 포함해 파일 처음부터 센 쪽수이며 문서 안의 인쇄 쪽수와 다를 수 있습니다.</p>','<ul class="source-list">']
                for ref in entry['source_refs']:
                    lines += ['<li data-source="'+ref['code']+'">'+escape(ref['code']+' · '+Path(ref['filename']).name+' · '+ref['kind']+' '+ref['locator'])+" {% timeline_document '"+ref['code']+"' %}</li>"]
                lines += ['</ul>',"{% timeline_responses '"+key+"' %}"]
            lines += ['</section>']
        lines += ["{% event_discussion '"+key+"' %}",'</article>','{% endif %}']
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=args.source.read_bytes()
    entries,sources=parse_document(data.decode('utf-8'))
    result=render(entries,hashlib.sha256(data).hexdigest())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(result,encoding='utf-8')
    print(f'검증·변환 완료: 사건 {len(entries)}개, 자료 {len(sources)}개. DB 변경 없음. 본문 커밋·업로드는 비공개 확인 후 별도 검토하세요.')

if __name__=='__main__':main()
