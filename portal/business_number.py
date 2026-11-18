"""Public evidence metadata. Only reviewed, redacted files may use these paths."""
from .landing import asset_url

ESTIMATES = (
    dict(key='estimate-2021', date='2021. 9. 25.', project='임시성전 인테리어', number='581-16-00460', amount='51,890,000원', check='검증 숫자 계산 일치'),
    dict(key='estimate-2023', date='2023. 10. 10.', project='임시성전 철거', number='581-16-00460', amount='12,090,000원', check='검증 숫자 계산 일치'),
    dict(key='estimate-2024', date='2024. 2. 25.', project='4층 개조공사', number='128-03-18446', amount='15,444,000원', check='검증 숫자 계산 불일치'),
)
QUERIES = (
    dict(key='hometax-1280318446', label='견적서 기재 번호', number='128-03-18446', check='불일치'),
    dict(key='hometax-1280318449', label='끝자리 변경 가정 번호', number='128-03-18449', check='일치'),
)

REGISTERED_QUERY = dict(key='hometax-5811600460', label='기존 견적서 기재 번호의 홈택스 조회', number='581-16-00460', date='2026. 11. 18.')


def business_number_context():
    estimates = []
    for row in ESTIMATES:
        full = asset_url('portal/business-number/' + row['key'] + '-redacted.jpg')
        detail = asset_url('portal/business-number/' + row['key'] + '-detail.jpg') if full else ''
        estimates.append({**row, 'url': full, 'detail_url': detail or full})
    queries = [{**row, 'url': asset_url('portal/business-number/' + row['key'] + '.png')} for row in QUERIES]
    registered = {**REGISTERED_QUERY, 'url': asset_url('portal/business-number/' + REGISTERED_QUERY['key'] + '.png')}
    evidence = [*estimates, *queries, registered]
    return dict(estimates=estimates, queries=queries, registered_query=registered,
                connected_count=sum(bool(r['url']) for r in evidence), total_count=len(evidence),
                missing=[r for r in evidence if not r['url']])
