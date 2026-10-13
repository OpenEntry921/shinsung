"""Fixed reading tests contain fictional material only."""
import json
import tempfile
from pathlib import Path
from django.test import TestCase, override_settings
from django.contrib.auth.models import User, Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from .models import Member, Case, Post
from .fixed_reading import load_reading, ReadingUnavailable
from scripts.encrypt_case_reading import encrypt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import base64
from django.core.management import call_command
import io


@override_settings(DEV=False, APP_MODE='production', SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False)
class FixedReadingTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'case-reading.enc'
        self.key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        encoded=base64.b64encode(self.key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())).decode('ascii')
        self.settings_override = override_settings(CASE_READING_ENCRYPTED_PATH=self.path,CASE_READING_PRIVATE_KEY=encoded)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.member = Member.objects.create(name='가상교인', phone='01000000000', synthetic=True)
        self.editor = User.objects.create_user('fictitious-admin', is_staff=True)
        self.body = dict(version=1, reviewed=True, basis_on='2025-01-01', source_title='가상 검토 자료', source_filename='fictional-source', entries=[self.entry()])
        self.write()
        self.login()

    def entry(self, key='F01', order=None):
        return dict(key=key, title='가상 사건 '+key, order=order or [2025, 1, 2], date_label='2025년 1월 2일', ordering_note='', source='가상 표 1행', overview='가상 본문 <script>alert(1)</script>', legacy_ids=[17] if key=='F01' else [], issues='가상 쟁점', needed='가상 추가 자료', responses='가상 입장 설명', statements=[dict(kind='unknown',presentation='summary',text='가상 미확인 설명',source='가상 표 1행')], rules=[dict(citation='가상 제999조',description='가상 조항 설명',source='가상 절',relevance='가상 관련성')])

    def write(self):
        self.path.write_text(json.dumps(encrypt(json.dumps(self.body,ensure_ascii=False).encode(),self.key.public_key())))

    def login(self):
        session=self.client.session
        session['member_id']=str(self.member.pk)
        session['member_version']=self.member.session_version
        session['member_auth']='sms'
        session.save()

    def test_no_case_queries_empty_tables_and_auth_preserved(self):
        post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 글',body='가상')
        self.assertEqual(Case.objects.count(),0)
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get('/')
        self.assertContains(response,'가상 본문 &lt;script&gt;')
        forbidden=('portal_case','portal_article','portal_document','portal_reviewedmaterialimport','portal_registeredmaterialcase','portal_decision')
        self.assertFalse(any(any(table in q['sql'].lower() for table in forbidden) for q in queries.captured_queries))
        self.assertEqual(Member.objects.get().pk,self.member.pk)
        self.assertEqual(Post.objects.get().member_id,self.member.pk)
        self.assertEqual(User.objects.get().pk,self.editor.pk)
        self.assertIn('no-store',response['Cache-Control'])
        self.assertIn('private',response['Cache-Control'])

    def test_each_entry_has_four_vertical_areas_and_search_ignored(self):
        early=self.entry('F00',[2024,0,0]);early['date_label']='2024년'
        unknown=self.entry('F02');unknown.update(order=None,date_label='날짜 미확인',ordering_note='가상 원문에 날짜가 없음')
        self.body['entries'] += [unknown,early];self.write()
        response=self.client.get('/?q=없는검색&order=desc&from=bad')
        html=response.content.decode()
        self.assertLess(html.index('id="material-F00"'),html.index('id="material-F01"'))
        self.assertLess(html.index('id="material-F01"'),html.index('id="material-F02"'))
        for heading in ('① 날짜','② 사건 경과','③ 관련 교단 헌법과 규정','④ 쟁점과 추가 확인사항'):
            self.assertContains(response,heading,count=3)
        for label in ('검색 결과','검색 조건 초기화','name="q"','class="search"','<script>','class="columns"'):
            self.assertNotContains(response,label)
        self.assertContains(response,'원자료 미대조')
        self.assertContains(response,'반론 자료 미확보')
        self.assertContains(response,'순서를 확정할 수 없는 사건')

    def test_links_only_use_private_body_aliases(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertRedirects(self.client.get('/cases/17/'),'/#material-F01',fetch_redirect_response=False)
        self.assertFalse(any('portal_case' in q['sql'].lower() for q in queries.captured_queries))
        self.assertRedirects(self.client.get('/cases/material/F01/'),'/#material-F01',fetch_redirect_response=False)
        self.assertEqual(self.client.get('/cases/18/').status_code,404)
        self.assertEqual(self.client.get('/cases/material/missing/').status_code,404)

    def test_guest_inactive_logout_and_no_file_endpoint(self):
        self.client.post('/logout/')
        for url in ('/','/cases/17/','/cases/material/F01/','/private/case-reading.body','/api/cases/'):
            r=self.client.get(url);self.assertIn(r.status_code,(302,403));self.assertNotIn('가상 본문',r.content.decode())
        self.assertEqual(self.client.get('/static/case-reading.body').status_code,404)
        self.login();Member.objects.filter(pk=self.member.pk).update(active=False)
        self.assertEqual(self.client.get('/').status_code,302)

    def test_admin_needs_active_staff_view_permission_and_mfa(self):
        self.client.post('/logout/');self.client.force_login(self.editor)
        self.assertEqual(self.client.get('/').status_code,302)
        self.editor.user_permissions.add(Permission.objects.get(codename='view_case'))
        self.assertEqual(self.client.get('/').status_code,302)
        session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        self.assertContains(self.client.get('/'),'가상 본문')
        session=self.client.session;session['admin_mfa_until']=0;session.save()
        self.assertEqual(self.client.get('/cases/material/F01/').status_code,302)

    def test_demo_missing_invalid_keys_and_damaged_ciphertext(self):
        with override_settings(DEV=True,APP_MODE='development'):
            self.assertEqual(self.client.get('/').status_code,403)
        for key,code in [('', 'private_key_missing'), ('not-a-private-key', 'private_key_invalid')]:
            with override_settings(CASE_READING_PRIVATE_KEY=key):
                with self.assertRaises(ReadingUnavailable) as caught:load_reading()
                self.assertEqual(caught.exception.code,code)
                r=self.client.get('/');self.assertEqual(r.status_code,503)
                self.assertNotIn('가상 본문',r.content.decode());self.assertNotIn(key,r.content.decode()) if key else None
                output=io.StringIO()
                with self.assertRaises(SystemExit):call_command('case_reading_status',stdout=output)
                self.assertEqual(json.loads(output.getvalue())['reason'],code)
        other=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        wrong=base64.b64encode(other.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())).decode()
        with override_settings(CASE_READING_PRIVATE_KEY=wrong):
            with self.assertRaises(ReadingUnavailable) as caught:load_reading()
            self.assertEqual(caught.exception.code,'decrypt_failed')
        envelope=json.loads(self.path.read_text());damaged=bytearray(base64.b64decode(envelope['ciphertext']));damaged[0]^=1
        envelope['ciphertext']=base64.b64encode(damaged).decode();self.path.write_text(json.dumps(envelope))
        with self.assertRaises(ReadingUnavailable) as caught:load_reading()
        self.assertEqual(caught.exception.code,'decrypt_failed')
        self.path.write_text('{bad')
        with self.assertRaises(ReadingUnavailable) as caught:load_reading()
        self.assertEqual(caught.exception.code,'ciphertext_invalid')
        self.path.unlink()
        with self.assertRaises(ReadingUnavailable) as caught:load_reading()
        self.assertEqual(caught.exception.code,'ciphertext_missing')

    def test_ciphertext_and_key_are_not_public_and_no_plaintext_is_written(self):
        self.assertNotIn('가상 본문',self.path.read_text())
        before=set(Path(self.directory.name).iterdir());body=load_reading()
        self.assertEqual(set(Path(self.directory.name).iterdir()),before)
        self.assertEqual(len(body['entries']),1)
        for url in ('/server_materials/case-reading.enc','/static/server_materials/case-reading.enc'):
            r=self.client.get(url);self.assertEqual(r.status_code,404)
            self.assertNotIn('ciphertext',r.content.decode())
        self.client.logout()
        from unittest.mock import patch
        with patch('portal.fixed_reading.load_reading',side_effect=AssertionError('Unauthenticated decryption attempted')):
            self.assertEqual(self.client.get('/').status_code,302)
        self.login();output=io.StringIO();call_command('case_reading_status',stdout=output)
        report=json.loads(output.getvalue());self.assertTrue(report['ready']);self.assertEqual(report['cases'],1)
        self.assertNotIn('가상',output.getvalue())

    def test_long_text_multiple_rules_fallback_and_no_truncation(self):
        e=self.body['entries'][0];e['overview']='가상 긴 본문 '*1000+'가상 끝표시'
        e['rules'].append(dict(e['rules'][0],citation='가상 제998조'))
        second=self.entry('F02');second['rules']=[];self.body['entries'].append(second);self.write()
        r=self.client.get('/');self.assertContains(r,'가상 끝표시');self.assertContains(r,'가상 제998조');self.assertContains(r,'관련 규정 추가 확인 필요')
