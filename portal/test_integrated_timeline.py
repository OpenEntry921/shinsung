"""No real excerpts in fixtures or failure messages. Verify source fidelity privately."""
import hashlib
import re
import tempfile
from pathlib import Path
from html import unescape
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import connection
from django.test import TestCase,SimpleTestCase,TransactionTestCase,override_settings
from django.contrib.auth.models import User
from .models import Member,CaseComment,Case,Post,Request,Document
from .testing import member_session
from .reading_registry import reading_entries,legacy_reading_entries,TIMELINE_KEYS,READING_KEYS,TimelineMetadata
from scripts.prepare_integrated_timeline import parse_document,render


def fictional_md():
    # Exactly 28 fictional catalog entries; preserve distinct A11 vs A11변경.
    codes=[f'A{i:02}' for i in range(1,26)]+['A11변경','B01','C02']
    entries=[]
    for i in range(1,73):
        code='A11변경' if i%2 else 'A11'
        entries.append(f'### {i:02} 가상 제목 {i} & 검토\n\n사건 구분: 가상 분류\n\n**날짜**: 가상 기간 {i}\n\n**경과**: 가상 주장 <script>fictional()</script>\n\n**관련 규정**: 가상 설명 · 공식 원문 확인 필요\n\n**쟁점**: 가상 미확인 사항\n\n근거 자료: {code} PDF 1~2쪽\n')
    catalog='\n'.join(f'- **{code}**: 가상 경로/{code}.{ "jpg" if code=="C02" else "pdf"} — 2쪽' for code in codes)
    from .timeline_revision import OLD_TO_REVISED
    mapping='\n'.join(f'| {old:02} | {new:02} | 유지 |' for old,new in OLD_TO_REVISED.items())
    mapping+='\n| 신규 기사 | 41 | 신규 추가 |\n| 신규 탄원 준비 | 72 | 신규 추가 |'
    return '# 가상 검증\n\n검토 기준일 2026년 11월 4일\n\n## 통합 사건 열람\n\n'+'\n'.join(entries)+'\n## 근거 자료 목록\n\n'+catalog+'\n- **S01**: fictional.docx — 가상 2차 정리본\n\n## 개정 내역\n\n### 기존 번호와 개정 번호 대응\n\n'+mapping+'\n'


class ConversionTests(SimpleTestCase):
    def test_deterministic_exact_fields_order_sources_and_escaping(self):
        source=fictional_md();entries,catalog=parse_document(source)
        self.assertEqual(tuple(e['key'] for e in entries),TIMELINE_KEYS)
        self.assertEqual(len(catalog),29)
        result=render(entries,hashlib.sha256(source.encode()).hexdigest())
        self.assertEqual(result,render(entries,hashlib.sha256(source.encode()).hexdigest()))
        self.assertFalse('<script>fictional()' in result)
        parser=TimelineMetadata();parser.feed(result)
        self.assertEqual(parser.entries[0]['title'],entries[0]['title'])
        self.assertEqual(parser.entries[0]['sources'],['A11변경'])
        self.assertEqual(parser.entries[1]['sources'],['A11'])
        self.assertEqual(result.count('class="reading-area"'),288)
        self.assertTrue('&lt;script&gt;fictional()&lt;/script&gt;' in result)
    def test_reject_missing_duplicate_invalid_reference_page_or_template_code(self):
        for source in (fictional_md().replace('### 70 ','### 69 '),
                       fictional_md().replace('A11변경 PDF 1~2쪽','Z99 PDF 1~2쪽',1),
                       fictional_md().replace('PDF 1~2쪽','PDF 1~3쪽',1),
                       fictional_md().replace('가상 미확인 사항','{{ unsafe }}',1)):
            with self.assertRaises(ValueError):parse_document(source)


@override_settings(SECURE_SSL_REDIRECT=False)
class IntegratedReadingTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상 통합 검증',phone='01000000000',synthetic=True)
        member_session(self.client,self.member)
    def test_all_seventy_two_once_exact_display_order_and_no_case_db_required(self):
        response=self.client.get('/');html=response.content.decode()
        self.assertEqual(response.status_code,200)
        timeline=html.split('<ol class="timeline">',1)[1].split('</ol>',1)[0]
        keys=re.findall(r'href="/cases/material/(T\d{2})/"',timeline)
        self.assertEqual(tuple(keys),TIMELINE_KEYS)
        self.assertEqual(Case.objects.count(),0)
        self.assertFalse('class="case-group direct-case"' in html)
        self.assertFalse('name="q"' in html or 'name="body"' in html)
        for key in TIMELINE_KEYS:
            response=self.client.get(f'/cases/material/{key}/');body=response.content.decode()
            self.assertEqual(response.status_code,200)
            self.assertEqual(re.findall(r'id="material-(T\d{2})"',body),[key])
            self.assertEqual(body.count('class="reading-area"'),4)
            for heading in ('① 날짜','② 경과','③ 관련 규정','④ 쟁점'):self.assertEqual(body.count(heading),1)
            self.assertTrue('2026년 11월 4일' in body)
            self.assertTrue('원문 보기(개인정보 가림)' in body or '개인정보 가림 사본 연결 확인 필요' in body or '이번 공개 자료에 미포함' in body)
            self.assertFalse(re.search(r'href="[^"]*/documents/',body))
            self.assertTrue('성도님의 목소리' in body)  # Shared header still present.
            self.assertTrue('no-store' in response['Cache-Control'])
        self.assertEqual(tuple(e['key'] for e in reading_entries()),TIMELINE_KEYS)
    def test_legacy_threads_posts_requests_and_direct_links_never_move(self):
        old=CaseComment.objects.create(member=self.member,author_name=self.member.name,reading_key='E01',body='가상 과거 의견')
        post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 이전 글',body='가상 보존',reading_key='E01')
        item=Request.objects.create(member=self.member,kind='correction',reading_key='E01',comment=old,body='가상 정정')
        for key in ('E01','E30'):
            self.assertEqual(self.client.get(f'/cases/material/{key}/').status_code,200)
        self.assertRedirects(self.client.get('/cases/1/'),'/cases/material/E01/',fetch_redirect_response=False)
        self.assertFalse('가상 과거 의견' in self.client.get('/cases/material/T01/').content.decode())
        self.assertTrue('가상 과거 의견' in self.client.get('/cases/material/E01/').content.decode())
        self.assertEqual(self.client.post('/comments/T01/',{'body':'가상 새 의견'}).status_code,302)
        self.assertEqual(CaseComment.objects.get(pk=old.pk).reading_key,'E01')
        self.assertEqual(Post.objects.get(pk=post.pk).reading_key,'E01')
        self.assertEqual(Request.objects.get(pk=item.pk).comment_id,old.pk)
        self.assertEqual(CaseComment.objects.filter(reading_key='T01').count(),1)
        self.assertEqual(len(legacy_reading_entries()),30)
    def test_guest_inactive_unknown_files_and_cross_event_reply_protection(self):
        self.assertEqual(self.client.get('/cases/material/T73/').status_code,404)
        old=CaseComment.objects.create(member=self.member,author_name=self.member.name,reading_key='E01',body='가상 경계')
        self.assertEqual(self.client.post('/comments/T01/',{'body':'가상 답글','parent':old.pk}).status_code,400)
        self.member.active=False;self.member.save()
        for path in ('/','/cases/archive/','/cases/material/T01/','/cases/material/T70/','/portal/templates/portal/integrated_case_reading.html'):
            response=self.client.get(path);self.assertEqual(response.status_code,302)
            self.assertFalse('material-T01' in response.content.decode())


@override_settings(SECURE_SSL_REDIRECT=False)
class SourceProtectionTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_ROOT=self.temp.name);self.override.enable();self.addCleanup(self.override.disable)
        self.member=Member.objects.create(name='가상 자료 검증',phone='01000000000',synthetic=True)
        member_session(self.client,self.member)
        self.user=User.objects.create(username='fictional-source-author')
        self.case=Case.objects.create(title='가상 자료 연결',topic='가상',occurred_precision='unknown',author=self.user)
        self.document=Document.objects.create(case=self.case,title='가상 파일.pdf',source='가상 확인',acquired_on='2026-01-01',excerpt='가상',original='originals/fictitious.pdf')
        self.document.reading.save('fictitious.pdf',ContentFile(b'%PDF-1.4 fictional reading only'))
        Document.objects.filter(pk=self.document.pk).update(state='published',redaction_checked=True)
        Case.objects.filter(pk=self.case.pk).update(state='published')
    def test_only_explicit_published_redacted_existing_reading_copy_and_no_original(self):
        from .timeline_sources import document_links
        with patch('portal.timeline_sources.SOURCE_DOCUMENT_IDS',{'A11':self.document.pk}), patch('portal.public_case_documents.public_links',return_value={'public_unavailable':True}):
            self.assertEqual(document_links(['A11'])['A11'].pk,self.document.pk)
            html=self.client.get('/cases/material/T07/').content.decode()
            self.assertTrue(f'/documents/{self.document.pk}/reading/' in html)
            self.assertFalse(f'/documents/{self.document.pk}/original/' in html)
            response=self.client.get(f'/documents/{self.document.pk}/reading/')
            self.assertEqual(response.status_code,200);response.close()
            self.assertEqual(self.client.get(f'/documents/{self.document.pk}/original/').status_code,403)
            self.client.logout();self.assertEqual(self.client.get(f'/documents/{self.document.pk}/reading/').status_code,403)
            Document.objects.filter(pk=self.document.pk).update(redaction_checked=False)
            self.assertEqual(document_links(['A11']),{})
        Document.objects.filter(pk=self.document.pk).update(redaction_checked=True)
        with patch('portal.timeline_sources.SOURCE_DOCUMENT_IDS',{'A11':self.document.pk,'A11변경':self.document.pk}):
            self.assertEqual(document_links(['A11','A11변경']),{})
        self.document.reading.delete(save=False)
        with patch('portal.timeline_sources.SOURCE_DOCUMENT_IDS',{'A11':self.document.pk}), patch('portal.public_case_documents.public_links',return_value={'public_unavailable':True}):
            self.assertEqual(document_links(['A11']),{})

    def test_admin_body_permission_does_not_imply_member_reading_download_permission(self):
        from django.contrib.auth.models import Permission
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename='view_case',content_type__app_label='portal'))
        self.client.logout();self.client.force_login(self.user)
        from django.utils import timezone
        session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        with patch('portal.timeline_sources.SOURCE_DOCUMENT_IDS',{'A11':self.document.pk}), patch('portal.public_case_documents.public_links',return_value={'public_unavailable':True}):
            response=self.client.get('/cases/material/T07/')
            self.assertEqual(response.status_code,200)
            self.assertFalse(f'/documents/{self.document.pk}/reading/' in response.content.decode())


class TimelineMigrationTests(TransactionTestCase):
    def test_only_key_choices_expand_and_old_ids_connections_survive(self):
        from django.db.migrations.executor import MigrationExecutor
        before=('portal','0013_alter_member_options_member_legacy_operator');after=('portal','0016_community_tasks_label')
        executor=MigrationExecutor(connection);executor.migrate([before])
        try:
            apps=executor.loader.project_state([before]).apps
            member=apps.get_model('portal','Member').objects.create(name='가상 이전 교인',phone='01000000000',legacy_operator=True)
            comment=apps.get_model('portal','CaseComment').objects.create(member_id=member.pk,author_name=member.name,reading_key='E01',body='가상 연결 보존')
            item=apps.get_model('portal','Request').objects.create(member_id=member.pk,reading_key='E01',comment_id=comment.pk,kind='report',body='가상 요청')
        finally:
            MigrationExecutor(connection).migrate([after])
        self.assertTrue(Member.objects.get(pk=member.pk).legacy_operator)
        self.assertEqual(CaseComment.objects.get(pk=comment.pk).reading_key,'E01')
        self.assertEqual(Request.objects.get(pk=item.pk).comment_id,comment.pk)
        CaseComment.objects.create(member_id=member.pk,author_name='가상',reading_key='T70',body='가상 새 번호')
        self.assertEqual(CaseComment.objects.count(),2)
