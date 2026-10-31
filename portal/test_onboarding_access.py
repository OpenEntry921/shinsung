from django.test import TestCase,override_settings,Client
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import AccessApplication,Member,ProgressRecord,Revision
from .testing import member_session,approve
from .access import POLICY_FIELDS

@override_settings(SECURE_SSL_REDIRECT=False)
class ApplicationTests(TestCase):
    def test_missing_configuration_blocks_get_and_post_without_storing_pii(self):
        response=self.client.post('/apply/',dict(name='가상',phone='01000000000',privacy='on',religion='on',transfer='on'))
        self.assertContains(response,'가입 접수 준비 중')
        self.assertEqual(AccessApplication.objects.count(),0)
        self.assertNotContains(response,'name="phone"')
    @override_settings(**{key:'가상 정책 설정' for key in POLICY_FIELDS})
    def test_each_explicit_consent_required_no_automatic_member_link(self):
        member=Member.objects.create(name='가상',phone='01000000000',synthetic=True)
        data=dict(name=member.name,phone=member.phone,privacy='on',religion='on',transfer='on')
        response=self.client.get('/apply/')
        self.assertNotContains(response,'checked')
        for field in ('privacy','religion','transfer'):
            partial=dict(data);partial.pop(field)
            self.assertEqual(self.client.post('/apply/',partial).status_code,200)
            self.assertEqual(AccessApplication.objects.count(),0)
        self.client.post('/apply/',data)
        app=AccessApplication.objects.get()
        self.assertIsNone(app.member_id);self.assertFalse(app.approved)
        self.assertTrue(app.consent_version and app.policy_snapshot and app.privacy_consent_at and app.transfer_consent_at and app.religious_consent_at)
        self.assertEqual(Member.objects.count(),1)
        self.assertNotIn('member_id',self.client.session)
        self.assertEqual(self.client.get('/cases/material/E01/').status_code,302)
        secure=Client(enforce_csrf_checks=True)
        self.assertEqual(secure.post('/apply/',data).status_code,403)
    def test_approval_requires_distinct_actual_confirmation_records(self):
        app=AccessApplication(name='가상',phone='01000000000',approved=True)
        with self.assertRaises(ValidationError):app.save()
    def test_fake_delivery_rejected_and_unpublished_records_private(self):
        record=ProgressRecord(category='request',title='가상',public_text='가상 내부 기록',basis_on=timezone.now().date(),status='delivered')
        with self.assertRaises(ValidationError):record.full_clean()
        record.status='preparing';record.save()
        member=Member.objects.create(name='가상',phone='01000000000',synthetic=True);member_session(self.client,member)
        self.assertNotContains(self.client.get('/'),'가상 내부 기록')

from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

class AccessMigrationTests(TransactionTestCase):
    def test_existing_comment_reply_revision_request_and_member_survive(self):
        old=('portal','0010_member_discussions')
        new=('portal','0012_accessapplication_church_requested_at_and_more')
        executor=MigrationExecutor(connection);executor.migrate([old])
        try:
            apps=executor.loader.project_state([old]).apps
            member=apps.get_model('portal','Member').objects.create(name='가상 이관',phone='01000000000')
            root=apps.get_model('portal','CaseComment').objects.create(member_id=member.pk,author_name='가상',reading_key='E22',body='가상 보존 댓글')
            reply=apps.get_model('portal','CaseComment').objects.create(member_id=member.pk,author_name='가상',reading_key='E22',body='가상 보존 답글',parent_id=root.pk)
            item=apps.get_model('portal','Request').objects.create(member_id=member.pk,kind='report',reading_key='E22',comment_id=root.pk,body='가상 보존 요청')
            revision=apps.get_model('portal','Revision').objects.create(target=f'comment:{root.pk}',actor=str(member.pk),body={'body':'가상 이력'})
        finally:
            executor=MigrationExecutor(connection);executor.migrate([new])
        from .models import CaseComment,Request
        self.assertEqual(CaseComment.objects.get(pk=root.pk).body,'가상 보존 댓글')
        self.assertEqual(CaseComment.objects.get(pk=reply.pk).parent_id,root.pk)
        self.assertEqual(Request.objects.get(pk=item.pk).comment_id,root.pk)
        self.assertEqual(Revision.objects.get(pk=revision.pk).body,{'body':'가상 이력'})
        self.assertEqual(Member.objects.get(pk=member.pk).name,'가상 이관')
        self.assertEqual(AccessApplication.objects.count(),0)
