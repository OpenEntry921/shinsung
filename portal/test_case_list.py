"""Security and structure assertions do not copy confidential excerpts into tests."""
import tempfile
from pathlib import Path
from django.test import TestCase, override_settings
from django.contrib.auth.models import User, Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from .models import Member, Case, Article, Document, Post

@override_settings(DEV=False,APP_MODE='production',SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
class DirectHTMLReadingTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        self.editor=User.objects.create_user('fictitious-admin',is_staff=True)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        setting=override_settings(MEDIA_ROOT=Path(self.temp.name));setting.enable();self.addCleanup(setting.disable)
        self.login()
    def login(self):
        session=self.client.session;session['member_auth']='roster';session['member_id']=str(self.member.pk);session['member_version']=self.member.session_version;session.save()
    def test_all_thirty_entries_four_sections_no_material_queries_or_file(self):
        post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 글',body='보존')
        self.assertEqual((Case.objects.count(),Article.objects.count(),Document.objects.count()),(0,0,0))
        self.assertFalse(list(Path(self.temp.name).iterdir()))
        with CaptureQueriesContext(connection) as queries:response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        html=response.content.decode()
        self.assertEqual(html.count('class="case-group direct-case"'),30)
        self.assertEqual(html.count('class="reading-area"'),120)
        for i in range(1,31):
            self.assertIn(f'id="material-E{i:02}"',html)
        for section in ('① 날짜','② 사건 내용','③ 관련 헌법 조문','④ 판결 설명 및 우리의 의견'):
            self.assertEqual(html.count(section),30)
        for token in ('<script','<details','<input','<select'):
            if token=='<input':continue # Existing CSRF token is part of the logout menu.
            self.assertNotIn(token,html)
        forbidden=('portal_case','portal_article','portal_document','portal_reviewedmaterialimport','portal_registeredmaterialcase','portal_decision')
        self.assertFalse(any(any(t in q['sql'].lower() for t in forbidden) for q in queries.captured_queries))
        self.assertEqual(Post.objects.get().member_id,self.member.pk)
        self.assertIn('no-store',response['Cache-Control']);self.assertIn('private',response['Cache-Control'])
    def test_guest_inactive_direct_links_and_files_protected(self):
        self.client.logout()
        for url in ('/','/cases/1/','/cases/material/E30/','/portal/templates/portal/direct_case_reading.html'):
            response=self.client.get(url);self.assertEqual(response.status_code,302);self.assertNotIn('material-E01',response.content.decode())
        self.login();self.member.active=False;self.member.save();self.assertEqual(self.client.get('/').status_code,302)
    def test_direct_links_and_no_search(self):
        for i in (1,30):
            self.assertRedirects(self.client.get(f'/cases/{i}/'),f'/#material-E{i:02}',fetch_redirect_response=False)
            self.assertRedirects(self.client.get(f'/cases/material/E{i:02}/'),f'/#material-E{i:02}',fetch_redirect_response=False)
        self.assertEqual(self.client.get('/cases/material/invalid/').status_code,404)
        self.assertContains(self.client.get('/?q=ignored'),'material-E30')
    def test_admin_mfa_and_demo_auth(self):
        self.client.logout();self.client.force_login(self.editor)
        self.assertEqual(self.client.get('/').status_code,302)
        self.editor.user_permissions.add(Permission.objects.get(codename='view_case'))
        session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        self.assertEqual(self.client.get('/').status_code,200)
        self.client.logout();self.login()
        with override_settings(DEV=True,APP_MODE='development'):
            self.assertEqual(self.client.get('/').status_code,200)
            self.assertEqual(self.client.post('/logout/').status_code,302)
