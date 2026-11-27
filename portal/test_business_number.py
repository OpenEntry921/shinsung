"""Public business-number section: evidence boundaries and arithmetic consistency."""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re
from unittest.mock import patch
from .business_number import ESTIMATES, QUERIES, REGISTERED_QUERY, business_number_context

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
    @override_settings(SHOW_BUSINESS_NUMBER_CARD=True)
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
        self.assertEqual(len(context['missing']), 6)
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        self.assertEqual(html.count('공개용 견적서 이미지 준비 중'), 3)
        self.assertEqual(html.count('해당 홈택스 조회 캡처의 공개용 이미지 준비 중'), 2)
        self.assertIn('현재 연결된 공개 증빙은 0개 / 전체 확인 대상 6개', html)
        self.assertIn('캡처 파일 미확보, 원문 화면 미대조', html)
        self.assertNotIn('<img ', html)
        self.assertNotIn('data-business-evidence data-', html)

    @patch('portal.business_number.asset_url', side_effect=lambda path: '/static/' + path)
    def test_all_six_reviewed_assets_have_correct_connections(self, _asset):
        context = business_number_context()
        self.assertEqual(context['missing'], [])
        self.assertEqual(context['connected_count'], 6)
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        self.assertEqual(len(re.findall(r'<img[^>]*src="([^"]+)"[^>]*>', html)), 6)
        self.assertNotIn('공개용 이미지 준비 중', html)
        self.assertNotIn('공개용 증빙 이미지 준비 상태', html)
        self.assertNotIn('준비 상태 보기', html)
        self.assertNotIn('캡처 파일 미확보', html)
        self.assertIn('현재 이 페이지에서 연결된 공개 증빙은 6개', html)
        self.assertIn('/static/portal/business-number/hometax-5811600460.png', html)
        self.assertIn('조회 화면 보기', html)
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

    def test_tax_status_correction_and_nonretroactive_limit(self):
        html = self.client.get('/').content.decode().split('id="business-number-check"', 1)[1]
        self.assertNotIn('별도 국세청 조회 증빙이 없어', html)
        self.assertEqual(REGISTERED_QUERY['number'], '581-16-00460')
        self.assertEqual(REGISTERED_QUERY['date'], '2026. 11. 18.')
        self.assertIn('2024년 08월 01일 간이과세자에서 일반과세자로 전환되었습니다', html)
        self.assertIn('해당 번호와 견적서상 상호·대표자명의 일치 여부나 개별 공사대금의 신고·납세 여부까지 확인되는 것은 아닙니다.', html)
        self.assertIn('실제 거래 당시 과세유형과 증빙 발급 의무는 공사 완료일·공급시기 등 관련 자료로 확인해야 합니다.', html)
        self.assertLess(html.index('</table>'), html.index('id="hometax-5811600460"'))
        self.assertLess(html.index('id="hometax-5811600460"'), html.index('id="estimate-2021"'))

    def test_accountability_copy_keeps_conditions_and_source_limits(self):
        html = self.client.get('/').content.decode()
        box = html.split('<aside class="business-number-accountability"', 1)[1].split('</aside>', 1)[0]
        for sentence in (
            '자신들이 관여한 재정 집행에도 같은 수준의 검증과 설명을 받아들여야 합니다.',
            '이 불일치는 ‘감사를 통과했다’는 말만으로 해소되지 않습니다.',
            '공급자 정보와 지급 증빙을 확인했습니까?',
            '정확한 지급·정산 증빙과 감사에서 확인한 자료를 제시하십시오.',
        ):
            self.assertIn('<strong>' + sentence + '</strong>', box)
        self.assertIn('확인하지 않았다면', box)
        self.assertIn('오류를 알고 있었다면', box)
        self.assertIn('이번 거래의 탈세나 고의적 허위 제출을 확정하는 것이 아니라', box)
        self.assertIn('‘감사를 통과했다’는 설명은 위 성도가 전달한 설명·요지에 근거합니다.', box)
        self.assertIn('노회 제출 여부·제출자·시점은 관련 원문과 추가 대조가 필요합니다.', box)
        for link in ('/cases/material/T24/', '/cases/material/T53/'):
            self.assertIn(link, box)
        self.assertIn('A01.', box)
        self.assertIn('#page=7', box)
        self.assertIn('#page=40', box)
        for phrase in ('불법인 줄 알면서', '알면서 노회를 속였다', '탈세했다', '횡령했다', '750만원', '750만 원', '업체가 존재하지 않는다', '실체 없는 업체'):
            self.assertNotIn(phrase, box)

    @patch('portal.business_number.asset_url', side_effect=lambda path: '/static/' + path if path.endswith('hometax-5811600460.png') else '')
    def test_registered_query_ready_does_not_clear_other_missing_states(self, _asset):
        context = business_number_context()
        self.assertEqual(context['connected_count'], 1)
        self.assertEqual(len(context['missing']), 5)
        html = self.client.get('/').content.decode()
        card = html.split('id="hometax-5811600460"', 1)[1].split('</figure>', 1)[0]
        self.assertNotIn('미확보', card)
        self.assertNotIn('준비 중', card)
        self.assertNotIn('직접 대조하지 못했습니다', card)
        self.assertIn('alt="581-16-00460 홈택스 조회 결과. 부가가치세 일반과세자로 표시되며, 2024년 8월 1일 간이과세자에서 일반과세자로 전환되었다는 안내. 조회기준일자 2026년 11월 18일."', card)
        self.assertIn('출처: 제공된 국세청 홈택스 사업자등록상태 조회 캡처 · 조회기준일자 2026. 11. 18.', card)
        self.assertIn('이 화면은 해당 번호의 과세유형과 전환 안내를 보여줍니다.', card)
        self.assertIn('공개용 증빙 이미지 준비 상태', html)
        self.assertEqual(html.count('공개용 견적서 이미지 준비 중'), 3)
        self.assertEqual(html.count('해당 홈택스 조회 캡처의 공개용 이미지 준비 중'), 2)

    def test_received_original_query_files_and_dates(self):
        import hashlib
        expected = {'hometax-5811600460.png': 'bf47c64db5b241e3d8a4212511e09bfcce522adb7ba143eee93ccd78c3cb29d2', 'hometax-1280318446.png': '4f156b7d5b7bafc1a02b8c04dc80b16d069be6227f6b20df9dd4c81305c76012'}
        for name, digest in expected.items():
            path = Path(settings.BASE_DIR) / 'portal/static/portal/business-number' / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        context = business_number_context()
        self.assertEqual(context['connected_count'], 3)
        self.assertEqual(len(context['missing']), 3)
        html = self.client.get('/').content.decode()
        registered = html.split('id="hometax-5811600460"', 1)[1].split('</figure>', 1)[0]
        self.assertNotIn('미확보', registered)
        self.assertNotIn('준비 중', registered)
        original = html.split('id="hometax-1280318446"', 1)[1].split('</figure>', 1)[0]
        self.assertIn('2026. 11. 18.', original)
        self.assertIn('2026-11-18', original)
        self.assertNotIn('2026-11-17', original)
        self.assertIn('끝자리 변경 가정 번호', html)
