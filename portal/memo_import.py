"""Private, conservative extraction. Never promotes a memo to verified evidence."""
import hashlib
import re
import zipfile
from xml.etree import ElementTree
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import MemoImport, ImportCandidate, Case, CaseStatement

TOPICS = {
    '공사 및 건축자금 집행': ('공사','건축자금'),
    '카페 운영과 세금 부담': ('카페','세금'),
    '세무대리인 변경': ('세무대리','세무사'),
    '당회 공개 공지와 임시당회 소집': ('당회','공개 공지'),
    '사역실행위원회 운영': ('사역실행위원회',),
    '제직 임명과 회계 선출': ('제직','회계 선출'),
    '회계 결재 체계 및 별도 계좌': ('결재','계좌'),
    '고소·기소 및 기소장 변경': ('고소','기소'),
    '재항고 결정': ('재항고',),
    '노회 재판국 선고와 후속 절차': ('노회','재판국'),
}
ORIGINALS = {
    '공사 및 건축자금 집행':'공사 계약·견적·변경 계약·지급 증빙·건축자금 결의 회의록',
    '카페 운영과 세금 부담':'카페 운영 약정·수입/비용 기록·세금 고지/신고·부담 주체 확인 자료',
    '세무대리인 변경':'위임 계약·변경 통지·의사결정 기록·업무 인계 자료',
    '당회 공개 공지와 임시당회 소집':'공지 원본·소집 통지·송달/공고 기록·당회 회의록',
    '사역실행위원회 운영':'위원회 구성/운영 규정·위임 근거·회의록·결정 기록',
    '제직 임명과 회계 선출':'임명/선출 관련 결의·회의록·적용 규정·참석/표결 범위 확인 자료 (개인정보 가림)',
    '회계 결재 체계 및 별도 계좌':'회계/결재 규정·계좌 개설 및 관리 권한 결의·결재 기록·출납 증빙 (계좌번호 가림)',
    '고소·기소 및 기소장 변경':'해당 사건별 고소장·공소장·변경 신청/허가·송달 기록·해당 판단 원문',
    '재항고 결정':'각 사건번호별 재항고 결정문 전문·이전 결정·송달 기록·상소/확정 관련 자료',
    '노회 재판국 선고와 후속 절차':'노회 재판국 선고문 전문·주문/이유·사건번호·송달·상소 접수/확정/집행 관련 자료',
}
STRATEGY = re.compile(r'대응\s*전략|행동\s*예측|협상\s*카드|지지세|탈퇴\s*준비|승리\s*목표|협상\s*전략|우리의\s*목표')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def require_private_environment():
    if settings.APP_MODE!='production' or not settings.PRIVATE_STORAGE_CONFIRMED or not settings.REAL_MATERIALS_ENABLED or settings.DATA_DIR==settings.BASE_DIR or settings.BASE_DIR in settings.DATA_DIR.resolve().parents or not all((settings.SMS_API_KEY,settings.SMS_API_SECRET,settings.SMS_SENDER)):
        raise ValidationError('실제 자료 등록은 운영 인증과 저장소 보호를 확인한 별도 운영 환경에서만 가능합니다.')

def validate_docx(file):
    try:
        with zipfile.ZipFile(file) as archive:
            entries=archive.infolist()
            if len(entries)>1000 or sum(x.file_size for x in entries)>30*1024*1024 or 'word/document.xml' not in archive.namelist(): raise ValidationError('DOCX 크기 또는 구조를 확인하세요.')
            if any('vbaProject' in x.filename or x.filename.startswith('word/embeddings/') for x in entries): raise ValidationError('매크로·내장 파일이 있는 문서는 허용하지 않습니다.')
            xml=archive.read('word/document.xml')
            if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper(): raise ValidationError('외부 엔터티는 허용하지 않습니다.')
            ElementTree.fromstring(xml)
            return xml
    except (zipfile.BadZipFile,KeyError,ElementTree.ParseError): raise ValidationError('유효한 DOCX 문서가 아닙니다.')
    finally: file.seek(0)

@transaction.atomic
def extract_candidates(document,actor):
    require_private_environment()
    if not document.internal_memo: raise ValidationError('내부 메모로 지정한 비공개 DOCX를 선택하세요.')
    document.original.open('rb')
    try:
        content=document.original.read()
        if len(content)>10*1024*1024: raise ValidationError('10MB 이하 DOCX만 허용합니다.')
        document.original.seek(0); xml=validate_docx(document.original)
    finally: document.original.close()
    digest=hashlib.sha256(content).hexdigest()
    batch,created=MemoImport.objects.get_or_create(digest=digest,defaults={'document':document,'author':actor})
    if not created: return batch,False
    groups={};excluded=0;unclassified=0;strategy_section=False
    root=ElementTree.fromstring(xml)
    body=root.find(W+'body')
    blocks=[];paragraph_index=0;table_index=0
    for element in list(body) if body is not None else []:
        if element.tag==W+'p':
            paragraph_index+=1
            style=element.find(W+'pPr/'+W+'pStyle')
            style_name=style.get(W+'val','') if style is not None else ''
            blocks.append(('문단 '+str(paragraph_index),''.join(t.text or '' for t in element.iter(W+'t')),style_name.lower().startswith('heading')))
        elif element.tag==W+'tbl':
            table_index+=1
            for row_index,row in enumerate(element.findall(W+'tr'),1):
                cells=[' '.join(''.join(t.text or '' for t in p.iter(W+'t')) for p in cell.findall(W+'p')) for cell in row.findall(W+'tc')]
                blocks.append((f'표 {table_index} 행 {row_index}',' | '.join(cells),False))
    for location,text,heading in blocks:
        text=text.strip()
        if not text: continue
        if heading: strategy_section=bool(STRATEGY.search(text))
        elif STRATEGY.fullmatch(re.sub(r'^[\d.\s]+','',text)): strategy_section=True
        if strategy_section or STRATEGY.search(text): excluded+=1;continue
        matches=[topic for topic,keys in TOPICS.items() if any(key in text for key in keys)]
        if not matches:
            unclassified+=1;continue  # Unclassified content is not automatically copied into an event.
        # Distinct proceeding numbers remain separate; lack of a number requires manual scope review.
        docket=' '.join(re.findall(r'\b\d{4}[가-힣]{1,5}\d+\b',text))
        topic=matches[0]; key=hashlib.sha256((topic+'|'+docket).encode()).hexdigest()
        group=groups.setdefault(key,{'topic':topic,'paragraphs':[],'locations':[],'hints':set(),'dates':[]})
        group['paragraphs'].append(text);group['locations'].append(location)
        for match in re.finditer(r'(\d{4})[년./-]\s*(\d{1,2})(?:월|[./-])(?:\s*(\d{1,2})(?:일)?)?',text):
            year,month,day=match.groups()
            if 1<=int(month)<=12:
                group['dates'].append({'year':int(year),'month':int(month),'day':int(day) if day else None,'precision':'day' if day else 'month','source':location})
        group['hints'].update(re.findall(r'제\s*\d+\s*조(?:\s*제\s*\d+\s*항)?',text))
    for key,group in groups.items():
        ImportCandidate.objects.create(batch=batch,key=key,topic=group['topic'],title=group['topic'],internal_excerpt='\n\n'.join(group['paragraphs']),source_locator=', '.join(group['locations']),required_originals=ORIGINALS[group['topic']]+' · 금액·날짜·인명·사건번호를 원자료와 대조하고 개별 판단 범위를 확인해야 합니다.',article_hints=' / '.join(sorted(group['hints'])),date_candidates=group['dates'])
    batch.excluded_blocks=excluded;batch.unclassified_blocks=unclassified;batch.save(update_fields=['excluded_blocks','unclassified_blocks'])
    return batch,True

@transaction.atomic
def convert_candidate(candidate,actor):
    require_private_environment()
    candidate=ImportCandidate.objects.select_for_update().get(pk=candidate.pk)
    if candidate.case_id: return candidate.case,False
    if candidate.state=='excluded' or not candidate.reviewed or not candidate.neutral_summary.strip(): raise ValidationError('중립 요약과 전략·개인정보 제외 검토가 필요합니다.')
    if STRATEGY.search(candidate.neutral_summary) or STRATEGY.search(candidate.title): raise ValidationError('전략·목표 내용은 교인용 설명에서 제외하세요.')
    case=Case(title=candidate.title,topic=candidate.topic,occurred_precision=candidate.occurred_precision,occurred_on=candidate.occurred_on,occurred_year=candidate.occurred_year,occurred_month=candidate.occurred_month,occurred_until=candidate.occurred_until,period_description=candidate.period_description,author=actor,last_editor=actor,state='draft',materials_as_of=candidate.batch.basis_on,status_as_of=candidate.batch.basis_on,status='내부 메모에 기재된 내용 · 원자료 확인 필요. 기준일 이후 상고 접수·확정·집행 여부는 최근 상태 확인 필요.',additional_materials=candidate.required_originals)
    case.full_clean();case.save()
    CaseStatement.objects.create(case=case,kind='unknown',text=candidate.neutral_summary,source_note=f'내부 메모에 기재된 내용 · 원자료 확인 필요 ({candidate.batch.basis_on}; {candidate.source_locator})')
    candidate.case=case;candidate.state='converted';candidate.save(update_fields=['case','state'])
    return case,True
