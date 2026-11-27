"""Public evidence metadata. Only reviewed, redacted files may use these paths."""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views.decorators.http import require_safe

ESTIMATES = (
    dict(key='estimate-2021', date='2021. 9. 25.', project='임시성전 인테리어', number='581-16-00460', amount='51,890,000원', check='검증 숫자 계산 일치'),
    dict(key='estimate-2023', date='2023. 10. 10.', project='임시성전 철거', number='581-16-00460', amount='12,090,000원', check='검증 숫자 계산 일치'),
    dict(key='estimate-2024', date='2024. 2. 25.', project='4층 개조공사', number='128-03-18446', amount='15,444,000원', check='검증 숫자 계산 불일치'),
)
QUERIES = (
    dict(key='hometax-1280318446', label='견적서 기재 번호', number='128-03-18446', check='불일치', date='2026. 11. 18.', iso_date='2026-11-18'),
    dict(key='hometax-1280318449', label='끝자리 변경 가정 번호', number='128-03-18449', check='일치', date='2026. 11. 17.', iso_date='2026-11-17'),
)

REGISTERED_QUERY = dict(key='hometax-5811600460', label='기존 견적서 기재 번호의 홈택스 조회', number='581-16-00460', date='2026. 11. 18.')


EVIDENCE_DIR = Path(__file__).with_name('business_number_evidence')
EVIDENCE_TYPES = {
    **{f"{row['key']}-{variant}.jpg": 'image/jpeg'
       for row in ESTIMATES for variant in ('redacted', 'detail')},
    **{f"{row['key']}.png": 'image/png' for row in (*QUERIES, REGISTERED_QUERY)},
}


def evidence_url(filename):
    if (EVIDENCE_DIR / filename).is_file():
        return reverse('business_number_evidence', kwargs={'filename': filename})
    return ''


@require_safe
def evidence(request, filename):
    if not settings.SHOW_BUSINESS_NUMBER_CARD or filename not in EVIDENCE_TYPES:
        raise Http404
    try:
        evidence_file = (EVIDENCE_DIR / filename).open('rb')
    except FileNotFoundError as exc:
        raise Http404 from exc
    return FileResponse(evidence_file, content_type=EVIDENCE_TYPES[filename])


def business_number_context():
    estimates = []
    for row in ESTIMATES:
        full = evidence_url(row['key'] + '-redacted.jpg')
        detail = evidence_url(row['key'] + '-detail.jpg') if full else ''
        estimates.append({**row, 'url': full, 'detail_url': detail or full})
    queries = [{**row, 'url': evidence_url(row['key'] + '.png')} for row in QUERIES]
    registered = {**REGISTERED_QUERY, 'url': evidence_url(REGISTERED_QUERY['key'] + '.png')}
    evidence = [*estimates, *queries, registered]
    return dict(estimates=estimates, queries=queries, registered_query=registered,
                connected_count=sum(bool(r['url']) for r in evidence), total_count=len(evidence),
                missing=[r for r in evidence if not r['url']])
