"""Only fabricated identities; exercise restored operator login without enrollment."""
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User, Permission
from django.utils import timezone
from .models import Member, CaseComment, AccessApplication, Audit, Revision

@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False)
class OperatorLoginTests(TestCase):
    def setUp(self):
        self.operator = Member.objects.create(name='가상 기존 운영자', phone='01000000007', synthetic=True, legacy_operator=True)
        self.other = Member.objects.create(name='가상 일반 교인', phone='01000000008', synthetic=True)

    def login(self):
        return self.client.post('/login/', {'name': self.operator.name, 'phone':'010-0000-0007'})

    def test_retired_operator_login_does_not_create_session_but_existing_session_works(self):
        self.assertRedirects(self.login(), '/', fetch_redirect_response=False)
        self.assertNotIn('member_id', self.client.session)
        session=self.client.session
        session.update(dict(member_id=str(self.operator.pk),member_auth='roster',member_version=self.operator.session_version))
        session.save()
        self.assertEqual(self.client.post('/comments/E01/', {'body':'가상 기존 운영자 의견'}).status_code,302)
        self.assertEqual(CaseComment.objects.get().member_id,self.operator.pk)
        self.assertContains(self.client.get('/cases/material/E01/'),'가상 기존 운영자 의견')
        self.client.logout()
        self.assertNotContains(self.client.get('/cases/material/E01/'),'가상 기존 운영자 의견')

    def test_general_members_guests_pending_and_forged_roles_cannot_read(self):
        for data in ({'name':self.other.name,'phone':self.other.phone,'legacy_operator':'on'},
                     {'name':self.operator.name,'phone':'01099999999'},
                     {'name':self.other.name,'phone':self.other.phone,'member_id':str(self.operator.pk)}):
            self.client.post('/login/?legacy_operator=1',data)
            self.assertNotIn('member_id',self.client.session)
        for path in ('/posts/','/requests/','/comment-link/1/'):
            self.assertEqual(self.client.get(path).status_code,403)
        self.assertEqual(self.client.get('/documents/1/reading/').status_code,404)
        self.assertEqual(self.client.post('/comments/E01/',{'body':'차단'}).status_code,403)

    def test_retired_login_csrf_and_existing_operator_revocation(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/login/',{'name':self.operator.name,'phone':self.operator.phone}).status_code,403)
        session=self.client.session
        session.update(dict(member_id=str(self.operator.pk),member_auth='roster',member_version=self.operator.session_version))
        session.save()
        self.operator.legacy_operator=False;self.operator.save()
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/requests/').status_code,403)
        self.assertNotIn('member_id',self.client.session)

    def test_administrator_auth_does_not_impersonate_member(self):
        user=User.objects.create_user(username='fictional-staff', password='fictional-test-password', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_case'))
        self.assertTrue(self.client.login(username=user.username,password='fictional-test-password'))
        self.assertEqual(self.client.get('/').status_code,200)
        session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        self.assertEqual(self.client.get('/cases/material/E01/').status_code,200)
        self.assertEqual(self.client.post('/comments/E01/',{'body':'대필 금지'}).status_code,403)
        self.assertEqual(CaseComment.objects.count(),0)

    def test_operator_role_requires_explicit_admin_permission_and_records_history(self):
        user=User.objects.create_user('fictional-roster-editor',is_staff=True)
        user.user_permissions.add(*Permission.objects.filter(codename__in=['view_member','change_member']))
        self.client.force_login(user)
        session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        path=f'/admin/portal/member/{self.other.pk}/change/'
        response=self.client.get(path)
        self.assertNotContains(response,'name="legacy_operator"')
        data={'name':self.other.name,'phone':self.other.phone,'active':'on','label':'','legacy_operator':'on','reason':'가상 운영자 지정 검증','_save':'저장'}
        self.assertEqual(self.client.post(path,data).status_code,302)
        self.other.refresh_from_db();self.assertFalse(self.other.legacy_operator)
        user.user_permissions.add(Permission.objects.get(codename='manage_legacy_operator'))
        response=self.client.get(path);self.assertContains(response,'name="legacy_operator"')
        self.assertEqual(self.client.post(path,data).status_code,302)
        self.other.refresh_from_db();self.assertTrue(self.other.legacy_operator)
        self.assertEqual(AccessApplication.objects.count(),0)
        self.assertEqual(Audit.objects.filter(action='operator_grant',target=str(self.other.pk)).count(),1)
        self.assertEqual(Revision.objects.get(target=f'member:{self.other.pk}').body,{'legacy_operator':False})
        self.assertEqual(Member.objects.filter(legacy_operator=True).count(),2)
