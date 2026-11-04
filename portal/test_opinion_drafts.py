"""Only fictional opinion text is used in fixtures."""
from django.test import SimpleTestCase,TestCase,override_settings
from .test_integrated_timeline import fictional_md
from scripts.prepare_integrated_timeline import parse_document,render
from .models import Member,CaseComment,Case
from .testing import member_session
import re

class OpinionConversionTests(SimpleTestCase):
    def source(self):
        return fictional_md().replace('### 02 ','''#### 우리의 의견 초안 OP01

**제목**: 가상 검토

**작성 주체·상태**: 가상 사용자 의견 · 검토 전

가상 주장 <script>unsafe()</script>

#### 사용자 제공 경과와 추가 확인

가상 경과 · 기관 판단 아님

### 02 ''',1).replace('### 03 ','''#### 관련 의견 안내 OP01

01번 가상 검토와 함께 읽습니다.

### 03 ''',1)
    def test_preserves_core_and_renders_supplements_once_inside_fourth_area(self):
        old,_=parse_document(fictional_md());new,_=parse_document(self.source())
        for a,b in zip(old,new):
            for field in ('key','number','title','날짜','경과','관련 규정','쟁점','references','source_refs'):
                self.assertEqual(a[field],b[field])
        output=render(new,'fictional')
        self.assertEqual(output.count('class="reading-area"'),288)
        self.assertEqual(output.count('data-opinion="OP01"'),1)
        self.assertTrue('&lt;script&gt;unsafe()&lt;/script&gt;' in output)
        self.assertFalse('<script>unsafe()' in output)
        self.assertTrue('<strong>작성 주체·상태</strong>' in output)
        first=output.split("{% if selected_key == 'T02' %}")[0]
        self.assertLess(first.index('data-area="쟁점"'),first.index('data-opinion="OP01"'))
        self.assertEqual(output,render(new,'fictional'))
    def test_rejects_duplicate_missing_reference_unknown_section_and_template_injection(self):
        for source in (self.source().replace('관련 의견 안내 OP01','우리의 의견 초안 OP01'),
                       self.source().replace('관련 의견 안내 OP01','관련 의견 안내 OP99'),
                       self.source().replace('사용자 제공 경과와 추가 확인','알 수 없는 절'),
                       self.source().replace('가상 경과 · 기관 판단 아님','{{ unsafe }}')):
            with self.assertRaises(ValueError):parse_document(source)

@override_settings(SECURE_SSL_REDIRECT=False)
class OpinionAccessTests(TestCase):
    def test_drafts_are_protected_and_do_not_create_comments_or_case_rows(self):
        guest=self.client.get('/cases/material/T05/')
        self.assertEqual(guest.status_code,302)
        self.assertNotIn(b'data-opinion=',guest.content)
        member=Member.objects.create(name='가상 검증',phone='01000000000',synthetic=True)
        member_session(self.client,member)
        response=self.client.get('/cases/material/T05/')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'data-opinion="OP15"',response.content)
        self.assertEqual(response.content.count(b'class="reading-area"'),4)
        self.assertIn('no-store',response.headers.get('Cache-Control',''))
        self.assertEqual(CaseComment.objects.count(),0)
        self.assertEqual(Case.objects.count(),0)
        member.active=False;member.save()
        denied=self.client.get('/cases/material/T05/')
        self.assertEqual(denied.status_code,302)
        self.assertNotIn(b'data-opinion=',denied.content)
