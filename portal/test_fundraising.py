"""Voluntary fundraising copy and fail-closed account publication regressions."""
from html.parser import HTMLParser
from unittest.mock import patch
from django.test import TestCase, override_settings
from .fundraising import FUNDRAISING

# The supplied publication copy, retained verbatim and in order.
BODY = (
    '우리가 바라는 것은 누군가의 승리로 끝나는 교회가 아닙니다.',
    '성도들이 안심하고 예배드리고, 서로의 안부를 묻고, 다음 세대에게 기쁜 마음으로 물려줄 수 있는 교회입니다. 질문하는 목소리가 존중받고, 공동체의 중요한 결정에 충분한 설명과 책임이 따르는 교회입니다.',
    '지금의 갈등을 바라보며 많은 성도님께서 마음 아파하셨을 것입니다. 드러내어 말하지 못했어도, 교회를 걱정하며 기도해 오신 마음이 있다는 것을 알고 있습니다.',
    '기도하며 기다리는 마음과 함께, 사실을 확인하고 책임을 분명히 묻는 행동도 필요하다고 생각합니다.',
    '우리는 그동안의 자료와 경과를 바탕으로, 사회법을 통한 판단을 구하고자 합니다. 서로 다른 주장 속에서 무엇이 사실인지, 어떤 절차와 책임을 바로 세워야 하는지 확인하기 위한 과정입니다. 우리 역시 확인된 사실에 근거해 주장하고, 그 판단을 성실하게 마주하겠습니다.',
    '이 과정에는 변호사 상담과 선임, 소송 진행, 증거자료 정리 등에 비용이 필요합니다. 몇 사람의 부담만으로는 감당하기 어려운 현실적인 문제입니다.',
    '이 비용은 교회 헌금이나 교회 재정으로 충당하지 않겠습니다. 취지에 공감하는 성도님들의 자발적인 참여로 마련하고자 합니다.',
    '각자의 형편과 마음에 따라 십시일반 힘을 보태 주십시오. 참여 금액의 크기로 마음의 무게를 판단하지 않겠습니다. 작은 정성도 이 과정을 이어가는 소중한 힘이 됩니다.',
    '모금 참여 여부가 신앙이나 교회를 사랑하는 마음의 기준이 될 수는 없습니다. 경제적인 참여가 어려우셔도 부담 갖지 않으셔도 됩니다. 자료를 살펴봐 주시는 일, 잘못된 부분을 짚어 주시는 일, 기도로 함께해 주시는 일도 우리에게 필요합니다.',
    '맡겨주신 마음에, 투명한 운영으로 답하겠습니다',
    '모금은 카카오뱅크 모임통장을 통해 진행합니다.',
    '모금 목적은 이번 법적 대응에 필요한 비용 마련입니다.',
    '계좌 관리 담당자와 지출 확인 담당자를 안내하겠습니다.',
    '모금 총액과 지출 내역을 정기적으로 공유하되, 참여자의 이름과 개별 금액은 동의 없이 공개하지 않겠습니다.',
    '법적 대응과 관계없는 용도로 사용하지 않겠습니다.',
    '목적을 변경해야 하거나 절차 종료 후 잔액이 남는 경우에는, 처리 방안을 사전에 안내하고 참여자의 의견을 구하겠습니다.',
    '문의 방법은 추후 안내하겠습니다.',
    '서로의 짐을 조금씩 나누어 주십시오',
    '우리가 함께 보태는 것은 법적 대응에 필요한 비용이자, 교회의 문제를 외면하지 않고 끝까지 살피겠다는 마음입니다.',
    '갈등이 오래 이어질수록 지치기 쉽습니다. 그렇기에 서로의 짐을 조금씩 나누고자 합니다.',
    '사실을 확인하고, 책임을 묻고, 바로잡아야 할 것을 바로잡는 과정에 함께해 주십시오. 우리가 사랑하는 교회가 다시 서로를 믿고 예배하는 공동체로 나아갈 수 있도록, 여러분의 마음을 보태 주십시오.',
)


class BodyParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.inside = False; self.current = None; self.items = []
    def handle_starttag(self, tag, attrs):
        if tag == 'div' and dict(attrs).get('class') == 'fundraising-body':
            self.inside = True
        if self.inside and tag in ('p', 'li', 'h3'):
            self.current = []
        if self.current is not None and tag == 'br':
            self.current.append(' ')
    def handle_data(self, text):
        if self.current is not None:
            self.current.append(text)
    def handle_endtag(self, tag):
        if self.inside and tag in ('p', 'li', 'h3') and self.current is not None:
            self.items.append(' '.join(''.join(self.current).split())); self.current = None
        if tag == 'div':
            self.inside = False


@override_settings(SECURE_SSL_REDIRECT=False)
class FundraisingTests(TestCase):
    def test_supplied_copy_and_placement_remain_public_without_forms(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        parser = BodyParser(); parser.feed(html)
        self.assertEqual(tuple(parser.items), BODY)
        self.assertContains(response, '우리가 사랑하는 교회, 함께 책임지고 지켜가겠습니다')
        self.assertContains(response, 'href="#fundraising"', count=1)
        self.assertEqual(html.count('id="fundraising"'), 1)
        self.assertLess(html.index('id="fundraising"'), html.index('id="timeline"'))
        self.assertLess(html.index('id="fundraising"'), html.index('<footer>'))
        self.assertNotIn('<details', html.split('id="fundraising"', 1)[1])
        for private in ('/prepare', '/login/', '<form', 'name="phone"'):
            self.assertNotIn(private, html)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(html.count('class="timeline-card"'), 72)
        self.assertEqual(html.count('<video '), 3)

    def test_confirmed_account_is_public_only_in_the_fundraising_section(self):
        response = self.client.get('/')
        self.assertContains(response, '카카오뱅크 모임통장 · 계좌 공개 중', count=1)
        self.assertContains(response, '계좌번호 복사', count=1)
        self.assertNotContains(response, '계좌 준비 중')
        page = response.content.decode()
        section = page.split('id="fundraising"', 1)[1].split('</section>', 1)[0]
        for value in ('3333-09-0895440', '교회를 사랑하는 모임'):
            self.assertContains(response, value, count=1)
            self.assertIn(value, section)
            self.assertNotContains(self.client.get('/cases/material/T53/'), value)

    def test_incomplete_or_unpublished_accounts_never_reach_html(self):
        test_account = dict(status='published', account_number='TEST-ACCOUNT-NOT-REAL',
                            account_holder='TEST-HOLDER-NOT-REAL', manager='TEST-MANAGER', contact='TEST-CONTACT')
        for changes in ({'status': 'preparing'}, {'status': 'unexpected'},
                        {'account_number': ''}, {'account_number': '   '}, {'account_holder': ''}):
            with self.subTest(changes=changes), patch.dict(FUNDRAISING, {**test_account, **changes}):
                html = self.client.get('/').content.decode()
                self.assertEqual(html.count('카카오뱅크 모임통장 · 계좌 준비 중'), 1)
                self.assertNotIn('계좌번호 복사', html)
                for value in ('TEST-ACCOUNT-NOT-REAL', 'TEST-HOLDER-NOT-REAL', 'TEST-MANAGER', 'TEST-CONTACT'):
                    self.assertNotIn(value, html)

    def test_complete_published_account_has_copy_control_and_no_empty_labels(self):
        with patch.dict(FUNDRAISING, dict(status='published', account_number=' TEST-ACCOUNT-NOT-REAL ',
                                        account_holder='TEST-HOLDER-NOT-REAL')):
            response = self.client.get('/')
        self.assertContains(response, '카카오뱅크 모임통장 · 계좌 공개 중', count=1)
        self.assertContains(response, '<dd id="fundraising-account-number">TEST-ACCOUNT-NOT-REAL</dd>', html=True)
        self.assertContains(response, '<dt>예금주</dt>', html=True)
        self.assertContains(response, '계좌번호 복사')
        self.assertContains(response, 'role="status"')
        self.assertNotContains(response, '<dt>관리 담당자</dt>', html=True)
        self.assertNotContains(response, '<dt>문의 방법</dt>', html=True)

    def test_optional_public_fields_are_escaped(self):
        with patch.dict(FUNDRAISING, dict(status='published', account_number='TEST-ACCOUNT-NOT-REAL',
                                        account_holder='TEST-HOLDER-NOT-REAL', manager='<script>test()</script>',
                                        contact='TEST-CONTACT')):
            response = self.client.get('/')
        self.assertContains(response, '&lt;script&gt;test()&lt;/script&gt;')
        self.assertNotContains(response, '<script>test()</script>')
        self.assertContains(response, '<dt>관리 담당자</dt>', html=True)
        self.assertContains(response, '<dt>문의 방법</dt>', html=True)
