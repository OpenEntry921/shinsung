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

    def test_real_login_path_without_enrollment_opens_all_cases_and_self_comments(self):
        for mode in (True, False):
            self.operator.synthetic = mode
            self.operator.save()
            with override_settings(DEV=mode):
                self.client.logout()
                with patch('portal.security.requests.post') as sender:
                    response=self.login()
                sender.assert_not_called()
                self.assertRedirects(response, '/', fetch_redirect_response=False)
                self.assertEqual(self.client.session['member_auth'], 'roster')
                self.assertEqual(AccessApplication.objects.count(), 0)
                home=self.client.get('/')
                self.assertContains(home, '공동 상황판')
                self.assertContains(home, '해결 절차 로드맵')
                self.assertEqual(home.content.count(b'class="timeline-card"'),30)
                self.assertRedirects(self.client.get('/login/'), '/', fetch_redirect_response=False)
                for n in range(1,31):
                    detail=self.client.get(f'/cases/material/E{n:02}/')
                    self.assertEqual(detail.status_code,200)
                    self.assertEqual(detail.content.count(b'class="case-group direct-case"'),1)
                created=self.client.post('/comments/E01/', {'body':'가상 시험 댓글', 'member':str(self.other.pk)})
                self.assertEqual(created.status_code,400)
                created=self.client.post('/comments/E01/', {'body':'가상 시험 댓글'})
                comment=CaseComment.objects.filter(deleted_at=None).get()
                self.assertEqual(comment.member_id,self.operator.pk)
                self.assertEqual(comment.author_name,self.operator.name)
                self.assertEqual(created.url,f'/cases/material/E01/#comment-{comment.pk}')
                self.assertContains(self.client.get('/cases/material/E01/'),'가상 시험 댓글')
                self.assertNotContains(self.client.get('/cases/material/E02/'),'가상 시험 댓글')
                self.client.post(f'/comments/E01/{comment.pk}/', {'action':'delete'})
                comment.refresh_from_db();self.assertIsNotNone(comment.deleted_at)
                self.assertNotContains(self.client.get('/cases/material/E01/'),'가상 시험 댓글')

    def test_general_members_guests_pending_and_forged_roles_cannot_read(self):
        for data in ({'name':self.other.name,'phone':self.other.phone,'legacy_operator':'on'},
                     {'name':self.operator.name,'phone':'01099999999'},
                     {'name':self.other.name,'phone':self.other.phone,'member_id':str(self.operator.pk)}):
            self.client.post('/login/?legacy_operator=1',data)
            self.assertNotIn('member_id',self.client.session)
        for path in ('/','/cases/material/E01/','/posts/','/requests/','/comment-link/1/'):
            self.assertEqual(self.client.get(path).status_code,302)
        self.assertEqual(self.client.get('/documents/1/reading/').status_code,403)
        self.assertEqual(self.client.post('/comments/E01/',{'body':'차단'}).status_code,302)

    def test_unique_match_rate_limit_csrf_and_revocation(self):
        with patch('portal.views.limit', return_value=False):
            self.assertEqual(self.login().status_code,200)
        self.assertNotIn('member_id',self.client.session)
        duplicate=Member.objects.create(name='가상 가족',phone=self.operator.phone,synthetic=True)
        self.assertEqual(self.login().status_code,200)
        self.assertNotIn('member_id',self.client.session)
        duplicate.active=False;duplicate.save()
        self.assertEqual(self.login().status_code,302)
        self.operator.legacy_operator=False;self.operator.save()
        self.assertEqual(self.client.get('/').status_code,302)
        self.assertNotIn('member_id',self.client.session)
        self.operator.legacy_operator=True;self.operator.save()
        self.assertEqual(self.login().status_code,302)
        self.operator.active=False;self.operator.save()
        self.assertEqual(self.client.get('/cases/material/E01/').status_code,302)
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/login/',{'name':self.operator.name,'phone':self.operator.phone}).status_code,403)

    def test_administrator_auth_does_not_impersonate_member(self):
        user=User.objects.create_user(username='fictional-staff', password='fictional-test-password', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_case'))
        self.assertTrue(self.client.login(username=user.username,password='fictional-test-password'))
        self.assertEqual(self.client.get('/').status_code,302)
        session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        self.assertEqual(self.client.get('/cases/material/E01/').status_code,200)
        self.assertEqual(self.client.post('/comments/E01/',{'body':'대필 금지'}).status_code,302)
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
