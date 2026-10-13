"""Database reading uses fictional records only."""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from .models import Member, Case, Post, Article

@override_settings(DEV=False, APP_MODE='production', SECURE_SSL_REDIRECT=False)
class DatabaseReadingTests(TestCase):
    def setUp(self):
        self.editor = User.objects.create_user('fictional-editor', is_staff=True)
        self.member = Member.objects.create(name='가상교인', phone='01000000000', synthetic=True)
        session = self.client.session
        session.update({'member_id':str(self.member.pk), 'member_version':self.member.session_version, 'member_auth':'sms'})
        session.save()
    def case(self, **kwargs):
        return Case.objects.create(author=self.editor,title='가상 사건', overview='가상 본문 <script>alert(1)</script>', state='published', **kwargs)
    def test_empty_and_published_only_escaped_vertical(self):
        self.assertContains(self.client.get('/'), '게시된 사건이 아직 없습니다')
        draft = Case.objects.create(author=self.editor,title='가상 비공개')
        case = self.case(occurred_precision='day', occurred_on='2001-01-01')
        post = Post.objects.create(member=self.member, author_name=self.member.name, title='가상 글', body='보존', case=case)
        response = self.client.get('/?q=ignored')
        self.assertContains(response, '가상 본문 &lt;script&gt;')
        self.assertNotContains(response, '<script>')
        self.assertNotContains(response, draft.title)
        html = response.content.decode()
        headings = ['① 날짜','② 사건 경과','③ 관련 교단 헌법과 규정','④ 쟁점과 추가 확인사항']
        self.assertEqual(sorted(html.index(h) for h in headings), [html.index(h) for h in headings])
        self.assertNotContains(response, '검색')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(Post.objects.get(pk=post.pk).case_id, case.pk)
        self.assertRedirects(self.client.get(f'/cases/{case.pk}/'), f'/#material-case-{case.pk}', fetch_redirect_response=False)
    def test_date_order_unknown_last_and_no_fake_day(self):
        later = self.case(occurred_precision='day', occurred_on='2002-01-01')
        early = self.case(occurred_precision='month', occurred_year=2001, occurred_month=2)
        unknown = self.case(occurred_precision='unknown')
        html = self.client.get('/').content.decode()
        self.assertLess(html.index(f'id="material-case-{early.pk}"'), html.index(f'id="material-case-{later.pk}"'))
        self.assertLess(html.index(f'id="material-case-{later.pk}"'), html.index(f'id="material-case-{unknown.pk}"'))
        self.assertIn('2001년 2월', html)
        self.assertIn('날짜 미확인', html)
    def test_guest_inactive_and_no_file_url(self):
        case = self.case()
        self.client.logout()
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertEqual(self.client.get(f'/cases/{case.pk}/').status_code, 302)
        self.assertEqual(self.client.get('/private/initial.review.json').status_code, 302)
        session=self.client.session; session.update({'member_id':str(self.member.pk), 'member_version':self.member.session_version,'member_auth':'sms'});session.save()
        Member.objects.filter(pk=self.member.pk).update(active=False)
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_demo_cannot_read_unregistered_published_case(self):
        self.case()
        with override_settings(DEV=True,APP_MODE='development'):
            self.assertEqual(self.client.get('/').status_code,403)
            self.assertNotContains(self.client.get('/'),'가상 본문',status_code=403)
