"""Public landing, real asset integrity, and isolated synthetic fallback tests."""
import hashlib
from unittest.mock import patch
from django.conf import settings
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.utils import timezone
from .landing import VIDEOS
from .models import ProgressRecord
from .reading_registry import reading_entries


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.in_timeline = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('class') == 'timeline-card':
            self.links.append(attrs['href'])


@override_settings(SECURE_SSL_REDIRECT=False)
class LandingTests(TestCase):
    @patch('portal.landing.asset_url', return_value='')
    def test_guest_landing_keeps_order_identifiers_and_public_boundary(self, _asset_url):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertContains(response, '신사모 첫 모임 ·')
        self.assertContains(response, 'id="devotion"')
        self.assertContains(response, 'href="/devotion/hymn-310/">찬송가 310장 「아 하나님의 은혜로」')
        self.assertContains(response, 'href="/devotion/acts-17-30-31/">사도행전 17:30–31')
        self.assertContains(response, '성도와 목회자가 함께 교회를 돌보고, 예배와 봉사를 이어갈 수 있도록 마음을 모읍니다.')
        for anchor, label in (
            ('dashboard', '현재 진행 상황'), ('fundraising', '모금 안내'), ('timeline', '시간순 사건 기록'),
        ):
            self.assertContains(response, f'href="#{anchor}">{label}</a>')
        self.assertContains(response, 'LAITY · 공동체의 질문')
        self.assertContains(response, '영상 준비 중', count=3)
        self.assertNotContains(response, '<video')
        self.assertNotContains(response, '<source')
        for private in ('/prepare', '/login/', '/apply/', '/posts/', '/requests/', 'name="phone"', '의견 등록'):
            self.assertNotIn(private, html)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn("default-src 'self'", response['Content-Security-Policy'])
        for anchor in ('videos', 'issues', 'timeline', 'dashboard', 'roadmap', 'progress-details', 'roadmap-details'):
            self.assertEqual(html.count(f'id="{anchor}"'), 1)
        order = ('hero-title', 'issues', 'registration-title', 'videos', 'dashboard', 'fundraising', 'timeline')
        positions = [html.index(f'id="{anchor}"') for anchor in order]
        self.assertEqual(positions, sorted(positions))
        self.assertContains(response, 'class="issue-row"', count=5)
        self.assertIn('<details id="progress-details" class="full-details">', html)
        self.assertIn('<details id="roadmap-details" class="full-details">', html)
        parser = Links(); parser.feed(html)
        self.assertEqual(parser.links, [f'/cases/material/{e["key"]}/' for e in reading_entries()])
        self.assertEqual(len(set(parser.links)), 72)
        self.assertContains(response, '기존 정리 E01~E30 보기')
        self.assertEqual(self.client.head('/').status_code, 200)

    def test_devotion_reading_pages_are_public_and_return_home(self):
        for path, title in (
            ('/devotion/hymn-310/', '찬송가 310장 「아 하나님의 은혜로」'),
            ('/devotion/acts-17-30-31/', '사도행전 17:30–31 · 개역개정'),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, f'<h1 id="devotion-title">{title}</h1>')
                if path.endswith('/hymn-310/'):
                    self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')
                else:
                    self.assertNotContains(response, 'acts-17-30-31.png')
                    self.assertContains(response, '<ol start="30">')
                    self.assertContains(response, '<li>', count=2)
                self.assertContains(response, 'href="/#devotion">홈으로 돌아가기</a>')
                self.assertEqual(self.client.head(path).status_code, 200)
                self.assertNotEqual(self.client.post(path).status_code, 200)

    @override_settings(SHOW_BUSINESS_NUMBER_CARD=False)
    def test_registration_chart_replaces_default_business_number_card(self):
        response = self.client.get('/')
        self.assertNotContains(response, 'id="business-number-card-title"')
        self.assertNotContains(response, 'href="#business-number-check"')
        self.assertNotContains(response, 'id="business-number-check"')
        self.assertNotContains(response, '공사 견적서 사업자등록번호 확인')
        self.assertNotContains(response, '/business-number-evidence/')
        self.assertNotContains(response, '등록일이 있는 경우')
        self.assertNotContains(response, '공개 사건 기록')
        self.assertContains(response, '<strong>214명</strong>')
        self.assertContains(response, '<details class="registration-details">')
        self.assertContains(response, '<summary>연도별 등록 현황 보기</summary>')
        self.assertContains(response, '함께 확인하고 싶은 질문이나 나누고 싶은 자료가 있다면 모임 진행자에게 말씀해 주세요.')
        self.assertContains(response, '11월 26일 기준')
        self.assertContains(response, '2020년 이후 새가족 등록 현황')
        self.assertContains(response, 'datetime="2026-11-26"')
        self.assertEqual(
            [(row['year'], row['count']) for row in response.context['annual_registrations']],
            [(2020, 3), (2021, 2), (2022, 2), (2023, 24), (2024, 82), (2025, 62), (2026, 46)],
        )

    def test_local_media_presence_and_missing_poster_do_not_break_home(self):
        with TemporaryDirectory() as directory, self.settings(
            STATICFILES_DIRS=[directory],
            STATICFILES_FINDERS=['django.contrib.staticfiles.finders.FileSystemFinder'],
            STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                      'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
            STATIC_ROOT=directory + '/collected',
        ):
            (Path(directory) / 'collected').mkdir()
            folder = Path(directory) / 'portal/videos'; folder.mkdir(parents=True)
            first = VIDEOS[0]
            (folder / first['filename']).write_bytes(b'synthetic-media-placeholder-not-playable')
            html = self.client.get('/').content.decode()
            self.assertEqual(html.count('<video '), 1)
            self.assertEqual(html.count('영상 준비 중'), 2)
            self.assertIn('controls playsinline preload="none"', html)
            self.assertNotIn(' autoplay', html)
            self.assertNotIn(' poster=', html)
            # Evidence images elsewhere do not supply a missing video poster.
            video_grid = html.split('<div class="video-grid">', 1)[1].split('<section class="landing-section"', 1)[0]
            self.assertNotIn('<img ', video_grid)
            (folder / first['poster']).write_bytes(b'synthetic-poster-placeholder')
            self.assertContains(self.client.get('/'), 'poster="/static/portal/videos/authority-and-responsibility.jpg"')
            (folder / first['filename']).unlink()
            html = self.client.get('/').content.decode()
            self.assertNotIn('<video ', html)
            self.assertIn('영상 준비 중', html)
            # A poster alone does not turn a missing film into a broken player.
            self.assertIn('alt="권한에 책임이 뒤따릅니다 영상 표지"', html)

    def test_uncollected_manifest_entry_falls_back_to_pending(self):
        from unittest.mock import patch
        from django.contrib.staticfiles.storage import staticfiles_storage
        original_url = staticfiles_storage.url
        def manifest_url(logical, *args, **kwargs):
            if logical.startswith('portal/videos/'):
                raise ValueError('missing manifest entry')
            return original_url(logical, *args, **kwargs)
        with patch('portal.landing.finders.find', return_value='synthetic.mp4'), patch(
            'portal.landing.staticfiles_storage.url', side_effect=manifest_url
        ):
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '영상 준비 중', count=3)
        self.assertNotContains(response, '<video')

    def test_three_recent_published_changes_sorted_by_real_modified_time(self):
        now = timezone.now()
        records = []
        for i in range(4):
            record = ProgressRecord.objects.create(category='issue', title=f'공개 검증 기록 {i}',
                public_text=f'가상 기록 {i}', basis_on=date(2026, 10, 1),
                reading_key='T05', status='review', published=True)
            ProgressRecord.objects.filter(pk=record.pk).update(updated_at=now + timedelta(minutes=i))
            records.append(record)
        ProgressRecord.objects.create(category='update', title='비공개 검증 기록',
            public_text='노출 금지', basis_on=date(2026, 11, 1), published=False)
        response = self.client.get('/')
        recent = response.context['recent_records']
        self.assertEqual([r['title'] for r in recent], [r.title for r in reversed(records[1:])])
        self.assertContains(response, 'data-recent-record=', count=3)
        self.assertNotContains(response, '비공개 검증 기록')
        self.assertContains(response, 'id="dashboard-full"')
        self.assertContains(response, 'id="roadmap-full"')
        self.assertEqual(ProgressRecord.objects.count(), 5)

    def test_defaults_and_related_links_are_grounded_in_existing_records(self):
        response = self.client.get('/')
        for record in response.context['recent_records']:
            self.assertTrue(record['is_default'])
            self.assertLessEqual(record['basis_on'], date(2026, 11, 4))
        # Linking real media must preserve the existing related-record mapping.
        self.assertEqual([e['key'] for e in response.context['home_videos'][2]['related']], ['T05', 'T18', 'T63'])
        for group in [*response.context['home_videos'], *response.context['home_issues']]:
            for entry in group['related']:
                target = self.client.get(f'/cases/material/{entry["key"]}/')
                self.assertEqual(target.status_code, 200)
                self.assertContains(target, entry['key'])
        self.assertEqual(ProgressRecord.objects.count(), 0)

    def test_three_real_videos_preserve_uploads_and_activate_the_right_cards(self):
        expected = (
            ('questions', 'authority-and-responsibility.mp4', '권한에 책임이 뒤따릅니다',
             'd68992e2ac642092dee5deca8a167fc41f9509f523a678d8d1a24afc72cc2ae1'),
            ('example', 'daily-participation.mp4', '누가 매일 나오랍니까?',
             'dc670f192f40e0c3d6a45af3ef1de542b1b54ece7de10bde7644ae5c19d058b6'),
            ('offering', 'purpose-of-offerings.mp4', '본질을 훼손 마세요',
             '4f4a5b2d377e129ee05d8cd009c97b0d60db2cc846dbab6c643d2fa952c450ae'),
        )
        response = self.client.get('/')
        self.assertContains(response, '<video ', count=3)
        self.assertNotContains(response, '영상 준비 중')
        self.assertContains(response, 'controls playsinline preload="none"', count=3)
        self.assertNotContains(response, ' autoplay')
        videos = response.context['home_videos']
        for item, (key, filename, title, digest) in zip(videos, expected):
            with self.subTest(key=key):
                self.assertEqual((item['key'], item['filename'], item['title']), (key, filename, title))
                binary = settings.BASE_DIR / 'portal/static/portal/videos' / filename
                self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), digest)
                self.assertTrue(item['url'].startswith('/static/portal/videos/'))
                self.assertTrue(item['url'].endswith('.mp4'))
                self.assertTrue(item['poster_url'].endswith('.jpg'))
                poster = settings.BASE_DIR / 'portal/static/portal/videos' / item['poster']
                self.assertTrue(poster.read_bytes().startswith(b'\xff\xd8'))
        html = response.content.decode()
        for invalid in ('sediment://', 'blob/', '/workspace/', 'chatgpt.com', 'sandbox:'):
            self.assertNotIn(invalid, html)

    def test_collected_only_assets_activate_without_source_files(self):
        from .landing import asset_url
        with TemporaryDirectory() as directory, self.settings(
            STATICFILES_DIRS=[],
            STATICFILES_FINDERS=['django.contrib.staticfiles.finders.FileSystemFinder'],
            STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                      'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
            STATIC_ROOT=directory,
        ):
            folder = Path(directory) / 'portal/videos'; folder.mkdir(parents=True)
            (folder / 'authority-and-responsibility.mp4').write_bytes(b'synthetic-collected-asset')
            self.assertEqual(asset_url('portal/videos/authority-and-responsibility.mp4'), '/static/portal/videos/authority-and-responsibility.mp4')
            self.assertEqual(asset_url('portal/videos/missing.mp4'), '')
