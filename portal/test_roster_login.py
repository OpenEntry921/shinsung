"""Fictional roster records; no actual excerpts or member data in fixtures."""
from unittest.mock import patch
from django.test import TestCase, override_settings
from .models import Member, Post, Case, Article, Document, Challenge

@override_settings(APP_MODE='production',DEV=False,SECURE_SSL_REDIRECT=False,SMS_API_KEY='',SMS_API_SECRET='',SMS_SENDER='')
class RosterLoginTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=False)
        self.post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 기존 글',body='보존')
    def test_first_visit_login_two_fields_then_entire_html(self):
        response=self.client.get('/',follow=True)
        self.assertEqual(response.redirect_chain,[('/login/',302)])
        self.assertTrue(b'id="name"' in response.content);self.assertTrue(b'id="phone"' in response.content)
        self.assertFalse(b'id="code"' in response.content)
        with patch('portal.security.requests.post') as sender:
            response=self.client.post('/login/',{'name':self.member.name,'phone':'010-0000-0000'},follow=True)
        sender.assert_not_called()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.redirect_chain,[('/',302)])
        self.assertEqual(response.content.count(b'class="case-group direct-case"'),30)
        self.assertEqual(response.content.count(b'class="reading-area"'),120)
        self.assertTrue(b'material-E01' in response.content and b'material-E30' in response.content)
        self.assertEqual((Case.objects.count(),Article.objects.count(),Document.objects.count(),Challenge.objects.count()),(0,0,0,0))
        self.assertEqual(Post.objects.get(pk=self.post.pk).member_id,self.member.pk)
    def test_unregistered_inactive_wrong_and_duplicate_records_denied(self):
        for name,number in [('존재하지않는가상교인','01000000009'),(self.member.name,'01000000099')]:
            response=self.client.post('/login/',{'name':name,'phone':number});self.assertEqual(response.status_code,200)
            self.assertNotIn('member_id',self.client.session)
        self.assertEqual(Member.objects.count(),1)
        self.member.active=False;self.member.save()
        self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone});self.assertNotIn('member_id',self.client.session)
    def test_shared_phone_does_not_allow_account_selection(self):
        Member.objects.create(name='가상 가족',phone=self.member.phone,synthetic=False)
        self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone})
        self.assertNotIn('member_id',self.client.session)
    def test_spoofed_id_ignored_and_logout_revokes(self):
        other=Member.objects.create(name='가상 다른교인',phone='01000000001',synthetic=False)
        self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone,'member_id':str(other.pk),'member_auth':'exception'})
        self.assertEqual(self.client.session['member_id'],str(self.member.pk))
        self.assertEqual(self.client.session['member_auth'],'roster')
        self.client.post('/logout/');self.assertEqual(self.client.get('/').status_code,302)
    def test_old_sms_session_requires_roster_login(self):
        session=self.client.session;session.update({'member_id':str(self.member.pk),'member_version':self.member.session_version,'member_auth':'sms'});session.save()
        self.assertEqual(self.client.get('/').status_code,302);self.assertNotIn('member_id',self.client.session)
    def test_development_existing_roster_can_read_without_otp(self):
        with override_settings(APP_MODE='development',DEV=True):
            response=self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone},follow=True)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.content.count(b'class="case-group direct-case"'),30)

    def test_corrected_input_and_relogin_have_no_sms_resend_delay(self):
        self.client.post('/login/',{'name':'가상 잘못된이름','phone':self.member.phone})
        self.assertNotIn('member_id',self.client.session)
        self.assertEqual(self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone}).status_code,302)
        self.client.post('/logout/')
        self.assertEqual(self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone}).status_code,302)
        self.assertEqual(self.client.session['member_id'],str(self.member.pk))
