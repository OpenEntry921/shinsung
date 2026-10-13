"""Fictional accounts only; no confidential case text copied into tests."""
import datetime
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import Member, Challenge, Case, Article, Document, Post
from .security import digest

@override_settings(APP_MODE='production',DEV=False,SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
class LoginEntryTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        self.post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 글',body='보존')
    def test_first_visit_shows_existing_login_without_body(self):
        r=self.client.get('/',follow=True)
        self.assertEqual(r.redirect_chain,[('/login/',302)])
        self.assertEqual(r.status_code,200)
        self.assertTrue('인증번호 요청'.encode() in r.content);self.assertTrue('인증번호 확인'.encode() in r.content)
        self.assertFalse(b'material-E01' in r.content)
    def issue(self):
        with patch('portal.views.send_sms',return_value=True),patch('portal.views.secrets.randbelow',return_value=123456):
            r=self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone})
        self.assertEqual(r.status_code,200)
        self.assertNotContains(r,'가상 발송 인증번호')
    def test_production_otp_leads_to_all_html_without_material_rows(self):
        self.issue()
        r=self.client.post('/otp/',{'code':'123456'},follow=True)
        self.assertEqual(r.redirect_chain,[('/',302)])
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.content.count(b'class="case-group direct-case"'),30)
        self.assertEqual(r.content.count(b'class="reading-area"'),120)
        self.assertIn(b'material-E01',r.content);self.assertIn(b'material-E30',r.content)
        self.assertEqual((Case.objects.count(),Article.objects.count(),Document.objects.count()),(0,0,0))
        self.assertEqual(self.client.session['member_auth_mode'],'production')
        self.assertEqual(Post.objects.get(pk=self.post.pk).member_id,self.member.pk)
    def test_missing_sms_never_authenticates(self):
        with override_settings(SMS_API_KEY='',SMS_API_SECRET='',SMS_SENDER=''):
            self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone})
            self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400)
        self.assertNotIn('member_id',self.client.session)
    def test_old_session_returns_login_and_preserves_records(self):
        session=self.client.session;session['member_id']=str(self.member.pk);session['member_version']=self.member.session_version;session['member_auth']='sms';session.save()
        self.assertEqual(self.client.get('/',follow=True).status_code,200)
        self.assertNotIn('member_id',self.client.session)
        self.assertEqual(Member.objects.count(),1);self.assertEqual(Post.objects.count(),1)
    def test_demo_cookie_cleared_and_login_is_displayed(self):
        with override_settings(APP_MODE='development',DEV=True):
            self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone})
            challenge=Challenge.objects.get();challenge.digest=digest(str(challenge.pk),'123456');challenge.save()
            r=self.client.post('/otp/',{'code':'123456'},follow=True)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.redirect_chain,[('/',302),('/login/',302)])
            self.assertContains(r,'인증번호 요청');self.assertFalse(b'material-E01' in r.content)
            self.assertNotIn('member_id',self.client.session)
    def test_demo_challenge_cannot_be_reused_in_production(self):
        with override_settings(APP_MODE='development',DEV=True):
            challenge=Challenge.objects.create(member=self.member,version=self.member.session_version,digest='',expires_at=timezone.now()+datetime.timedelta(minutes=5))
            challenge.digest=digest(str(challenge.pk),'123456');challenge.save()
            session=self.client.session;session['challenge_id']=str(challenge.pk);session.save()
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400)
        self.assertNotIn('member_id',self.client.session)
    def test_mode_switch_requires_real_authentication(self):
        session=self.client.session;session.update({'member_id':str(self.member.pk),'member_version':self.member.session_version,'member_auth':'sms','member_auth_mode':'development'});session.save()
        r=self.client.get('/',follow=True)
        self.assertEqual(r.status_code,200);self.assertFalse(b'material-E01' in r.content)
        self.assertNotIn('member_id',self.client.session)
