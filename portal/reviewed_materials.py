"""Import an externally reviewed, private manifest; source content is never shipped in code."""
import datetime
import hashlib
import json
import re
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.contrib.auth.models import User
from .memo_import import validate_docx, W, STRATEGY
from defusedxml import ElementTree
from .models import (Document, Case, CaseStatement, Article, ArticleCaseLink,
                     ReviewedMaterialImport, RegisteredMaterialCase, Audit)
from .case_services import publication_errors

class ImportRejected(Exception):
    pass

def reject():
    raise ImportRejected('원문·검토 파일·식별자·권한·비공개 저장소 조건을 확인하세요. 자료 내용은 로그에 출력하지 않습니다.')

def read_plan(source_path, plan_path):
    source=Path(source_path).read_bytes();raw=Path(plan_path).read_bytes()
    if len(source)>10*1024*1024 or len(raw)>10*1024*1024: reject()
    import io
    xml=validate_docx(io.BytesIO(source))
    root=ElementTree.fromstring(xml,forbid_dtd=True)
    locations={};section=None
    for index,node in enumerate(root.find(W+'body'),1):
        text=''.join(t.text or '' for t in node.iter(W+'t'))
        if node.tag==W+'p':
            heading=re.match(r'^(\d{1,2})\.\s',text)
            if heading: section=int(heading[1])
            if section in (1,2,3,4,10): locations[f'b{index}']=text
        elif node.tag==W+'tbl' and section in (1,2,3,4,10):
            for n,row in enumerate(node.findall(W+'tr'),1):
                locations[f'b{index}:r{n}']=' | '.join(''.join(t.text or '' for t in cell.iter(W+'t')) for cell in row.findall(W+'tc'))
    plan=json.loads(raw)
    if not plan.get('reviewed') or plan.get('source_sha256')!=hashlib.sha256(source).hexdigest(): reject()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',plan['key']): reject()
    datetime.date.fromisoformat(plan['basis_on'])
    cases=plan['cases'];rules=plan.get('rules',[])
    if not cases or len(cases)>500 or len(rules)>500: reject()
    keys=[item['key'] for item in cases]
    if len(set(keys))!=len(keys) or any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',k) for k in keys): reject()
    for item in cases+rules:
        if not item.get('locations') or any(loc not in locations for loc in item['locations']): reject()
    for rule in rules:
        if not rule['case_keys'] or not set(rule['case_keys'])<=set(keys): reject()
    for case in cases:
        if not set(case.get('related_keys',[]))<=set(keys): reject()
        for statement in case.get('statements',[]):
            if statement['kind'] not in ('unknown','claim','opinion'): reject()
            if statement.get('presentation','summary') not in ('summary','quotation','redacted_quotation'): reject()
            if statement['location'] not in case['locations']: reject()
            if statement.get('presentation')=='quotation' and statement['text'] not in locations[statement['location']]: reject()
    # Manifest has been edited to remove personal identifiers, then attested by its reviewer.
    public=json.dumps(cases+rules,ensure_ascii=False)
    if STRATEGY.search(public) or re.search(r'01[016789][-\s]?\d{3,4}[-\s]?\d{4}|\d{10,}',public): reject()
    return source,plan,hashlib.sha256(raw).hexdigest()

def register(source_path,plan_path,author_name,reviewer_name,apply=False,publish=False,reason=''):
    source,plan,plan_digest=read_plan(source_path,plan_path)
    existing=ReviewedMaterialImport.objects.filter(key=plan['key']).first()
    if ReviewedMaterialImport.objects.filter(source_digest=plan['source_sha256']).exclude(key=plan['key']).exists():
        raise ImportRejected('같은 원문이 다른 등록 식별자로 이미 등록되어 있습니다. 중복 등록하지 않습니다.')
    if existing and (existing.source_digest!=plan['source_sha256'] or existing.plan_digest!=plan_digest):
        raise ImportRejected('같은 등록 식별자의 원문 또는 검토 파일이 변경되었습니다. 기존 자료를 덮어쓰지 않습니다. 관리자 변경·검토 절차를 사용하세요.')
    counts={'cases':len(plan['cases']),'rules':len(plan.get('rules',[])),
            'statements':sum(len(item.get('statements',[])) for item in plan['cases']),
            'create_rules':0 if existing else len(plan.get('rules',[])),
            'create_statements':0 if existing else sum(len(item.get('statements',[])) for item in plan['cases']),
            'create_cases':0 if existing else len(plan['cases']),
            'preserve_cases':existing.records.count() if existing else 0,'update_cases':0,
            'create_documents':0 if existing else 1,'apply':apply,'publish_requested':publish}
    if not apply: return counts
    directory=settings.DATA_DIR.resolve()
    if settings.APP_MODE!='production' or not settings.PRIVATE_STORAGE_CONFIRMED or not settings.REAL_MATERIALS_ENABLED or directory==settings.BASE_DIR.resolve() or settings.BASE_DIR.resolve() in directory.parents or settings.MEDIA_ROOT.resolve()!=directory/'private': reject()
    author=User.objects.get(username=author_name);reviewer=User.objects.get(username=reviewer_name)
    if not all((author.is_active,author.is_staff,reviewer.is_active,reviewer.is_staff)) or author.pk==reviewer.pk or not author.has_perm('portal.add_case') or (publish and (not reviewer.has_perm('portal.publish_case') or not reason.strip())): reject()
    if existing:
        if existing.records.count()!=len(plan['cases']): reject()
        counts['published_cases']=existing.records.filter(case__state='published').count()
        return counts # Never republish a case an administrator edited or withdrew.
    saved_file=None
    try:
        with transaction.atomic():
            doc=Document(title=plan['source_filename'],source=plan['source_title'],acquired_on=datetime.date.today(),written_on=plan.get('written_on'),internal_memo=True,excerpt='관리자 전용 내부 검토 원본. 교인 다운로드 금지.',state='draft')
            doc.original.save('source.docx',ContentFile(source),save=False);saved_file=doc.original
            doc.full_clean();doc.save()
            batch=ReviewedMaterialImport.objects.create(key=plan['key'],source_digest=plan['source_sha256'],plan_digest=plan_digest,document=doc,basis_on=plan['basis_on'],author=author,reviewer=reviewer)
            records={}
            fields=('title','topic','overview','occurred_precision','occurred_on','occurred_year','occurred_month','occurred_until','period_description','claims','unknown','decisions','responses','issues','additional_materials','opinion','status')
            for item in plan['cases']:
                values={k:item[k] for k in fields if k in item}
                case=Case(**values,author=author,last_editor=author,state='draft',materials_as_of=plan['basis_on'],status_as_of=plan['basis_on'])
                case.full_clean();case.save();records[item['key']]=case
                RegisteredMaterialCase.objects.create(batch=batch,key=item['key'],case=case,source_locator=item['source_locator'])
                for position,statement in enumerate(item.get('statements',[])):
                    obj=CaseStatement(case=case,kind=statement['kind'],presentation=statement.get('presentation','summary'),text=statement['text'],source_note=f"{plan['source_filename']} · {statement['source_label']} · {statement['location']}",date_description=case.date_label if statement['location']==item['locations'][0] else '별도 설명·결정일은 원자료 확인 필요',position=position)
                    obj.full_clean();obj.save()
            for rule in plan.get('rules',[]):
                linked=[records[k] for k in rule['case_keys']]
                article=Article(case=linked[0],citation=rule['citation'],document_kind=rule.get('document_kind','constitution'),review_description=rule['description'],review_source=f"{plan['source_filename']} · {rule['source_label']}",relevance=rule['relevance'])
                article.full_clean();article.save()
                for case in linked[1:]:ArticleCaseLink.objects.create(article=article,case=case,relevance=rule['relevance'])
            for item in plan['cases']:
                case=records[item['key']]
                case.related_cases.add(*(records[k] for k in item.get('related_keys',[]) if k in records and k!=item['key']))
                if publish:
                    case.refresh_from_db();case.sources_reviewed=True;case.privacy_reviewed=True
                    case.publication_reason=reason;case.reviewer=reviewer;case.state='published'
                    case.full_clean()
                    if publication_errors(case): reject()
                    case.save()
                    Audit.objects.create(actor=str(reviewer.pk),action='case_publish',target=str(case.pk),reason=reason)
            counts['published_cases']=batch.records.filter(case__state='published').count()
            Audit.objects.create(actor=str(author.pk),action='reviewed_material_import',target=str(batch.pk),reason='별도 편집 파일 검토 후 등록. 원자료 검증과 게시 상태는 별개.')
        return counts
    except BaseException:
        if saved_file: saved_file.storage.delete(saved_file.name)
        raise
