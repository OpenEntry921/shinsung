"""Render approved database excerpts without a runtime body file or search UI."""
from django.db.models import Q
from .models import Case, Article

class ReadingUnavailable(Exception):
    pass

def load_reading():
    cases = list(Case.objects.filter(state='published').select_related('source_registration__batch__document').defer('source_registration__batch__document__original_blob').prefetch_related('statements').order_by('pk'))
    if not cases:
        return None
    entries = []
    for case in cases:
        registration = getattr(case, 'source_registration', None)
        source = (f'{registration.batch.document.source} · {registration.batch.document.title} · {registration.source_locator}' if registration else '관리자 검토·게시 자료')
        bounds = case.date_bounds()
        order = (case.occurred_on or bounds[0])
        note = ''
        if not order:
            note = '원문에서 기간 시작을 확정할 수 없어 시계열 순서를 추가 확인해야 합니다.'
        elif case.occurred_precision != 'day' and any(other.pk != case.pk and other.date_bounds()[0] and bounds[0] <= other.date_bounds()[1] and other.date_bounds()[0] <= bounds[1] for other in cases):
            order = None
            note = '원문에 기재된 월·기간이 다른 사건의 날짜와 겹쳐 정확한 선후관계를 확정할 수 없습니다. 기간 표현을 유지하고 원자료를 추가 확인합니다.'
        statements = [{'kind': s.kind, 'presentation': s.presentation, 'text': s.text, 'source': s.source_note} for s in case.statements.all() if s.kind in ('unknown', 'claim', 'opinion')]
        rules = [{'citation': a.citation, 'description': a.review_description, 'source': a.review_source, 'relevance': a.relevance} for a in Article.objects.filter(Q(case=case) | Q(related_cases=case)).distinct() if a.review_description]
        from .case_services import case_context
        general = case_context(case) if registration is None else None
        entries.append(dict(general=general, key=registration.key if registration else f'case-{case.pk}', title=case.title,
                            legacy_ids=[case.pk], date_label='날짜 미확인' if case.occurred_precision=='unknown' else case.date_label, order=order, ordering_note=note,
                            source=source, overview=case.overview, statements=statements, rules=rules,
                            issues=case.issues, responses=case.responses, needed='\n'.join(filter(None, (case.additional_materials, case.unknown))), case=case))
    dated = sorted((e for e in entries if e['order'] is not None), key=lambda e: (e['order'], e['key']))
    uncertain = [e for e in entries if e['order'] is None]
    batch = next((c.source_registration.batch for c in cases if getattr(c, 'source_registration', None)), None)
    return dict(entries=entries, dated_entries=dated, uncertain_entries=uncertain,
                source_title=batch.document.source if batch else '관리자 검토·게시 자료',
                source_filename=batch.document.title if batch else '', basis_on=batch.basis_on if batch else '')
