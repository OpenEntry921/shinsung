"""Versioned defaults and fictional operator records; no production data or messages."""
from datetime import date
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError
from .dashboard import dashboard_groups
from .models import ProgressRecord,Member,CaseComment
from .testing import member_session

@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardTests(TestCase):
    def test_five_groups_repeat_without_database_writes_or_duplicate_defaults(self):
        first=dashboard_groups();second=dashboard_groups()
        self.assertEqual([len(items) for _,items in first],[3,3,4,3,1])
        ids=[i['id'] for _,items in first for i in items]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(ids,[i['id'] for _,items in second for i in items])
        self.assertEqual(ProgressRecord.objects.count(),0)
        for _,items in first:
            for item in items:
                self.assertLess(item['basis_on'],item['edited_on'])
                self.assertTrue(item['sources'])
                self.assertTrue(all(r['locator']!='추가 확인 필요' for r in item['sources']))
                if item['id'].startswith('default-request-'):
                    self.assertIn('미전달',item['status_text'])
                    self.assertFalse(item.get('recipient') or item.get('delivered_on') or item.get('reply_requested_on'))
    def test_published_records_win_and_edits_hidden_records_and_dates_are_preserved(self):
        record=ProgressRecord.objects.create(category='request',title='가상 운영자 수정 제목',public_text='가상 운영 기록',reading_key='T13',basis_on=date(2026,11,5),status='review',published=True)
        hidden=ProgressRecord.objects.create(category='request',title='가상 비공개',public_text='가상 숨김',reading_key='T08',basis_on=date(2026,11,5),published=False)
        items=dict(dashboard_groups())['질의·시정 요청']
        self.assertEqual(items[0]['id'],'db-'+str(record.pk))
        self.assertFalse(any(i['id']=='default-request-tax' for i in items))
        self.assertFalse(any(i['title']==hidden.title for i in items))
        self.assertEqual(len(items),4)
        ProgressRecord.objects.filter(pk=record.pk).update(public_text='가상 추가 수정')
        self.assertEqual(dict(dashboard_groups())['질의·시정 요청'][0]['public_text'],'가상 추가 수정')
        self.assertEqual(ProgressRecord.objects.count(),2)
        legacy=ProgressRecord.objects.create(category='update',title='가상 기존 E 사건 기록',public_text='가상 보존',reading_key='E18',basis_on=date(2026,11,5),published=True)
        entry=dict(dashboard_groups())['최근 업데이트'][0]
        self.assertEqual(entry['id'],'db-'+str(legacy.pk))
        self.assertEqual(entry['related'][0]['key'],'E18')
        self.assertEqual(entry['related'][0]['number'],'E18')
    def test_actual_delivery_still_requires_recipient_and_delivery_date(self):
        record=ProgressRecord(category='request',title='가상',public_text='가상',basis_on=date(2026,11,4),status='delivered')
        with self.assertRaises(ValidationError):record.full_clean()
        record.recipient='가상 수신 기관';record.delivered_on=date(2026,11,5);record.full_clean()
    def test_protected_page_escapes_operator_records_and_shows_distinct_statuses(self):
        self.assertEqual(self.client.get('/').status_code,302)
        member=Member.objects.create(name='가상 상황판 검증',phone='01000000000',synthetic=True)
        member_session(self.client,member)
        record=ProgressRecord.objects.create(category='update',title='<script>fake()</script>',public_text='가상 공지',reading_key='T69',basis_on=date(2026,11,5),status='review',published=True)
        response=self.client.get('/');html=response.content.decode()
        self.assertEqual(response.status_code,200)
        self.assertTrue('&lt;script&gt;fake()&lt;/script&gt;' in html)
        self.assertFalse('<script>fake()</script>' in html)
        for label in ('자료 기준일','화면 편집일','미전달','회신 자료 확인 필요','공동 확인 과제'):self.assertIn(label,html)
        self.assertNotIn('아직 등록된 진행 기록이 없습니다',html)
        self.assertEqual(CaseComment.objects.count(),0)

    def test_community_tasks_replaces_meeting_default_without_touching_operator_text(self):
        items=dict(dashboard_groups())['공동 확인 과제']
        self.assertEqual(len(items),1)
        task=items[0]
        self.assertEqual(task['id'],'default-week-agenda')
        self.assertEqual(task['classification'],'자료 확인·설명 요청')
        self.assertEqual(task['title'],'교회 공동체가 확인해야 할 핵심 사항')
        self.assertEqual(task['status_text'],'확인 과제 정리 · 항목별 진행 상황 확인 필요')
        self.assertEqual(len(task['task_progress']),3)
        self.assertNotIn('모임',task['public_text'])
        self.assertNotIn('토요일',task['public_text'])
        self.assertEqual([r['code'] for r in task['sources']],['A01','B01','A12','S01'])
        record=ProgressRecord.objects.create(category='week',title='가상 운영자 고유 제목',public_text='가상 운영자 작성 내용 유지',basis_on=date(2026,11,5),status='review',published=True)
        current=dict(dashboard_groups())['공동 확인 과제']
        self.assertEqual(len(current),1)
        self.assertEqual(current[0]['public_text'],'가상 운영자 작성 내용 유지')
        self.assertEqual(current[0]['status_text'],'검토 중')
        self.assertEqual(ProgressRecord.objects.get(pk=record.pk).category,'week')
        self.assertEqual(ProgressRecord.objects.count(),1)
