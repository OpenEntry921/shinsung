"""Only fictional documents and identities; never the user's source or manifest."""
import copy,hashlib,io,json,tempfile,zipfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth.models import User,Permission
from django.core.exceptions import ValidationError
from .models import Case,Article,Document,Member,Post,ReviewedMaterialImport,RegisteredMaterialCase
from .reviewed_materials import register,ImportRejected

class ReviewedMaterialTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.override=override_settings(APP_MODE='production',DEV=False,DATA_DIR=self.directory,MEDIA_ROOT=self.directory/'private',PRIVATE_STORAGE_CONFIRMED=True,REAL_MATERIALS_ENABLED=True,SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
        self.override.enable();self.addCleanup(self.override.disable)
        self.author=User.objects.create(username='fictitious-material-editor',is_staff=True)
        self.reviewer=User.objects.create(username='fictitious-material-reviewer',is_staff=True)
        self.author.user_permissions.add(Permission.objects.get(codename='add_case'))
        self.reviewer.user_permissions.add(Permission.objects.get(codename='publish_case'))
        self.member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        self.post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 기존 글',body='보존 확인')
        self.source=self.directory/'fictitious.docx'
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>1. 가상 연표</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>일자</w:t></w:r></w:p></w:tc></w:tr><w:tr><w:tc><w:p><w:r><w:t>날짜 미확인</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>가상 원문 발췌</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><w:r><w:t>5. 내부 전략</w:t></w:r></w:p><w:p><w:r><w:t>공개하지 않는 가상 전략</w:t></w:r></w:p></w:body></w:document>'
        with zipfile.ZipFile(self.source,'w') as z:z.writestr('word/document.xml',xml)
        self.plan=dict(key='fictional-edition',reviewed=True,basis_on='2001-01-01',source_filename='fictitious.docx',source_title='가상 검토 문서',source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),cases=[dict(key='E01',title='가상 사건',topic='가상',overview='가상 편집자 설명',occurred_precision='unknown',source_locator='가상 제1절 표2행',locations=['b2:r2'],issues='가상 추가 확인 쟁점',statements=[dict(kind='unknown',presentation='quotation',text='가상 원문 발췌',location='b2:r2',source_label='가상 표2행')])],rules=[dict(citation='가상 제999조 후보',description='가상 검토 문서의 설명',case_keys=['E01'],locations=['b2:r2'],source_label='가상 표2행',relevance='가상 관련 이유')])
        self.manifest=self.directory/'test.review.json';self.write()
    def write(self):self.manifest.write_text(json.dumps(self.plan,ensure_ascii=False))
    def run_import(self,**kwargs):return register(self.source,self.manifest,self.author.username,self.reviewer.username,reason='가상 편집 검토 승인',**kwargs)
    def member_session(self):
        session=self.client.session;session['member_auth']='roster';session['member_id']=str(self.member.pk);session['member_version']=self.member.session_version;session.save()
    def test_preview_and_atomic_published_registration(self):
        self.assertEqual(self.run_import()['create_cases'],1);self.assertEqual(Case.objects.count(),0)
        result=self.run_import(apply=True,publish=True);self.assertEqual(result['published_cases'],1)
        self.assertEqual(Document.objects.get().state,'draft');self.assertTrue(Document.objects.get().internal_memo)
        self.assertFalse(Article.objects.get().verified);self.assertEqual(RegisteredMaterialCase.objects.get().verification,'memo_only')
        self.assertTrue(Member.objects.filter(pk=self.member.pk).exists());self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
    def test_repeat_preserves_ids_admin_edits_and_withdrawal(self):
        self.run_import(apply=True,publish=True);case=Case.objects.get();case.overview='관리자가 수정한 가상 내용';case.state='review';case.save()
        result=self.run_import(apply=True,publish=True)
        case.refresh_from_db();self.assertEqual(case.overview,'관리자가 수정한 가상 내용');self.assertEqual(case.state,'review');self.assertEqual(result['create_cases'],0)
        self.assertEqual((Case.objects.count(),Article.objects.count(),Document.objects.count()),(1,1,1))
    def test_rollback_and_private_file_cleanup(self):
        with patch('portal.reviewed_materials.Article.full_clean',side_effect=ValidationError('가상 실패')):
            with self.assertRaises(ValidationError):self.run_import(apply=True,publish=True)
        self.assertEqual(Case.objects.count(),0);self.assertEqual(Document.objects.count(),0);self.assertEqual(ReviewedMaterialImport.objects.count(),0)
        self.assertFalse(any(p.is_file() for p in (self.directory/'private').rglob('*')))
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
    def test_modified_manifest_rejected_without_overwrite(self):
        self.run_import(apply=True,publish=True);self.plan['cases'][0]['overview']='다른 내용';self.write()
        with self.assertRaises(ImportRejected):self.run_import(apply=True,publish=True)
        self.assertEqual(Case.objects.get().overview,'가상 편집자 설명')
    def test_strategy_locations_and_false_fact_claims_rejected(self):
        self.plan['cases'][0]['locations']=['b4'];self.write()
        with self.assertRaises(ImportRejected):self.run_import()
        self.plan['cases'][0]['locations']=['b2:r2'];self.plan['cases'][0]['statements'][0]['kind']='fact';self.write()
        with self.assertRaises(ImportRejected):self.run_import()
    def test_development_and_unapproved_publication_blocked(self):
        with override_settings(APP_MODE='development',DEV=True):
            with self.assertRaises(ImportRejected):self.run_import(apply=True,publish=True)
        self.reviewer.user_permissions.clear()
        with self.assertRaises(ImportRejected):self.run_import(apply=True,publish=True)
        self.assertEqual(Case.objects.count(),0)
    def test_db_import_does_not_control_fixed_member_body(self):
        self.run_import(apply=True,publish=True);self.member_session()
        response=self.client.get('/')
        self.assertNotContains(response,'가상 원문 발췌')
        self.assertContains(response,'material-E01')
        self.assertNotContains(response,'검색 조건 초기화')
    def test_original_guest_inactive_and_direct_link_protection(self):
        self.run_import(apply=True,publish=True);case=Case.objects.get();doc=Document.objects.get()
        for url in ('/',f'/cases/{case.pk}/',f'/documents/{doc.pk}/original/',f'/documents/{doc.pk}/reading/'):
            response=self.client.get(url);self.assertIn(response.status_code,(302,403));self.assertNotIn('가상 원문 발췌',response.content.decode())
        self.member_session();self.assertEqual(self.client.get(f'/documents/{doc.pk}/original/').status_code,403);self.assertEqual(self.client.get(f'/documents/{doc.pk}/reading/').status_code,403)
        Member.objects.filter(pk=self.member.pk).update(active=False);self.assertEqual(self.client.get('/').status_code,302)

    def test_source_edit_requires_revalidation_and_preserves_withdrawal(self):
        self.run_import(apply=True,publish=True)
        doc=Document.objects.get();doc.source='관리자가 정정한 가상 출처';doc.save()
        case=Case.objects.get();self.assertEqual(case.state,'review')
        result=self.run_import(apply=True,publish=True)
        self.assertEqual(result['published_cases'],0)
        self.assertEqual(Document.objects.get().source,'관리자가 정정한 가상 출처')

    def test_changed_original_blocks_publication_until_source_rechecked(self):
        from .case_services import publication_errors
        self.run_import(apply=True,publish=True)
        doc=Document.objects.get()
        with open(doc.original.path,'wb') as stream:stream.write(b'fictitious altered source')
        self.assertTrue(any('현재 원본이 다릅니다' in error for error in publication_errors(Case.objects.get())))

    def test_same_source_under_new_key_cannot_duplicate_cases(self):
        self.run_import(apply=True,publish=True)
        self.plan['key']='different-fictitious-key';self.write()
        with self.assertRaises(ImportRejected):self.run_import(apply=True,publish=True)
        self.assertEqual(Case.objects.count(),1)

    def test_roster_session_does_not_expose_missing_api_after_mode_change(self):
        self.run_import(apply=True,publish=True);self.member_session();case=Case.objects.get()
        with override_settings(APP_MODE='development',DEV=True):
            for url in ('/api/posts/',):
                response=self.client.get(url);self.assertEqual(response.status_code,404);self.assertNotIn('가상 원문 발췌',response.content.decode())
