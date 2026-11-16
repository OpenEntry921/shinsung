"""Public business-number section: evidence boundaries and arithmetic consistency."""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re

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
        self.assertIn('4×5 = <strong>119</strong>', html)
        self.assertIn('119 + 2 = <strong>121</strong>', html)
        self.assertIn('검증 숫자 = <strong>9</strong>', html)
        self.assertIn('계산을 통과한다고 실제 등록된 번호임이 증명되는 것은 아니며', html)

    def test_evidence_missing_status_and_query_attribution(self):
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        self.assertIn('다른 견적서 2장과 홈택스 조회 화면 2장은 현재 확보하지 못했습니다.', html)
        self.assertEqual(html.count('견적서 원문 미확보'), 2)
        self.assertEqual(html.count('해당 홈택스 조회 화면: 미확보'), 2)
        self.assertEqual(html.count('사용자 전달 조회기준일자: 2026. 11. 17.'), 2)
        self.assertIn('끝자리 변경 가정 번호: <strong>128-03-18449</strong>', html)
        self.assertIn('성도가 전달한 설명·요지', html)
        self.assertIn('별도 영수증의 내용, 자료 공개 요청·회신 경위, 감사 관련 설명은 관련 원문과 추가 대조가 필요합니다.', html)
        self.assertIn('href="https://www.hometax.go.kr"', html)
        self.assertNotIn('<blockquote', html)
        self.assertNotRegex(html, r'<img[^>]*(hometax|2021|2023)')
        for phrase in ('위법이 드러났다', '가짜 업체다', '위조 견적서다', '사기 또는 횡령이다', '감사가 허위였다', '명예훼손에 해당하지 않는다'):
            self.assertNotIn(phrase, html)
        images = re.findall(r'<img[^>]*src="([^"]+)"[^>]*>', html)
        self.assertEqual(len(images), 1)
        self.assertIn('estimate-2024-detail', images[0])
        self.assertIn('비교 부분 확대 보기 (새 탭)', html)
        self.assertIn('견적서 전체 보기 (개인정보 가림, 새 탭)', html)
        # Keep the already-public source unchanged; never substitute a private original.
        source = Path(settings.BASE_DIR) / 'static/case-documents/D01.pdf'
        expected = '1103118c9b9291508394c90b5f40e41b912a02e6d3b9bdeedccadcd30544206c'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), expected)
