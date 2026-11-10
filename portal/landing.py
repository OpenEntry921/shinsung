"""Public landing metadata only; never loads member or preparation records."""
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from .reading_registry import legacy_reading_entries

# Stable keys, not display numbers (the revised timeline intentionally differs).
VIDEOS = (
    dict(key='questions', title='교회에 묻는 다섯 가지 질문',
         description='고소 이후의 회복, 헌신, 참여와 교회 운영에 관한 질문입니다.',
         filename='church-questions.mp4',
         poster='questions.jpg', related=('T24', 'T33', 'T32')),
    dict(key='offering', title='목적헌금의 본질을 훼손하지 마십시오',
         description='목적헌금의 실제 지출과 원심 판단, 복직 요청과 바로잡는 책임을 살펴봅니다.',
         filename='offering-and-restoration.mp4',
         poster='offering.jpg', related=('T05', 'T18', 'T63')),
    dict(key='example', title='누가 매일 나오시라고 합니까?',
         description='베드로전서의 권면과 예배·사역에 참여하는 지도자의 본을 묻습니다.',
         filename='prayer-and-service.mp4',
         poster='example.jpg', related=('T02', 'T47')),
)
ISSUES = (
    ('목사 고소와 교회의 회복', '판결과 상고의 쟁점, 공동체 회복의 책임', ('T24', 'T62', 'T63', 'T64')),
    ('목적헌금과 회계 처리', '실제 사용 내역과 원심 판단', ('T04', 'T05', 'T18', 'T63')),
    ('장로의 헌신과 참여', '십일조 기록, 예배와 사역 참여', ('T02', 'T47')),
    ('제직 임명과 참여 기회', '임명 기준과 진행 경과', ('T33', 'T34')),
    ('공동의회와 설명 책임', '개최 경과, 예산·결산과 성도의 참여', ('E22', 'T32', 'T40')),
)


def asset_url(logical):
    """Only advertise installed local assets, including collected-only deployments."""
    if not (finders.find(logical) or staticfiles_storage.exists(logical)):
        return ''
    try:
        return staticfiles_storage.url(logical)
    except (ValueError, OSError):
        # A missing manifest entry must not break the public page.
        return ''


def landing_context(entries, groups):
    lookup = {e['key']: e for e in [*entries, *legacy_reading_entries()]}
    def related(keys):
        return [lookup[key] for key in keys]
    videos = []
    for item in VIDEOS:
        videos.append({**item, 'related': related(item['related']),
                       'url': asset_url('portal/videos/' + item['filename']),
                       'poster_url': asset_url('portal/videos/' + item['poster'])})
    issues = [dict(title=t, description=d, related=related(keys)) for t, d, keys in ISSUES]
    # Published operator changes take precedence; defaults retain their historical
    # basis dates and explicit editorial classification, never fabricated freshness.
    records = [r for _, items in groups for r in items]
    published = sorted((r for r in records if not r['is_default']),
                       key=lambda r: (r['updated_at'], r['id']), reverse=True)
    defaults = next(items for label, items in groups if label == '최근 업데이트')
    recent = (published + [r for r in defaults if r['is_default']])[:3]
    return dict(home_videos=videos, home_issues=issues, recent_records=recent)
