"""Stable IDs: the unified MD timeline and original HTML records remain separate."""
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
from .timeline_links import LEGACY_RELATED
from .timeline_revision import TIMELINE_ORDER, ENTRY_COUNT

LEGACY_KEYS = tuple(f'E{i:02}' for i in range(1,31))
TIMELINE_KEYS = TIMELINE_ORDER
READING_KEYS = LEGACY_KEYS + TIMELINE_KEYS
READING_CHOICES = [(key,key) for key in READING_KEYS]


def legacy_reading_entries():
    source=(Path(__file__).parent/'templates/portal/direct_case_reading.html').read_text()
    entries=[dict(key=k,title=unescape(t),date=unescape(d),uncertain=k in ('E06','E10','E22'),legacy=True,
                  related_keys=LEGACY_RELATED.get(k,()))
             for k,t,d in re.findall(r'id="material-(E\d+)"><h2>E\d+ · (.*?)</h2>\n<section class="reading-area"><h3>① 날짜</h3><p>(.*?)</p>',source)]
    if len(entries)!=30 or {e['key'] for e in entries}!=set(LEGACY_KEYS): raise ValueError('기존 사건 메타데이터를 확인하세요.')
    return entries


class TimelineMetadata(HTMLParser):
    def __init__(self):
        super().__init__();self.entries=[];self.source_code=None;self.source_text=[]
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if tag=='article' and data.get('data-key'):
            key=data['data-key']
            self.entries.append(dict(key=key,number=data['data-number'],title=data['data-title'],date=data['data-date'],category=data['data-category'],
                sources=data['data-sources'].split(),legacy=False,uncertain=False,
                related_keys=tuple(old for old,targets in LEGACY_RELATED.items() if key in targets)))
        if tag=='li' and data.get('data-source') and self.entries:
            self.source_code=data['data-source'];self.source_text=[]
    def handle_data(self,data):
        if self.source_code:self.source_text.append(data)
    def handle_endtag(self,tag):
        if tag=='li' and self.source_code:
            match=re.search(r' · (?:PDF|JPG|2차 정리본) (.*?) \{%', ''.join(self.source_text),re.S)
            if match:
                self.entries[-1].setdefault('source_locators',{}).setdefault(self.source_code,match[1])
                self.entries[-1].setdefault('source_references',[]).append({'code':self.source_code,'locator':match[1]})
            self.source_code=None;self.source_text=[]


def reading_entries():
    # This file is a protected Django template, never a public static/JSON endpoint.
    source=(Path(__file__).parent/'templates/portal/integrated_case_reading.html').read_text()
    parser=TimelineMetadata();parser.feed(source)
    if tuple(e['key'] for e in parser.entries)!=TIMELINE_KEYS: raise ValueError('통합 사건 개정본의 누락·중복·순서를 확인하세요.')
    if [e['number'] for e in parser.entries]!=[f'{i:02}' for i in range(1,ENTRY_COUNT+1)]: raise ValueError('표시 번호를 확인하세요.')
    return parser.entries


def entries_for(key):
    return legacy_reading_entries() if key in LEGACY_KEYS else reading_entries()
