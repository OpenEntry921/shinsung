"""Public landing metadata only; never loads member or preparation records."""
from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from .reading_registry import legacy_reading_entries

# Stable keys, not display numbers (the revised timeline intentionally differs).
VIDEOS = (
    dict(key='questions', title='권한에 책임이 뒤따릅니다',
         description='교회 운영에서 권한과 설명 책임을 묻습니다.',
         filename='authority-and-responsibility.mp4',
         poster='authority-and-responsibility.jpg', related=('T24', 'T33', 'T32')),
    dict(key='example', title='누가 매일 나오랍니까?',
         description='예배와 사역에 참여하는 지도자의 역할을 묻습니다.',
         filename='daily-participation.mp4',
         poster='daily-participation.jpg', related=('T02', 'T47')),
    dict(key='offering', title='본질을 훼손 마세요',
         description='목적헌금의 취지와 사용에 관한 기록을 살펴봅니다.',
         filename='purpose-of-offerings.mp4',
         poster='purpose-of-offerings.jpg', related=('T05', 'T18', 'T63')),
)

# Published aggregates only. Known registration dates take precedence over report years.
ANNUAL_REGISTRATIONS = ((2020, 3), (2021, 2), (2022, 2), (2023, 24),
                        (2024, 82), (2025, 62), (2026, 46))
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
    maximum = max(count for _, count in ANNUAL_REGISTRATIONS if count is not None)
    registrations = [
        dict(year=year, count=count, width=round(100 * count / maximum) if count is not None else 0)
        for year, count in ANNUAL_REGISTRATIONS
    ]
    return dict(home_videos=videos, home_issues=issues, recent_records=recent,
                show_business_number_card=settings.SHOW_BUSINESS_NUMBER_CARD,
                annual_registrations=registrations)
