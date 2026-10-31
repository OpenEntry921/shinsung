"""Timeline lists metadata only; detail pages preserve template records."""
from django.test import TestCase,override_settings
from .models import Member,Case,CaseComment
from .testing import member_session
from .reading_registry import reading_entries

@override_settings(SECURE_SSL_REDIRECT=False)
class DirectHTMLReadingTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        member_session(self.client,self.member)
    def test_timeline_metadata_links_counts_and_uncertain_group(self):
        CaseComment.objects.create(member=self.member,author_name=self.member.name,reading_key='E01',body='목록에 노출되면 안 되는 가상 의견')
        response=self.client.get('/');html=response.content.decode()
        self.assertEqual(response.status_code,200)
        self.assertEqual(html.count('class="timeline-card"'),30)
        self.assertNotIn('class="case-group direct-case"',html)
        self.assertNotIn('name="body"',html)
        self.assertNotIn('목록에 노출되면 안 되는 가상 의견',html)
        self.assertEqual(Case.objects.count(),0)
        self.assertEqual([e['key'] for e in reading_entries() if e['uncertain']],['E06','E10','E22'])
        for i in range(1,31): self.assertEqual(html.count(f'href="/cases/material/E{i:02}/"'),1)
        self.assertIn('의견 1개',html)
        self.assertEqual(html.count('아직 등록된 진행 기록이 없습니다'),5)
        self.assertEqual(html.count('진행 상태 등록 전'),5)
    def test_legacy_and_invalid_links(self):
        for i in (1,30):
            self.assertRedirects(self.client.get(f'/cases/{i}/'),f'/cases/material/E{i:02}/',fetch_redirect_response=False)
            self.assertEqual(self.client.get(f'/cases/material/E{i:02}/').status_code,200)
        self.assertEqual(self.client.get('/cases/material/E31/').status_code,404)
    def test_guest_no_body(self):
        self.client.logout()
        for path in ('/','/cases/1/','/cases/material/E30/'):
            self.assertEqual(self.client.get(path).status_code,302)
