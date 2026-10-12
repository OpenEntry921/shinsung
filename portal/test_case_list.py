"""Continuous comparison uses fictional content only; no real materials."""
import datetime
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from .models import Case, Member, Article, Document, CaseEvidence, CaseStatement, Decision

@override_settings(DEV=True, APP_MODE='development', SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False)
class ContinuousCaseTests(TestCase):
    def setUp(self):
        self.editor=User.objects.create(username='fictitious-list-editor')
        self.member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        session=self.client.session
        session['member_id']=str(self.member.pk);session['member_version']=self.member.session_version;session.save()
    def case(self,title='가상 사건',day=1,**fields):
        return Case.objects.create(title=title,topic='가상 주제',author=self.editor,state='published',occurred_on=datetime.date(2025,1,day),**fields)
    def test_full_groups_and_detail_compatibility(self):
        first=self.case('가상 첫 사건',1,overview='첫 사건 개요',issues='첫 검토 쟁점',opinion='첫 운영 의견')
        second=self.case('가상 두 번째',2,overview='둘째 개요',issues='둘째 검토 쟁점')
        response=self.client.get('/');content=response.content.decode()
        self.assertContains(response,'검색 결과 2건');self.assertContains(response,'class="review-section"',count=3)
        self.assertNotContains(response,'class="columns"')
        self.assertLess(content.index('① 사건 경과'),content.index('② 관련 교단 헌법과 규정'));self.assertLess(content.index('② 관련 교단 헌법과 규정'),content.index('③ 쟁점과 추가 확인사항'))
        for case in (first,second):
            self.assertContains(response,f'/cases/{case.pk}/')
            self.assertContains(self.client.get(f'/cases/{case.pk}/'),case.overview)
    def test_long_text_multiple_articles_and_safe_html(self):
        case=self.case(overview='가상 본문 '*500+'끝표시 <script>alert(1)</script>')
        for number in (1,2):Article.objects.create(case=case,citation=f'가상 조문 후보 {number}',text='검증 안 된 본문')
        Case.objects.filter(pk=case.pk).update(state='published')
        response=self.client.get('/')
        self.assertContains(response,'끝표시 &lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertContains(response,'가상 조문 후보 1');self.assertContains(response,'가상 조문 후보 2')
        self.assertNotContains(response,'검증 안 된 본문')
    def test_initial_content_has_all_cases_and_keeps_sort_filters(self):
        for day in range(1,8):self.case(f'가상 사건 {day}',day)
        response=self.client.get('/?q=가상&topic=주제&order=desc&from=2025-01-01')
        self.assertContains(response,'검색 결과 7건')
        self.assertEqual([c.title for c in response.context['cases']], [f'가상 사건 {n}' for n in range(7,0,-1)])
        self.assertNotContains(response,'다음 페이지')
    def test_empty_search_and_reset(self):
        self.assertContains(self.client.get('/'),'게시된 사건이 아직 없습니다')
        self.case();response=self.client.get('/?q=없는검색')
        self.assertContains(response,'검색 조건에 맞는 사건이 없습니다');self.assertContains(response,'검색 조건 초기화')
    def test_partial_dates_and_unknown_last(self):
        known=self.case()
        monthly=Case.objects.create(title='가상 월 사건',author=self.editor,state='published',occurred_precision='month',occurred_year=2024,occurred_month=12)
        unknown=Case.objects.create(title='가상 날짜 미상',author=self.editor,state='published',occurred_precision='unknown')
        self.assertEqual(list(self.client.get('/').context['cases']),[monthly,known,unknown])
        self.assertEqual(list(self.client.get('/?order=desc').context['cases']),[known,monthly,unknown])
        self.assertContains(self.client.get('/?from=2024-12-15&to=2024-12-20'),'2024년 12월 (월 단위)')
        monthly.refresh_from_db();self.assertIsNone(monthly.occurred_on)
    def test_private_document_metadata_and_drafts_not_exposed(self):
        case=self.case();draft=self.case('가상 초안',2);Case.objects.filter(pk=draft.pk).update(state='review')
        for state,reading,redaction,memo,title in [('draft','private.pdf',True,False,'비공개 초안 문서'),('published','',True,False,'열람본 없는 문서'),('published','private.pdf',False,False,'가림 미확인 문서'),('draft','',False,True,'내부 메모 제목')]:
            doc=Document.objects.create(case=case,title=title,source='가상 출처',acquired_on=datetime.date(2025,1,1),state=state,reading=reading,redaction_checked=redaction,internal_memo=memo)
            evidence=CaseEvidence.objects.create(case=case,document=doc,locator='비공개 위치')
            CaseStatement.objects.create(case=case,kind='unknown',text='원자료 확인 필요',source_note='확인 중',evidence=evidence)
            decision=Decision.objects.create(document=doc,locator='비공개 결정 위치');decision.cases.add(case)
        Case.objects.filter(pk=case.pk).update(state='published')
        for url in ('/',f'/cases/{case.pk}/'):
            response=self.client.get(url)
            for hidden in ('가상 초안','비공개 초안 문서','열람본 없는 문서','가림 미확인 문서','내부 메모 제목','비공개 위치','비공개 결정 위치','/original/'):
                self.assertNotContains(response,hidden)
    def test_multiple_approved_reading_documents(self):
        case=self.case()
        for n in (1,2):
            doc=Document.objects.create(case=case,title=f'가상 승인 열람본 {n}',source='가상 출처',acquired_on=datetime.date(2025,1,1),state='published',reading=f'fictitious-{n}.pdf',redaction_checked=True)
            CaseEvidence.objects.create(case=case,document=doc,locator=f'{n}쪽')
        Case.objects.filter(pk=case.pk).update(state='published')
        response=self.client.get('/')
        for n in (1,2):self.assertContains(response,f'가상 승인 열람본 {n}')
        self.assertNotContains(response,'/original/')
    def test_guest_and_inactive_cannot_read_content(self):
        case=self.case(overview='가상 비공개 본문');self.client.logout()
        for url in ('/',f'/cases/{case.pk}/'):
            response=self.client.get(url);self.assertEqual(response.status_code,302);self.assertNotContains(response,case.title,status_code=302)
        session=self.client.session;session['member_id']=str(self.member.pk);session['member_version']=self.member.session_version;session.save()
        Member.objects.filter(pk=self.member.pk).update(active=False)
        self.assertEqual(self.client.get('/').status_code,302)

    def test_body_date_and_shared_rule_search_connections(self):
        from .models import ArticleCaseLink
        first=self.case('가상 첫 연결 사건',2,overview='본문만의 검색어')
        second=self.case('가상 둘째 연결 사건',3)
        article=Article.objects.create(case=first,citation='가상 제998조 후보',review_description='공식 원문이 아닌 가상 설명',relevance='가상 관련성')
        ArticleCaseLink.objects.create(article=article,case=second,relevance='두 번째 가상 연결')
        Case.objects.filter(pk__in=[first.pk,second.pk]).update(state='published')
        self.assertEqual([c.pk for c in self.client.get('/?q=2025.1.2').context['cases']],[first.pk])
        self.assertEqual(self.client.get('/?q=2025.99.99').status_code,200)
        self.assertEqual([c.pk for c in self.client.get('/?q=본문만의').context['cases']],[first.pk])
        response=self.client.get('/?q=998');self.assertEqual([c.pk for c in response.context['cases']],[first.pk,second.pk])
        self.assertContains(response,'가상 제998조 후보',count=1)
        self.assertContains(response,'공식 원문이 아닌 가상 설명')

    def test_month_range_search_keeps_original_period_and_no_fake_day(self):
        case=Case.objects.create(title='가상 월 구간',topic='가상',author=self.editor,state='published',occurred_precision='period',occurred_year=2001,occurred_month=4,period_description='2001.4~6')
        for url in ('/?q=2001.6','/?from=2001-06-15&to=2001-06-20'):
            self.assertContains(self.client.get(url),'2001.4~6')
        case.refresh_from_db();self.assertIsNone(case.occurred_on);self.assertIsNone(case.occurred_until)
