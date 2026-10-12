"""No real memo, person, statute or judgment is used in these tests."""
import datetime
import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth.models import User,Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from .models import *
from .memo_import import extract_candidates,convert_candidate
from .case_services import publication_errors

@override_settings(DEV=True,APP_MODE='development',SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
class CaseReviewTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='shinsung-fictitious-review-')
        self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_ROOT=Path(self.temp.name)/'private')
        self.override.enable();self.addCleanup(self.override.disable)
        self.editor=User.objects.create_user('fictitious-editor',is_staff=True)
        self.reviewer=User.objects.create_user('fictitious-reviewer',is_staff=True)
        self.member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        self.case=Case.objects.create(title='가상 사건',topic='가상 주제',occurred_on=datetime.date(2025,2,12),author=self.editor,last_editor=self.editor)
    def publish(self,*cases):
        for case in cases or (self.case,):
            case.state='published';case.reviewer=self.reviewer;case.save()
    def login_member(self):
        session=self.client.session;session['member_id']=str(self.member.pk);session['member_version']=self.member.session_version;session.save()
    def login_staff(self,user=None,permissions=()):
        user=user or self.editor
        user.user_permissions.add(*Permission.objects.filter(codename__in=permissions))
        self.client.force_login(user);session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+600;session.save()
    def doc(self,**kwargs):
        fields=dict(case=self.case,title='가상 근거 PDF',source='가상 원자료 출처',acquired_on=datetime.date(2025,3,1),excerpt='원문 1쪽',original=SimpleUploadedFile('synthetic.pdf',b'%PDF-1.4 fictitious'),reading=SimpleUploadedFile('synthetic-reading.pdf',b'%PDF-1.4 redacted fictional'),redaction_checked=True,state='published')
        fields.update(kwargs);return Document.objects.create(**fields)
    def memo(self):
        buffer=io.BytesIO()
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        for text in ['2025년 2월 가상 카페 운영에 관하여 내부 기재만 있음. 제999조 확인 후보.', '2025년 3월 가상 카페 운영 경과 확인 필요.', '카페 협상 카드와 승리 목표는 교인용 설명에서 제외.', '2025년 4월 가상 재항고 2025가상101 원문 확인 필요.', '2025년 4월 가상 재항고 2025가상102 별도 원문 확인 필요.']:
            xml+=f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
        xml+='</w:body></w:document>'
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('word/document.xml',xml)
        return Document.objects.create(title='가상 내부 메모',source='가상 내부 출처',acquired_on=datetime.date(2026,9,19),excerpt='내부 검토용',internal_memo=True,original=SimpleUploadedFile('synthetic-memo.docx',buffer.getvalue()))
    def private_environment(self):
        return override_settings(APP_MODE='production',DEV=False,PRIVATE_STORAGE_CONFIRMED=True,REAL_MATERIALS_ENABLED=True,DATA_DIR=Path(self.temp.name)/'production',SMS_API_KEY='fictitious-test-key',SMS_API_SECRET='fictitious-test-secret',SMS_SENDER='01000000000')
    def test_partial_date_no_fabricated_day(self):
        case=Case(title='가상 월 단위',topic='가상',occurred_precision='month',occurred_year=2025,occurred_month=2,author=self.editor)
        case.full_clean();case.save();self.assertIsNone(case.occurred_on);self.assertEqual(case.date_label,'2025년 2월 (월 단위)')
        case.occurred_on=datetime.date(2025,2,1)
        with self.assertRaises(ValidationError):case.full_clean()
    def test_sort_search_and_basis_dates(self):
        monthly=Case.objects.create(title='가상 월 사건',topic='가상 월 주제',occurred_precision='month',occurred_year=2025,occurred_month=1,author=self.editor,materials_as_of=datetime.date(2026,9,19))
        unknown=Case.objects.create(title='가상 미상 사건',topic='가상',occurred_precision='unknown',author=self.editor)
        self.publish(self.case,monthly,unknown);self.login_member()
        content=self.client.get('/').content.decode();self.assertLess(content.index(monthly.title),content.index(self.case.title));self.assertLess(content.index(self.case.title),content.index(unknown.title))
        content=self.client.get('/?order=desc').content.decode();self.assertLess(content.index(self.case.title),content.index(monthly.title));self.assertLess(content.index(monthly.title),content.index(unknown.title))
        response=self.client.get('/?from=2025-01-15&to=2025-01-20&topic=월');self.assertContains(response,monthly.title);self.assertNotContains(response,self.case.title);self.assertContains(response,'2026년 9월 19일')
    def test_unknown_statute_body_not_generated_or_disclosed(self):
        Article.objects.create(case=self.case,citation='가상 제999조 확인 후보',text='공식 원문이 아닌 가상 내부 기재',relevance='관련 여부 확인 중')
        self.publish();self.login_member();response=self.client.get(f'/cases/{self.case.pk}/')
        self.assertContains(response,'조문 확인 중');self.assertNotContains(response,'공식 원문이 아닌 가상 내부 기재')
    def test_verified_statute_and_applicability_are_independent(self):
        article=Article.objects.create(case=self.case,citation='가상 검증 예시 (실제 헌법 아님)',text='가상 테스트 조문 본문',source='https://www.pck.or.kr/',amendment_source='https://www.pck.or.kr/',effective_on=datetime.date(2025,1,1),amended_on=datetime.date(2024,12,1),checked_on=datetime.date(2025,1,2),official_page='가상 1쪽',verified=True,relevance='가상 검토',applicability_status='pending')
        article.full_clean();self.publish();self.login_member();response=self.client.get(f'/cases/{self.case.pk}/')
        self.assertContains(response,'가상 테스트 조문 본문');self.assertContains(response,'사건 당시 적용: 확인 중')
        article.applicability_status='applicable';article.effective_on=datetime.date(2026,1,1);article.applicability_reason='가상 근거'
        with self.assertRaises(ValidationError):article.full_clean()
    def test_multiple_documents_articles_and_shared_decision(self):
        other=Case.objects.create(title='다른 가상 사건',topic='가상',occurred_on=datetime.date(2025,4,1),author=self.editor)
        first=self.doc(original_checked=True);second=self.doc(title='두 번째 가상 PDF')
        CaseEvidence.objects.create(case=self.case,document=first,locator='1쪽 문단 2',checked=True)
        CaseEvidence.objects.create(case=self.case,document=second,locator='증거 가상1')
        CaseEvidence.objects.create(case=other,document=first,locator='2쪽')
        Article.objects.create(case=self.case,citation='가상 조문 후보1',relevance='확인 중')
        shared=Article.objects.create(case=self.case,citation='가상 조문 후보2',relevance='확인 중');shared.related_cases.add(other)
        decision=Decision.objects.create(institution='가상 기관',case_number='가상번호',document=first);decision.cases.add(self.case,other)
        self.publish(self.case,other);self.login_member()
        response=self.client.get(f'/cases/{self.case.pk}/');self.assertContains(response,'가상 조문 후보1');self.assertContains(response,'가상 조문 후보2');self.assertContains(response,'1쪽 문단 2');self.assertContains(response,'증거 가상1');self.assertContains(response,'가상 기관')
        self.assertContains(self.client.get(f'/cases/{other.pk}/'),'가상 조문 후보2')
        self.assertEqual(decision.cases.count(),2)
    def test_fact_requires_original_and_decision_fact_specific_scope(self):
        doc=self.doc();evidence=CaseEvidence.objects.create(case=self.case,document=doc,locator='1쪽')
        statement=CaseStatement(case=self.case,kind='fact',text='가상 확인 예시',source_note='가상 출처',evidence=evidence)
        with self.assertRaises(ValidationError):statement.full_clean()
        doc.original_checked=True;doc.save();evidence.checked=True;evidence.save();statement.full_clean();statement.save()
        decision=Decision.objects.create(institution='가상 기관',case_number='가상번호',decided_on=datetime.date(2025,3,1),order='가상 주문 (실제 판결 아님)',scope='가상 일부 항목에 한정',document=doc,locator='1쪽',verified=True,outcome='excluded',finality='unknown');decision.cases.add(self.case)
        decision.full_clean();CaseStatement.objects.create(case=self.case,kind='decision_fact',text='가상 결정의 일부 항목',source_note='가상 판결문',evidence=evidence,decision=decision)
        self.publish();self.login_member();response=self.client.get(f'/cases/{self.case.pk}/')
        self.assertContains(response,'해당 결정에서 인정한 사실');self.assertContains(response,'판단 제외');self.assertContains(response,'확정 여부: 확인 중');self.assertContains(response,'가상 일부 항목에 한정')
    def test_pending_decision_never_claims_known_result(self):
        decision=Decision.objects.create(institution='가상 기관',case_number='가상번호',order='검증되지 않은 가상 주문',outcome='acquitted',finality='final');decision.cases.add(self.case)
        self.publish();self.login_member();response=self.client.get(f'/cases/{self.case.pk}/')
        self.assertContains(response,'결정 원자료 확인 중');self.assertNotContains(response,'검증되지 않은 가상 주문');self.assertNotContains(response,'결과 유형: 무죄');self.assertNotContains(response,'확정 여부: 확정')
    def test_memo_cannot_be_official_fact_or_member_download(self):
        memo=self.memo();memo.state='published';memo.redaction_checked=True
        with self.assertRaises(ValidationError):memo.full_clean()
        memo.state='draft';memo.save()
        evidence=CaseEvidence(case=self.case,document=memo,locator='문단 1',checked=True)
        with self.assertRaises(ValidationError):evidence.full_clean()
        self.publish();self.login_member();self.assertEqual(self.client.get(f'/documents/{memo.pk}/reading/').status_code,403)
    def test_source_edits_reopen_all_linked_cases(self):
        other=Case.objects.create(title='가상 연결',topic='가상',occurred_on=datetime.date(2025,1,1),author=self.editor)
        doc=self.doc();CaseEvidence.objects.create(case=other,document=doc,locator='1쪽')
        self.publish(self.case,other);doc.source='변경된 가상 출처';doc.save()
        self.case.refresh_from_db();other.refresh_from_db();self.assertEqual(self.case.state,'review');self.assertEqual(other.state,'review')
    def test_guest_inactive_member_and_regular_member_access(self):
        doc=self.doc();self.publish()
        self.assertEqual(self.client.get(f'/cases/{self.case.pk}/').status_code,302)
        self.assertEqual(self.client.get(f'/documents/{doc.pk}/reading/').status_code,403)
        self.assertEqual(self.client.get('/api/cases/').status_code,403)
        self.login_member();self.assertEqual(self.client.get(f'/documents/{doc.pk}/reading/').status_code,200);self.assertEqual(self.client.get(f'/documents/{doc.pk}/original/').status_code,403)
        self.assertEqual(self.client.get('/materials/import/').status_code,302)
        self.member.active=False;self.member.save();self.assertEqual(self.client.get(f'/cases/{self.case.pk}/').status_code,302)
    def test_original_requires_document_permission_and_admin_mfa(self):
        doc=self.doc();self.login_staff(permissions=['view_case'])
        self.assertEqual(self.client.get(f'/documents/{doc.pk}/original/').status_code,403)
        self.editor.user_permissions.add(Permission.objects.get(codename='view_document'))
        self.assertEqual(self.client.get(f'/documents/{doc.pk}/original/').status_code,200)
        session=self.client.session;session['admin_mfa_until']=0;session.save();self.assertEqual(self.client.get(f'/documents/{doc.pk}/original/').status_code,403)
    def test_preview_is_staff_only_and_three_area_order(self):
        self.assertEqual(self.client.get(f'/admin/portal/case/{self.case.pk}/preview/').status_code,302)
        self.login_staff(permissions=['view_case'])
        response=self.client.get(f'/admin/portal/case/{self.case.pk}/preview/');self.assertEqual(response.status_code,200)
        self.assertContains(response,'관리자 전용 저장된 내용 미리보기');html=response.content.decode();self.assertLess(html.index('01 · 사건'),html.index('02 · 관련'));self.assertLess(html.index('02 · 관련'),html.index('03 · 현재'));self.assertIn('grid-template-columns:1fr',html)
    def test_publication_checks_and_role_permissions(self):
        self.assertEqual(len(publication_errors(self.case)),3)
        self.case.sources_reviewed=True;self.case.privacy_reviewed=True;self.case.publication_reason='가상 검토 확인';self.assertEqual(publication_errors(self.case),[])
        self.login_staff(permissions=['view_case','change_case'])
        from .admin import CaseForm
        form=CaseForm(instance=self.case);form.actor=self.editor
        data={'title':self.case.title,'topic':self.case.topic,'occurred_on':'2025-02-12','occurred_precision':'day','state':'published','sources_reviewed':'on','privacy_reviewed':'on','publication_reason':'가상 검토'}
        form=CaseForm(data,instance=self.case);form.actor=self.editor;self.assertFalse(form.is_valid())
    def test_requests_prefill_case_and_remain_private(self):
        self.publish();self.login_member();response=self.client.get(f'/requests/?case={self.case.pk}');self.assertEqual(response.context['form'].initial['case'],self.case)
        self.client.post('/requests/',{'kind':'response','case':self.case.pk,'body':'가상 비공개 반론'})
        self.assertContains(self.client.get('/requests/'),'가상 비공개 반론');self.assertNotContains(self.client.get(f'/cases/{self.case.pk}/'),'가상 비공개 반론')
    def test_import_is_blocked_in_development(self):
        memo=self.memo()
        with self.assertRaises(ValidationError):extract_candidates(memo,self.editor)
        self.assertEqual(MemoImport.objects.count(),0)
    def test_import_duplicate_grouping_strategy_exclusion_and_draft_conversion(self):
        memo=self.memo()
        with self.private_environment():
            batch,created=extract_candidates(memo,self.editor);self.assertTrue(created);self.assertEqual(batch.basis_on,datetime.date(2026,9,19));self.assertEqual(batch.candidates.count(),3)
            again,created=extract_candidates(memo,self.editor);self.assertFalse(created);self.assertEqual(again.pk,batch.pk)
            cafe=batch.candidates.get(topic='카페 운영과 세금 부담');self.assertNotIn('협상 카드',cafe.internal_excerpt);self.assertEqual(len(cafe.date_candidates),2);self.assertIn('제999조',cafe.article_hints)
            with self.assertRaises(ValidationError):convert_candidate(cafe,self.editor)
            cafe.neutral_summary='가상 카페 운영에 대한 내부 메모 기재. 원자료 확인 필요.';cafe.reviewed=True;cafe.occurred_precision='month';cafe.occurred_year=2025;cafe.occurred_month=2;cafe.save()
            case,created=convert_candidate(cafe,self.editor);self.assertTrue(created);self.assertEqual(case.state,'draft');self.assertIsNone(case.occurred_on);self.assertEqual(case.statements.get().kind,'unknown');self.assertEqual(case.articles.count(),0);self.assertEqual(case.official_decisions.count(),0)
            same,created=convert_candidate(cafe,self.editor);self.assertFalse(created);self.assertEqual(same.pk,case.pk);self.assertIn('최근 상태 확인 필요',case.status)
    def test_strategy_summary_and_unsafe_environment_refused(self):
        memo=self.memo()
        with self.private_environment():
            batch,_=extract_candidates(memo,self.editor);candidate=batch.candidates.first();candidate.reviewed=True;candidate.neutral_summary='가상 협상 카드와 승리 목표';candidate.save()
            with self.assertRaises(ValidationError):convert_candidate(candidate,self.editor)
        with self.private_environment(),override_settings(PRIVATE_STORAGE_CONFIRMED=False):
            with self.assertRaises(ValidationError):extract_candidates(memo,self.editor)
    def test_import_admin_endpoint_and_duplicate_post(self):
        memo=self.memo();self.login_staff(permissions=['add_case','change_importcandidate','view_importcandidate','view_document'])
        self.assertEqual(self.client.post('/materials/import/',{'document':memo.pk}).status_code,403)
        with self.private_environment():
            response=self.client.post('/materials/import/',{'document':memo.pk});self.assertEqual(response.status_code,200)
            self.client.post('/materials/import/',{'document':memo.pk});self.assertEqual(MemoImport.objects.count(),1);self.assertEqual(ImportCandidate.objects.count(),3)
    def test_docx_table_date_and_strategy_sections(self):
        buffer=io.BytesIO()
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl><w:tr><w:tc><w:p><w:r><w:t>2025년 2월</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>가상 카페 운영 확인 필요</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>대응 전략</w:t></w:r></w:p><w:p><w:r><w:t>카페 가상 비공개 전략 내용</w:t></w:r></w:p></w:body></w:document>'
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('word/document.xml',xml)
        memo=Document.objects.create(title='가상 표 메모',source='가상',acquired_on=datetime.date(2026,9,19),excerpt='내부',internal_memo=True,original=SimpleUploadedFile('synthetic-table.docx',buffer.getvalue()))
        with self.private_environment():
            batch,_=extract_candidates(memo,self.editor)
        candidate=batch.candidates.get();self.assertIn('표 1 행 1',candidate.source_locator);self.assertEqual(candidate.date_candidates[0]['precision'],'month');self.assertIsNone(candidate.date_candidates[0]['day']);self.assertNotIn('가상 비공개 전략 내용',candidate.internal_excerpt);self.assertEqual(batch.excluded_blocks,2)
    def test_fully_redacted_reading_and_internal_source_names(self):
        memo=self.memo();CaseEvidence.objects.create(case=self.case,document=memo,locator='문단 1')
        unsafe=self.doc(redaction_checked=False,state='draft')
        self.publish();self.login_member();response=self.client.get(f'/cases/{self.case.pk}/')
        self.assertNotContains(response,memo.title);self.assertNotContains(response,'synthetic-memo.docx');self.assertEqual(self.client.get(f'/documents/{unsafe.pk}/reading/').status_code,403)
    def test_editor_cannot_publish_without_independent_approver(self):
        self.login_staff(permissions=['view_case','change_case','publish_case'])
        from .admin import CaseForm
        data={'title':self.case.title,'topic':self.case.topic,'occurred_on':'2025-02-12','occurred_precision':'day','state':'published','sources_reviewed':'on','privacy_reviewed':'on','publication_reason':'가상 검토'}
        form=CaseForm(data,instance=self.case);form.actor=self.editor;self.assertFalse(form.is_valid())
    def test_changed_statement_actor_blocks_self_approval(self):
        from .admin import StatementAdmin,CaseForm
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        other=User.objects.create_user('another-fictitious-editor',is_staff=True)
        other.user_permissions.add(Permission.objects.get(codename='publish_case'))
        statement=CaseStatement(case=self.case,kind='unknown',text='가상 내용',source_note='가상 원자료 확인 필요')
        request=RequestFactory().post('/');request.user=other
        form=type('Form',(),{'cleaned_data':{}})()
        StatementAdmin(CaseStatement,AdminSite()).save_model(request,statement,form,False)
        self.case.refresh_from_db();self.assertEqual(self.case.last_editor,other)
        data={'title':self.case.title,'topic':self.case.topic,'occurred_on':'2025-02-12','occurred_precision':'day','state':'published','sources_reviewed':'on','privacy_reviewed':'on','publication_reason':'가상 확인'}
        form=CaseForm(data,instance=self.case);form.actor=other;self.assertFalse(form.is_valid())

    def test_shared_statute_never_inherits_applicability_from_another_case(self):
        article=Article.objects.create(case=self.case,citation='가상 조문 확인 사례',text='가상 문장 (실제 조문 아님)',verified=True,source='https://www.pck.or.kr/',amendment_source='https://www.pck.or.kr/',official_page='가상 1쪽',effective_on=datetime.date(2025,1,1),amended_on=datetime.date(2024,12,1),checked_on=datetime.date(2025,1,2),applicability_status='applicable',applicability_reason='가상 기본 사건 검증',relevance='가상 기본 사건')
        older=Case.objects.create(title='가상 과거 사건',topic='가상',occurred_on=datetime.date(2024,1,1),author=self.editor)
        article.related_cases.add(older)
        self.publish(self.case,older);self.login_member()
        response=self.client.get(f'/cases/{older.pk}/');self.assertContains(response,'사건 당시 적용: 확인 중');self.assertNotContains(response,'가상 기본 사건 검증')
        application=ArticleCaseLink.objects.get(article=article,case=older);application.applicability_status='applicable';application.applicability_reason='가상 잘못된 소급 적용'
        with self.assertRaises(ValidationError):application.full_clean()
    def test_supporting_evidence_scope_and_private_log_ids(self):
        other=Case.objects.create(title='다른 가상 비공개 사건',topic='가상',occurred_on=datetime.date(2025,1,1),author=self.editor)
        evidence=CaseEvidence.objects.create(case=other,document=self.doc(),locator='가상 1쪽')
        statement=CaseStatement.objects.create(case=self.case,kind='unknown',text='가상 설명',source_note='가상 출처');statement.supporting_evidence.add(evidence)
        with self.assertRaises(ValidationError):statement.full_clean()
        from .admin import CaseAdmin
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        request=RequestFactory().post('/');request.user=self.editor
        entry=CaseAdmin(Case,AdminSite()).log_change(request,self.case,'가상 수정')
        self.assertEqual(entry.object_repr,f'case:{self.case.pk}');self.assertNotIn(self.case.title,entry.object_repr)

from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

class CaseMigrationTests(TransactionTestCase):
    def test_old_case_post_document_ids_are_preserved(self):
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes('portal')
        executor.migrate([('portal','0005_case_review_summary_changenote')])
        old=executor.loader.project_state([('portal','0005_case_review_summary_changenote')]).apps
        user=old.get_model('auth','User').objects.create(username='migration-fictitious-author')
        member=old.get_model('portal','Member').objects.create(name='가상이전교인',phone='01000000000',synthetic=True)
        case=old.get_model('portal','Case').objects.create(title='가상 이전 사건',topic='가상',occurred_on=datetime.date(2025,1,2),author_id=user.pk)
        doc=old.get_model('portal','Document').objects.create(case_id=case.pk,title='가상 이전 문서',original='originals/fictitious.pdf',source='가상 원자료',acquired_on=datetime.date(2025,2,1),excerpt='가상')
        post=old.get_model('portal','Post').objects.create(member_id=member.pk,author_name='가상이전교인',case_id=case.pk,title='가상 이전 글',body='가상 보존 본문')
        try:
            executor=MigrationExecutor(connection);executor.migrate(latest)
            new=executor.loader.project_state(latest).apps
            self.assertEqual(new.get_model('portal','Case').objects.get(pk=case.pk).occurred_on,datetime.date(2025,1,2))
            self.assertEqual(new.get_model('portal','Post').objects.get(pk=post.pk).case_id,case.pk)
            self.assertEqual(new.get_model('portal','Post').objects.get(pk=post.pk).member_id,member.pk)
            self.assertEqual(new.get_model('portal','Document').objects.get(pk=doc.pk).case_id,case.pk)
            link=new.get_model('portal','CaseEvidence').objects.get(case_id=case.pk,document_id=doc.pk)
            self.assertFalse(link.checked)
        finally:
            MigrationExecutor(connection).migrate(latest)
