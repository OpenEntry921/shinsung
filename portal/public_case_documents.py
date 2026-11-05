"""Explicitly approved redacted static copies; unrelated private Documents stay private."""
import json
import re
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

APPROVED = {**{f'A{i:02}':f'A{i:02}.pdf' for i in (*range(1,10),11,12)},
            'A11변경':'A11-change.pdf',**{f'B{i:02}':f'B{i:02}.pdf' for i in range(1,9)},
            **{f'C{i:02}':f'C{i:02}.pdf' for i in (1,3,4,5,6)},'C02':'C02.jpg','D01':'D01.pdf','E01':'E01.pdf'}


def catalog(base=None):
    """Return only valid present files plus safe diagnostics (no absolute paths)."""
    base=Path(base or settings.BASE_DIR);valid={};errors=[]
    try:
        rows=json.loads((base/'data/case_documents.json').read_text(encoding='utf-8'))['documents']
        if not isinstance(rows,list): raise ValueError()
        ids=[row.get('id') for row in rows]
        if len(rows)!=28 or len(set(ids))!=28 or set(ids)!=set(APPROVED):
            return {},['catalog: expected exactly the 28 approved unique IDs']
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return {},['catalog: unreadable or invalid schema']
    for row in rows:
        code=row['id'];logical='case-documents/'+APPROVED[code];relative='static/'+logical
        if (row.get('file')!=relative or row.get('url')!='/static/'+logical
                or row.get('status')!='redacted_copy' or not isinstance(row.get('title'),str)
                or type(row.get('bytes')) is not int or row['bytes']<=0
                or type(row.get('pages')) is not int or row['pages']<=0
                or (code=='C02' and row['pages']!=1)):
            errors.append(code+': invalid metadata');continue
        path=base/relative
        try:
            if path.is_symlink() or path.resolve().parent!=base.resolve()/'static/case-documents':raise ValueError()
            if path.stat().st_size!=row['bytes']:raise ValueError()
            with path.open('rb') as stream:magic=stream.read(5)
            if not (magic.startswith(b'%PDF-') if logical.endswith('.pdf') else magic.startswith(b'\xff\xd8\xff')):raise ValueError()
        except (OSError,ValueError):
            errors.append(code+': missing file or size/format mismatch');continue
        valid[code]={**row,'logical':logical}
    if sum(row.get('pages',0) for row in rows if type(row.get('pages')) is int)!=490:
        return {},errors+['catalog: expected 490 pages including image']
    return valid,errors


def page_targets(locator,pages):
    # Keep individual references and range starts; validate every endpoint.
    # Existing suffixes ("이하 첨부 회의록", "특히") remain visible in the original source line.
    group=r'[0-9]+(?:~[0-9]+)?(?:·[0-9]+(?:~[0-9]+)?)*'
    if not re.fullmatch(group+r'쪽(?: 이하 첨부 회의록| 특히 '+group+r'쪽)?',locator):raise ValueError('invalid page notation')
    matches=list(re.finditer(r'([0-9]+)(?:~([0-9]+))?',locator))
    if not matches:raise ValueError('missing page')
    targets=[]
    for match in matches:
        start=int(match[1]);end=int(match[2] or start)
        if not 1<=start<=end<=pages:raise ValueError('out of range page')
        if start not in targets:targets.append(start)
    return targets


def public_links(code,locator=''):
    if code not in APPROVED:return {'public_missing':code=='S01'}
    documents,_=catalog();document=documents.get(code)
    if not document:return {'public_unavailable':True}
    try:
        targets=page_targets(locator,document['pages']) if document['logical'].endswith('.pdf') else [None]
        url=staticfiles_storage.url(document['logical'])
    except (ValueError,OSError):return {'public_unavailable':True}
    return {'public_document':document,'public_links':[{'url':url+(f'#page={n}' if n else ''),'page':n} for n in targets]}
