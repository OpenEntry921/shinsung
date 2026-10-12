from django.db.models import Q
from .models import Article, Document, Case

def case_context(case,preview=False):
    articles=Article.objects.filter(Q(case=case)|Q(related_cases=case)).distinct()
    for article in articles:
        application=article if article.case_id==case.pk else article.case_applications.filter(case=case).first()
        article.case_applicability=application.get_applicability_status_display() if application else '확인 중'
        article.case_applicability_reason=application.applicability_reason if application else ''
        article.case_relevance=application.relevance if application else ''
        article.case_current_difference=application.current_difference if application else ''
    links=case.evidence_links.select_related('document')
    documents=Document.objects.filter(Q(case=case)|Q(case_links__case=case),internal_memo=False).distinct()
    if not preview: documents=documents.filter(state='published',redaction_checked=True).exclude(reading='')
    public_ids=set(documents.values_list('pk',flat=True))
    if not preview: links=links.filter(document_id__in=public_ids)
    statements=case.statements.select_related('evidence__document','decision').prefetch_related('supporting_evidence__document')
    # Render unverified or invalidated statements as unknown even before an admin corrects metadata.
    for item in statements:
        item.visible_evidence=item.evidence if item.evidence and (preview or item.evidence.document_id in public_ids) else None
        item.visible_supporting_evidence=[link for link in item.supporting_evidence.all() if preview or link.document_id in public_ids]
        item.display_kind=item.get_kind_display()
        item.decision_fact_confirmed=False
        if item.kind in ('fact','decision_fact'):
            evidence=item.evidence
            if not evidence or not evidence.checked or not evidence.document.original_checked or evidence.document.internal_memo or (item.kind=='decision_fact' and (not item.decision or not item.decision.source_confirmed)):
                item.display_kind='미확인 · 원자료 재확인 필요'
            elif item.kind=='decision_fact': item.decision_fact_confirmed=True
    from django.db.models import F
    decisions=case.official_decisions.select_related('document').order_by(F('decided_on').asc(nulls_last=True),'pk')
    for decision in decisions:
        decision.visible_document=preview or decision.document_id in public_ids
    warnings=[]
    if preview:
        import re
        for item in statements:
            if item.kind in ('claim','unknown','opinion') and re.search(r'확정|무죄|유죄|승소|패소',item.text): warnings.append(f'설명 #{item.pk}: 미검증·주장·의견에 결론 표현이 있습니다. 인용과 판단 범위를 점검하세요.')
        if case.facts or case.decisions: warnings.append('기존 자유 기재 사실·결정은 분류와 원자료 연결을 재확인하세요.')
        if any(not article.source_confirmed for article in articles): warnings.append('확인 중인 조문은 본문을 노출하지 않으며 개정·당시 적용 정보를 별도로 검증해야 합니다.')
        if case.materials_as_of and any(doc.acquired_on>case.materials_as_of for doc in documents): warnings.append('자료 기준일보다 나중에 확보한 문서가 있습니다. 기준일을 확인하세요.')
    return {'case':case,'articles':articles,'documents':documents,'evidence_links':links,'statements':statements,'event_statements':[item for item in statements if item.kind!='opinion'],'opinion_statements':[item for item in statements if item.kind=='opinion'],'decisions':decisions,'preview':preview,'review_warnings':warnings,'review_errors':publication_errors(case) if preview else [],'related_cases':case.related_cases.all() if preview else case.related_cases.filter(state='published')}

def publication_errors(case):
    errors=[]
    if not case.sources_reviewed: errors.append('출처와 근거 없는 확정 표현을 검토하세요.')
    if not case.privacy_reviewed: errors.append('본문·열람본의 개인정보 가림을 확인하세요.')
    if not case.publication_reason.strip(): errors.append('검토·승인 사유를 기록하세요.')
    for statement in case.statements.all():
        try: statement.full_clean()
        except __import__('django').core.exceptions.ValidationError: errors.append('설명 분류·원자료·해당 결정의 연결을 재확인하세요.')
    for article in Article.objects.filter(Q(case=case)|Q(related_cases=case)).distinct():
        if article.verified or article.applicability_status=='applicable':
            try: article.full_clean()
            except __import__('django').core.exceptions.ValidationError: errors.append('조문 원문·개정 정보·사건 당시 적용 검증을 다시 확인하세요.')
    for link in case.article_links.filter(applicability_status='applicable'):
        try: link.full_clean()
        except __import__('django').core.exceptions.ValidationError: errors.append('공유 조문의 이 사건 당시 적용 근거를 별도로 확인하세요.')
    for decision in case.official_decisions.filter(verified=True):
        try: decision.full_clean()
        except __import__('django').core.exceptions.ValidationError: errors.append('공식 결정의 원자료와 판단 범위를 확인하세요.')
    for doc in Document.objects.filter(Q(case=case)|Q(case_links__case=case)).distinct():
        if doc.state=='published' and (doc.internal_memo or not doc.reading or not doc.redaction_checked or not doc.source): errors.append('열람 자료의 출처·가림 검증을 확인하세요.')
    return list(dict.fromkeys(errors))
