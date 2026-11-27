from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .access import POLICY_FIELDS
from .models import Challenge, Member, Post, RateBucket
from .testing import approve

LOGIN = '/board/auth/'
VERIFY = '/board/verify/'


@override_settings(SECURE_SSL_REDIRECT=False, DEV=True,
                   **{name: '가상 운영 설정' for name in POLICY_FIELDS})
class BoardAuthenticationTests(TestCase):
    def setUp(self):
        self.member = Member.objects.create(name='가상 교인', phone='01000000001', synthetic=True)
        self.application = approve(self.member)
        self.client.get(LOGIN)
        self.sender = self.enterContext(patch('portal.board_auth.send_sms', return_value=True))

    def request_code(self, **changes):
        return self.client.post(LOGIN, {
            'name': self.member.name, 'phone': '010-0000-0001', 'acknowledged': 'yes', **changes,
        })

    def code(self):
        return self.sender.call_args.args[1]

    def test_home_to_real_name_post_and_logout(self):
        self.assertContains(self.client.get('/'), f'href="{LOGIN}"')
        self.assertEqual(self.client.get('/posts/').status_code, 403)
        self.assertRedirects(self.request_code(), VERIFY)
        before = self.client.session.session_key
        self.assertRedirects(self.client.post(VERIFY, {'code': self.code()}), '/posts/')
        self.assertNotEqual(self.client.session.session_key, before)
        self.assertNotIn('member_id', self.client.session)
        self.assertRedirects(self.client.get(LOGIN), '/posts/')
        form = self.client.get('/posts/new/')
        self.assertContains(form, '명부에 등록된 실명이 게시판에 표시됩니다')
        self.client.post('/posts/new/', {'title': '가상 질문', 'body': '질문 본문', 'author_name': '조작'})
        post = Post.objects.get()
        self.assertEqual(post.author_name, self.member.name)
        detail = f'/posts/{post.pk}/'
        self.assertContains(self.client.get(detail), self.member.name)
        self.assertNotContains(self.client.get(detail), self.member.phone)
        self.assertEqual(Client().get(detail).status_code, 403)
        self.assertEqual(self.client.get('/requests/').status_code, 403)
        self.assertEqual(self.client.get('/comments/E01/').status_code, 403)
        self.assertRedirects(self.client.get('/admin/'), '/admin/login/', fetch_redirect_response=False)
        self.client.post('/logout/')
        self.assertEqual(self.client.get(detail).status_code, 403)
        self.assertEqual(self.client.post(VERIFY, {'code': self.code()}).status_code, 400)

    def test_mismatch_shared_number_and_unapproved_have_identical_response(self):
        expected = self.request_code(name='불일치')
        self.assertEqual((expected.status_code, expected.url), (302, VERIFY))
        RateBucket.objects.all().delete()
        other = Member.objects.create(name='다른 교인', phone=self.member.phone, synthetic=True)
        shared = self.request_code()
        self.assertEqual((shared.status_code, shared.url, shared.content),
                         (expected.status_code, expected.url, expected.content))
        other.delete()
        RateBucket.objects.all().delete()
        self.application.delete()
        self.assertRedirects(self.request_code(), VERIFY)
        self.sender.assert_not_called()

    def test_attempt_limit_expiry_and_browser_binding(self):
        self.request_code()
        code = self.code()
        challenge = Challenge.objects.get()
        self.assertNotEqual(challenge.digest, code)
        other = Client()
        other.get(LOGIN)
        self.assertEqual(other.post(VERIFY, {'code': code}).status_code, 400)
        wrong = '000000' if code != '000000' else '000001'
        for _ in range(5):
            self.assertEqual(self.client.post(VERIFY, {'code': wrong}).status_code, 400)
        self.assertEqual(self.client.post(VERIFY, {'code': code}).status_code, 400)
        Challenge.objects.update(attempts=0, expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(VERIFY, {'code': code}).status_code, 400)

    def test_resend_replaces_old_code_and_failure_leaves_no_usable_challenge(self):
        with patch('portal.board_auth.secrets.randbelow', return_value=123456):
            self.request_code()
            old = self.code()
            self.request_code()
            self.assertEqual(self.sender.call_count, 1)
            RateBucket.objects.update(start=timezone.now() - timedelta(seconds=61))
            self.request_code()
        self.assertNotEqual(old, self.code())
        self.assertEqual(self.client.post(VERIFY, {'code': old}).status_code, 400)
        self.sender.return_value = False
        RateBucket.objects.update(start=timezone.now() - timedelta(seconds=61))
        self.assertRedirects(self.request_code(), VERIFY)
        self.assertEqual(self.client.post(VERIFY, {'code': self.code()}).status_code, 400)

    def test_consumption_and_revocation(self):
        self.request_code()
        from .board_auth import BROWSER_KEY, consume
        browser = self.client.session[BROWSER_KEY]
        self.assertRedirects(self.client.post(VERIFY, {'code': self.code()}), '/posts/')
        self.assertIsNone(consume(browser, self.code()))
        self.application.delete()
        self.assertEqual(self.client.get('/posts/').status_code, 403)

    def test_deactivation_invalidates_board_session(self):
        self.request_code()
        self.client.post(VERIFY, {'code': self.code()})
        self.member.active = False
        self.member.save()
        self.assertEqual(self.client.get('/posts/').status_code, 403)
