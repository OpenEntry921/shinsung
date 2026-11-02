"""Stable IDs: the unified MD timeline and original HTML records remain separate."""
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
from .timeline_links import LEGACY_RELATED

LEGACY_KEYS = tuple(f'E{i:02}' for i in range(1,31))
TIMELINE_KEYS = tuple(f'T{i:02}' for i in range(1,71))
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
        super().__init__();self.entries=[]
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if tag=='article' and data.get('data-key'):
            key=data['data-key']
            self.entries.append(dict(key=key,title=data['data-title'],date=data['data-date'],category=data['data-category'],
                sources=data['data-sources'].split(),legacy=False,uncertain=False,
                related_keys=tuple(old for old,targets in LEGACY_RELATED.items() if key in targets)))


def reading_entries():
    # This file is a protected Django template, never a public static/JSON endpoint.
    source=(Path(__file__).parent/'templates/portal/integrated_case_reading.html').read_text()
    parser=TimelineMetadata();parser.feed(source)
    if tuple(e['key'] for e in parser.entries)!=TIMELINE_KEYS: raise ValueError('통합 사건 01~70의 누락·중복·순서를 확인하세요.')
    return parser.entries


def entries_for(key):
    return legacy_reading_entries() if key in LEGACY_KEYS else reading_entries()
