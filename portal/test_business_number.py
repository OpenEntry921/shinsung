"""Public business-number section: evidence boundaries and arithmetic consistency."""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re
from unittest.mock import patch
from .business_number import ESTIMATES, QUERIES, business_number_context

from django.conf import settings
from django.test import TestCase, override_settings


class ComparisonRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = ''
    def handle_data(self, data):
        if self.row is not None: self.row += data + ' '
    def handle_endtag(self, tag):
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


@override_settings(SECURE_SSL_REDIRECT=False)
class BusinessNumberTests(TestCase):
    def test_public_placement_and_existing_content(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('id="business-number-check"'), 1)
        self.assertEqual(html.count('href="#business-number-check"'), 1)
        self.assertLess(html.index('class="hero-description"'), html.index('class="business-number-card"'))
        self.assertLess(html.index('class="business-number-card"'), html.index('class="fundraising-card"'))
        self.assertLess(html.index('class="business-number-card"'), html.index('class="timeline"'))
        self.assertEqual(html.count('class="timeline-card"'), 72)
        self.assertEqual(html.count('<video '), 3)
        self.assertIn('id="fundraising"', html)
        self.assertNotIn('/prepare', html)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn("default-src 'self'", response['Content-Security-Policy'])
        self.assertEqual(self.client.head('/').status_code, 200)

    def test_comparison_and_calculation_agree(self):
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        table = ComparisonRows(); table.feed(html)
        for day, project, number in (
            ('2021. 9. 25.', '임시성전 인테리어', '581-16-00460'),
            ('2023. 10. 10.', '임시성전 철거', '581-16-00460'),
            ('2024. 2. 25.', '4층 개조공사', '128-03-18446'),
        ):
            self.assertTrue(any(all(value in row for value in (day, project, number)) for row in table.rows))
        # Independently recompute the two printed examples, without a network lookup.
        weights = [1, 3, 7, 1, 3, 7, 1, 3, 5]
        for number, total, check in [('1280318446', 121, 9), ('5811600460', 100, 0)]:
            digits = list(map(int, number))
            actual = sum(n * w for n, w in zip(digits[:9], weights)) + digits[8] * 5 // 10
            self.assertEqual(actual, total)
            self.assertEqual((-actual) % 10, check)
        self.assertIn('= <strong>119</strong>', html)
        self.assertIn('119 + 2 = <strong>121</strong>', html)
        self.assertIn('= <strong>9</strong>', html)
        self.assertIn('검증 계산을 통과하더라도 실제 등록된 번호라는 뜻은 아닙니다.', html)

    @patch('portal.business_number.asset_url', return_value='')
    def test_missing_evidence_has_no_broken_or_substitute_image_links(self, _asset):
        context = business_number_context()
        self.assertEqual(len(context['missing']), 5)
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        self.assertEqual(html.count('공개용 견적서 이미지 준비 중'), 3)
        self.assertEqual(html.count('해당 홈택스 조회 캡처의 공개용 이미지 준비 중'), 2)
        self.assertNotIn('<img ', html)
        self.assertNotIn('data-business-evidence data-', html)

    @patch('portal.business_number.asset_url', side_effect=lambda path: '/static/' + path)
    def test_all_five_reviewed_assets_have_correct_connections(self, _asset):
        context = business_number_context()
        self.assertEqual(context['missing'], [])
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        self.assertEqual(len(re.findall(r'<img[^>]*src="([^"]+)"[^>]*>', html)), 5)
        self.assertNotIn('공개용 이미지 준비 중', html)
        for row in ESTIMATES:
            self.assertIn('id="' + row['key'] + '"', html)
            self.assertIn(row['amount'], html)
            self.assertIn('/static/portal/business-number/' + row['key'] + '-redacted.jpg', html)
            self.assertIn('/static/portal/business-number/' + row['key'] + '-detail.jpg', html)
        for row in QUERIES:
            self.assertIn('/static/portal/business-number/' + row['key'] + '.png', html)
        self.assertIn('data-business-evidence-close', html)
        self.assertIn('data-business-evidence-zoom', html)

    def test_query_attribution_and_evidence_boundary(self):
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        self.assertIn('끝자리 변경 가정 번호: <strong>128-03-18449</strong>', html)
        self.assertIn('견적서에 없는 번호이며, 마지막 숫자만 변경해 추가 조회한 번호입니다.', html)
        self.assertIn('성도가 전달한 설명·요지', html)
        self.assertIn('별도 영수증과 자료 요청·회신 경위는 추가 증빙과 대조가 필요합니다.', html)
        self.assertIn('href="https://www.hometax.go.kr"', html)
        self.assertNotIn('<blockquote', html)
        for phrase in ('위법 확정', '가짜 업체', '위조 견적서', '사기', '횡령', '허위 감사', '명예훼손에 해당하지 않는다', '답변 거부'):
            self.assertNotIn(phrase, html)
        # The already-public source remains unchanged; never substitute a private original.
        source = Path(settings.BASE_DIR) / 'static/case-documents/D01.pdf'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), '1103118c9b9291508394c90b5f40e41b912a02e6d3b9bdeedccadcd30544206c')
