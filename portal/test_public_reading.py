"""Public reads must not widen private member, operator or preparation access."""
import tempfile
from unittest.mock import patch
from django.contrib.auth.models import User, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import (
    Member, Case, Document, CaseComment, Post, Request, AccessApplication,
    Challenge, PreparationComment, Revision, Audit,
)
from .testing import member_session


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False)
class PublicReadingTests(TestCase):
    def test_all_entries_direct_refresh_head_mobile_and_no_private_ui(self):
        from .reading_registry import reading_entries
        entries = reading_entries()
        self.assertEqual(len(entries), 72)
        for method in (self.client.get, self.client.head):
            home = method('/')
            self.assertEqual(home.status_code, 200)
            self.assertEqual(home['X-Robots-Tag'], 'noindex, nofollow')
        home = self.client.get('/')
        self.assertEqual(home.content.count(b'class="timeline-card"'), 72)
        for text in ('공동 상황판', '해결 절차 로드맵'):
            self.assertContains(home, text)
        for entry in entries:
            path = f'/cases/material/{entry["key"]}/'
            for _ in range(2):
                response = self.client.get(path, HTTP_USER_AGENT='Mobile')
                self.assertEqual(response.status_code, 200, path)
                self.assertContains(response, '⑤ 우리의 의견')
            for text in ('/prepare', '/login/', '/apply/', '/exception/', '/posts/', '/requests/',
                         'name="phone"', '의견 등록', '교인 로그인', '로그아웃'):
                self.assertNotContains(response, text)
        self.assertEqual(Member.objects.count(), 0)
        self.assertNotIn('member_id', self.client.session)
        self.assertEqual(self.client.get('/cases/archive/').status_code, 200)
        self.assertEqual(self.client.head('/cases/material/E01/').status_code, 200)

    def test_retired_auth_does_not_collect_pii_authenticate_or_touch_preparation(self):
        member = Member.objects.create(name='가상 운영자', phone='01000000000', synthetic=True, legacy_operator=True)
        until = timezone.now().timestamp() + 1800
        session = self.client.session
        session['preparation_until'] = until
        session.save()
        before = {model: model.objects.count() for model in (Member, Challenge, AccessApplication, Audit)}
        with patch('portal.views.limit') as limiter, patch('portal.security.requests.post') as sender:
            for path in ('/login/', '/apply/', '/otp/', '/exception/'):
                for method in (self.client.get, self.client.head, self.client.post):
                    response = method(path, {'name':member.name, 'phone':member.phone, 'token':'unused'})
                    self.assertRedirects(response, '/', fetch_redirect_response=False)
                    self.assertEqual(self.client.session['preparation_until'], until)
                    self.assertNotIn('member_id', self.client.session)
            limiter.assert_not_called()
            sender.assert_not_called()
        for model, count in before.items():
            self.assertEqual(model.objects.count(), count)
        self.assertContains(self.client.get('/policy/'), '로그인과 개인정보 입력 없이')

    def test_invalid_member_sessions_and_logout_preserve_preparation(self):
        member = Member.objects.create(name='가상', phone='01000000000', synthetic=True)
        for mid in ('bad-uuid', str(member.pk)):
            session = self.client.session
            until = timezone.now().timestamp() + 1200
            session.update(dict(member_id=mid, member_auth='roster', member_version=0, preparation_until=until))
            session.save()
            self.assertEqual(self.client.get('/').status_code, 200)
            self.assertNotIn('member_id', self.client.session)
            self.assertEqual(self.client.session['preparation_until'], until)
            self.assertRedirects(self.client.post('/logout/'), '/', fetch_redirect_response=False)
            self.assertEqual(self.client.session['preparation_until'], until)
            self.assertEqual(self.client.get('/prepare/events/').status_code, 200)
        # Revoked/expired strong member authentication must also preserve preparation.
        for expiry in (0, 'invalid'):
            member_session(self.client, member)
            session = self.client.session
            session['identity_until'] = expiry
            session['preparation_until'] = until
            session.save()
            self.assertEqual(self.client.get('/cases/material/T01/').status_code, 200)
            self.assertNotIn('member_id', self.client.session)
            self.assertEqual(self.client.session['preparation_until'], until)

    def test_private_content_does_not_appear_and_anonymous_writes_are_denied(self):
        member = Member.objects.create(name='비공개작성자', phone='01000000000', synthetic=True)
        comment = CaseComment.objects.create(member=member, author_name=member.name, reading_key='T01', body='비공개댓글')
        CaseComment.objects.create(member=member, author_name=member.name, reading_key='T01', body='숨김댓글', hidden=True)
        CaseComment.objects.create(member=member, author_name=member.name, reading_key='T01', body='삭제댓글', deleted_at=timezone.now())
        post = Post.objects.create(member=member, author_name=member.name, title='비공개게시물', body='비공개본문')
        item = Request.objects.create(member=member, reading_key='T01', kind='response', body='비공개요청',
                                      public_excerpt='승인된공개발췌', public_approved=True)
        Request.objects.create(member=member, reading_key='T01', kind='response', body='미승인요청', public_excerpt='미승인발췌')
        PreparationComment.objects.create(reading_key='T01', author_name='내부', kind='other', body='준비내부의견')
        paths = ('/posts/', f'/posts/{post.pk}/', '/posts/new/', f'/posts/{post.pk}/edit/',
                 f'/posts/{post.pk}/delete/', '/requests/', f'/comment-link/{comment.pk}/',
                 '/comments/T01/', f'/comments/T01/{comment.pk}/')
        before = (Post.objects.count(), CaseComment.objects.count(), Request.objects.count(), Revision.objects.count())
        for path in paths:
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(path, {'body':'위조', 'title':'위조', 'action':'delete', 'member':str(member.pk)}).status_code, 403, path)
        for path in ('/', '/cases/material/T01/', '/cases/archive/', '/policy/'):
            response = self.client.get(path)
            for text in ('비공개작성자', '비공개댓글', '숨김댓글', '삭제댓글', '비공개게시물', '비공개요청',
                         '미승인발췌', '준비내부의견', member.phone, '/prepare'):
                self.assertNotContains(response, text)
        self.assertContains(self.client.get('/cases/material/T01/'), item.public_excerpt)
        self.assertEqual(before, (Post.objects.count(), CaseComment.objects.count(), Request.objects.count(), Revision.objects.count()))
        member_session(self.client, member)
        self.assertContains(self.client.get('/cases/material/T01/'), comment.body)
        self.assertContains(self.client.get('/posts/'), post.title)
        self.assertContains(self.client.get('/requests/'), item.body)
        secure = Client(enforce_csrf_checks=True)
        self.assertEqual(secure.post('/comments/T01/', {'body':'위조'}).status_code, 403)

    def test_reading_files_keep_all_publication_guards_and_original_permissions(self):
        user = User.objects.create_user('fictional-staff', is_staff=True)
        case = Case.objects.create(title='가상', topic='가상', author=user, state='published')
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            doc = Document.objects.create(case=case, title='가상문서', source='가상', acquired_on='2026-01-01', state='published', redaction_checked=True,
                original=SimpleUploadedFile('original.pdf', b'private-original'),
                reading=SimpleUploadedFile('reading.pdf', b'%PDF-public'))
            Case.objects.filter(pk=case.pk).update(state='published')
            path = f'/documents/{doc.pk}/reading/'
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-public')
            self.assertEqual(self.client.head(path).status_code, 200)
            self.assertEqual(self.client.post(path).status_code, 403)
            for field, value in (('internal_memo', True), ('state', 'draft'), ('redaction_checked', False)):
                old = getattr(doc, field)
                Document.objects.filter(pk=doc.pk).update(**{field:value})
                self.assertEqual(self.client.get(path).status_code, 403, field)
                Document.objects.filter(pk=doc.pk).update(**{field:old})
            case.state='draft'; case.save()
            self.assertEqual(self.client.get(path).status_code, 403)
            case.state='published'; case.save()
            Document.objects.filter(pk=doc.pk).update(reading='missing-reading.pdf')
            self.assertEqual(self.client.get(path).status_code, 404)
            Document.objects.filter(pk=doc.pk).update(reading='')
            self.assertEqual(self.client.get(path).status_code, 404)
            original = f'/documents/{doc.pk}/original/'
            self.assertEqual(self.client.get(original).status_code, 403)
            self.client.force_login(user)
            self.assertEqual(self.client.get(original).status_code, 403)
            session=self.client.session; session['admin_mfa_until']=timezone.now().timestamp()+300; session.save()
            self.assertEqual(self.client.get(original).status_code, 403)
            user.user_permissions.add(Permission.objects.get(codename='view_document'))
            response = self.client.get(original)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'private-original')

    def test_only_explicit_reads_are_public_and_admin_keeps_mfa(self):
        for path in ('/', '/cases/archive/', '/cases/material/T01/', '/policy/', '/health/'):
            self.assertEqual(self.client.post(path, {'body':'위조'}).status_code, 403)
        for path in ('/admin/', '/admin-mfa/', '/roster/', '/exception-issue/', '/materials/import/'):
            self.assertRedirects(self.client.get(path), '/admin/login/', fetch_redirect_response=False)
        user=User.objects.create_user('fictional-admin', is_staff=True)
        self.client.force_login(user)
        self.assertRedirects(self.client.get('/roster/'), '/admin-mfa/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/prepare/events/'), '/prepare/', fetch_redirect_response=False)
        self.assertEqual(self.client.post('/comments/T01/', {'body':'위조'}).status_code, 403)
