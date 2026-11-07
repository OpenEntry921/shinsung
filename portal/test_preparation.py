"""Temporary preparation access must never grant existing member access."""
import hashlib
import json
import re
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import CaseComment, Member, PreparationComment, PreparationReview
from .preparation import SESSION_KEY, preparation_data
from .reading_registry import TIMELINE_KEYS
from .testing import member_session


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False)
class PreparationTests(TestCase):
    def login(self, client=None):
        return (client or self.client).post('/prepare/', {'name': '준비위원', 'phone': '01011111111'})

    def test_shared_login_isolated_in_production_with_real_roster(self):
        Member.objects.create(name='가상 별도 명부', phone='01099999999', synthetic=False)
        with override_settings(DEV=False):
            self.assertRedirects(self.client.get('/prepare'), '/prepare/', fetch_redirect_response=False)
            for name, number in [('가상교인', '01000000000'), ('준비위원', '01000000000'), ('준비위원', '한글번호')]:
                response = self.client.post('/prepare/', {'name': name, 'phone': number})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(SESSION_KEY, self.client.session)
                self.assertNotContains(response, '72개 사건 전수 점검표')
            self.assertRedirects(self.login(), '/prepare/', fetch_redirect_response=False)
            self.assertNotIn('member_id', self.client.session)
            self.assertEqual(Member.objects.count(), 1)
            response = self.client.get('/prepare/')
            self.assertContains(response, '72개 사건 전수 점검표')
            self.assertEqual(len(response.context['rows']), 72)
            self.assertIn('noindex', response['X-Robots-Tag'])
            self.assertIn('no-store', response['Cache-Control'])
            self.assertContains(self.client.get('/prepare/events/T01/'), '기존 ⑤ 우리의 의견')
            self.assertRedirects(self.client.get('/'), '/login/', fetch_redirect_response=False)
            self.assertEqual(self.client.post('/comments/T01/', {'body': '가상 분리 검증'}).status_code, 302)
            self.assertEqual(CaseComment.objects.count(), 0)

    def test_member_login_does_not_open_preparation_or_link_to_it(self):
        member = Member.objects.create(name='가상 일반 이용자', phone='01000000000', synthetic=True)
        member_session(self.client, member)
        home = self.client.get('/')
        self.assertNotContains(home, '/prepare')
        self.assertContains(self.client.get('/prepare/'), '준비위원 접속')
        self.assertNotContains(self.client.get('/prepare/'), '72개 사건 전수 점검표')
        self.assertRedirects(self.client.get('/prepare/events/T01/'), '/prepare/', fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertRedirects(self.login(), '/prepare/', fetch_redirect_response=False)
        self.client.post('/prepare/logout/')
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.session.get('member_id'), str(member.pk))
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_guests_expiry_csrf_throttling_and_post_only(self):
        payload = {'author_name': '가상 작성자', 'kind': 'evidence', 'body': '가상 자료'}
        for method in ('get', 'post'):
            response = getattr(self.client, method)('/prepare/events/T01/comments/', payload)
            self.assertIn(response.status_code, (302, 405))
        self.assertEqual(PreparationComment.objects.count(), 0)
        with patch('portal.preparation.limit', return_value=False):
            self.assertEqual(self.login().status_code, 429)
            self.assertNotIn(SESSION_KEY, self.client.session)
        secure = Client(enforce_csrf_checks=True)
        self.assertEqual(self.login(secure).status_code, 403)
        secure.get('/prepare/')
        token = secure.cookies['csrftoken'].value
        response = secure.post('/prepare/', {'name': '준비위원', 'phone': '01011111111', 'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(secure.post('/prepare/events/T01/comments/', payload).status_code, 403)
        self.assertEqual(secure.post('/prepare/logout/').status_code, 403)
        self.assertEqual(secure.get('/prepare/events/T01/comments/').status_code, 405)
        session = secure.session
        session[SESSION_KEY] = timezone.now().timestamp() - 1
        session.save()
        self.assertRedirects(secure.get('/prepare/events/T01/'), '/prepare/', fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, secure.session)

    def test_comments_are_persistent_separate_escaped_and_event_specific(self):
        self.login()
        payload = {'author_name': '가상 작성자', 'kind': 'evidence', 'source_reference': '가상 문서 3쪽', 'body': '<script>fictional()</script> 가상 자료'}
        response = self.client.post('/prepare/events/T71/comments/', payload)
        item = PreparationComment.objects.get()
        self.assertRedirects(response, f'/prepare/events/T71/#prepare-comment-{item.pk}', fetch_redirect_response=False)
        self.assertEqual(item.reading_key, 'T71')
        self.assertEqual(CaseComment.objects.count(), 0)
        response = self.client.get('/prepare/events/T71/')
        self.assertContains(response, '&lt;script&gt;fictional()&lt;/script&gt;')
        self.assertNotContains(response, '<script>fictional()</script>')
        self.assertNotContains(self.client.get('/prepare/events/T41/'), '가상 자료')
        self.client.post('/prepare/logout/')
        self.login()
        self.assertContains(self.client.get('/prepare/events/T71/'), '가상 자료')
        item.hidden = True
        item.save()
        self.assertNotContains(self.client.get('/prepare/events/T71/'), '가상 자료')
        self.assertEqual(self.client.get('/prepare/events/E01/').status_code, 404)
        self.assertEqual(self.client.post('/prepare/events/T99/comments/', payload).status_code, 404)
        payload['author_name'] = ' '
        self.assertEqual(self.client.post('/prepare/events/T01/comments/', payload).status_code, 400)
        self.assertEqual(PreparationComment.objects.count(), 1)

    def test_filters_working_draft_and_snapshot_do_not_modify_existing_opinion(self):
        self.login()
        source = Path(__file__).parent / 'templates/portal/integrated_case_reading.html'
        before = source.read_bytes()
        PreparationReview.objects.create(reading_key='T71', status='reviewing', evidence_notes='가상 확보 기록', revised_draft='가상 수정 초안')
        response = self.client.get('/prepare/?status=reviewing')
        self.assertEqual([row['key'] for row in response.context['rows']], ['T71'])
        self.assertContains(response, '가상 수정 초안')
        self.assertEqual([row['key'] for row in self.client.get('/prepare/?q=T71').context['rows']], ['T71'])
        self.assertContains(self.client.get('/prepare/events/T71/'), '가상 확보 기록')
        self.assertEqual(before, source.read_bytes())
        data = preparation_data()
        self.assertEqual(tuple(row['key'] for row in data['entries']), TIMELINE_KEYS)
        self.assertEqual(data['entries'][40]['key'], 'T71')
        self.assertEqual(data['entries'][41]['key'], 'T41')
        self.assertEqual(data['timeline_sha256'], hashlib.sha256(before).hexdigest())
        for row in data['entries']:
            self.assertTrue(row['original_opinion'] and row['evidence_plan'] and row['draft_suggestion'])
            self.assertEqual(hashlib.sha256(row['original_opinion'].encode()).hexdigest(), row['original_opinion_sha256'])
            self.assertIn('원문 직접 대조 전', row['appeal_basis'])
        # Independently compare every original paragraph with the source HTML.
        from html import unescape
        for article in re.findall(r'<article\b.*?</article>', before.decode(), re.S):
            key = re.search(r'data-key="(T\d+)"', article).group(1)
            opinion = re.search(r'<div class="opinion-draft" data-opinion="[^"]+">(.*?)</div>', article, re.S).group(1)
            paragraphs = [unescape(re.sub(r'<[^>]+>', '', paragraph)).strip() for paragraph in re.findall(r'<p>(.*?)</p>', opinion, re.S)]
            row = next(row for row in data['entries'] if row['key'] == key)
            self.assertEqual(row['original_opinion'], '\n\n'.join(paragraphs))
