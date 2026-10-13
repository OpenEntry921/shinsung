import datetime, tempfile, io, json
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import User,Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from openpyxl import Workbook
from .models import *
from .security import digest
from .roster import parse

@override_settings(DEV=True,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,SECURE_SSL_REDIRECT=False)
class PortalTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상교인A',phone='01000000001',synthetic=True)
        self.other=Member.objects.create(name='가상교인B',phone='01000000002',synthetic=True)
        self.staff=User.objects.create_user('test-editor',password='synthetic-test-password',is_staff=True)
        self.approver=User.objects.create_user('test-approver',password='synthetic-test-password',is_staff=True)
        self.case=Case.objects.create(title='가상 테스트 자료',occurred_on='2026-01-01',topic='가상',author=self.staff,reviewer=self.approver,state='published')
    def member_login(self,member=None,client=None):
        production=override_settings(DEV=False,APP_MODE="production");production.enable();self.addCleanup(production.disable)
        member=member or self.member; client=client or self.client
        session=client.session; session['member_id']=str(member.pk); session['member_version']=member.session_version; session.save()
    def staff_login(self):
        self.client.force_login(self.staff); session=self.client.session; session['admin_mfa_until']=timezone.now().timestamp()+300; session.save()
    def challenge(self,member=None,**kwargs):
        ch=Challenge(member=member or self.member,version=(member or self.member).session_version,expires_at=timezone.now()+datetime.timedelta(minutes=5),**kwargs)
        ch.digest=digest(str(ch.pk),'123456');ch.save(); session=self.client.session;session['challenge_id']=str(ch.pk);session.save();return ch
    def test_guest_access(self):
        for url in ['/','/posts/','/cases/1/','/requests/']:
            self.assertEqual(self.client.get(url).status_code,302)
        self.assertEqual(self.client.get('/documents/1/reading/').status_code,403)
        self.assertEqual(self.client.get('/api/anything/').status_code,403)
        self.assertEqual(self.client.get('/policy/').status_code,200)
    def test_member_cannot_admin(self):
        self.member_login()
        for url in ['/admin/','/roster/','/exception-issue/']:
            self.assertEqual(self.client.get(url).status_code,302)
    def test_inactive_revocation(self):
        self.member_login(); self.member.active=False;self.member.save()
        self.assertEqual(self.client.get('/').status_code,302)
    def test_number_change_revokes_session_and_otp(self):
        ch=self.challenge(); self.member_login();self.member.phone='01000000003';self.member.save()
        self.assertEqual(self.client.get('/').status_code,302)
        session=self.client.session;session['challenge_id']=str(ch.pk);session.save()
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400)
    def test_otp_success_one_use_hashed(self):
        ch=self.challenge();self.assertNotIn('123456',ch.digest)
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,302)
        self.assertEqual(self.client.get('/').status_code,403)  # Demo OTP cannot read actual excerpts.
        session=self.client.session;session['challenge_id']=str(ch.pk);session.save()
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400)
    def test_expired_otp(self):
        ch=self.challenge();ch.expires_at=timezone.now()-datetime.timedelta(seconds=1);ch.save()
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400)
    def test_otp_attempt_limit(self):
        ch=self.challenge()
        for _ in range(5):self.assertEqual(self.client.post('/otp/',{'code':'000000'}).status_code,400)
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400)
        ch.refresh_from_db();self.assertEqual(ch.attempts,5)
    def test_unknown_and_known_generic_response(self):
        unknown=self.client.post('/login/',{'name':'존재하지않는가상교인','phone':'01000000999'})
        known=self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone})
        from .views import GENERIC
        self.assertContains(unknown,GENERIC);self.assertContains(known,GENERIC)
        self.assertIsNone(Challenge.objects.order_by('expires_at').first().member)
    def test_resend_limit(self):
        with patch('portal.views.send_sms',return_value=True) as sender:
            for _ in range(2):self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone})
            self.assertEqual(sender.call_count,1)
    def test_shared_phone_denied(self):
        self.other.phone=self.member.phone;self.other.save()
        with patch('portal.views.send_sms') as sender:
            self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone});sender.assert_not_called()
        self.assertIsNone(Challenge.objects.latest('expires_at').member)
    @override_settings(DEV=False,SMS_API_KEY='',SMS_API_SECRET='',SMS_SENDER='')
    def test_no_sms_no_auth(self):
        response=self.client.post('/login/',{'name':self.member.name,'phone':self.member.phone})
        self.assertNotContains(response,'가상 발송 인증번호');self.assertIsNone(Challenge.objects.latest('expires_at').member)
    def test_development_real_member_denied(self):
        self.member.synthetic=False;self.member.save();self.challenge()
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400)
    def test_author_spoof_ignored(self):
        self.member_login()
        self.client.post('/posts/new/',{'title':'가상 글','body':'가상 본문','member':str(self.other.pk),'author_name':'위조 작성자'})
        post=Post.objects.get();self.assertEqual(post.member,self.member);self.assertEqual(post.author_name,self.member.name)
        self.assertNotContains(self.client.get(f'/posts/{post.pk}/'),self.member.phone)
    def test_other_post_edit_delete_blocked(self):
        post=Post.objects.create(member=self.other,author_name=self.other.name,title='가상 글',body='본문')
        self.member_login()
        self.assertEqual(self.client.post(f'/posts/{post.pk}/edit/',{'title':'침해','body':'침해'}).status_code,404)
        self.assertEqual(self.client.post(f'/posts/{post.pk}/delete/').status_code,404)
    def test_edit_revision_delete(self):
        self.member_login();self.client.post('/posts/new/',{'title':'가상 제목','body':'이전 본문'})
        post=Post.objects.get();self.client.post(f'/posts/{post.pk}/edit/',{'title':'새 제목','body':'새 본문'})
        post.refresh_from_db();self.assertTrue(post.edited);self.assertEqual(Revision.objects.get().body['body'],'이전 본문')
        self.client.post(f'/posts/{post.pk}/delete/');self.assertEqual(self.client.get(f'/posts/{post.pk}/').status_code,404)
    def test_csrf(self):
        client=Client(enforce_csrf_checks=True);self.member_login(client=client)
        self.assertEqual(client.post('/posts/new/',{'title':'가상','body':'가상'}).status_code,403)
        self.assertEqual(client.post('/logout/').status_code,403)
    def test_logout(self):
        self.member_login();self.client.post('/logout/');self.assertEqual(self.client.get('/').status_code,302)
    def test_xss_escaped(self):
        self.member_login();self.client.post('/posts/new/',{'title':'<script>alert(1)</script>','body':'<img src=x onerror=alert(1)>'})
        response=self.client.get(f'/posts/{Post.objects.get().pk}/')
        self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>')
    def test_mfa_required(self):
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get('/admin/'),'/admin-mfa/',fetch_redirect_response=False)
        self.assertEqual(self.client.post('/admin-mfa/',{'code':'000000'}).status_code,200)
        self.assertNotIn('admin_mfa_until',self.client.session)
    def test_roster_permission(self):
        self.staff_login();self.assertEqual(self.client.get('/roster/').status_code,403)
    def workbook(self,rows):
        book=Workbook();sheet=book.active;sheet.title='교인명부';sheet.append([]);sheet.append(['','이름','전화번호'])
        for name,num in rows:sheet.append(['',name,num])
        buff=io.BytesIO();book.save(buff)
        return SimpleUploadedFile('synthetic.xlsx',buff.getvalue())
    def test_roster_validation(self):
        rows,summary=parse(self.workbook([('가상교인A','010-0000-0001'),('가상교인C',1000000004),('가상교인C','01000000005'),('가상교인D','01000000005'),('가상교인E',None),('가상교인A','01000000001'),(None,None)]))
        self.assertEqual(len(rows),6);self.assertEqual(summary['duplicates'],2);self.assertEqual(summary['shared_phones'],4)
        self.assertIn('복구 후보',rows[1]['issue']);self.assertEqual(summary['missing_or_invalid'],2)
    def test_roster_reupload_and_change_preserves_id(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='change_member'));self.staff_login()
        post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상',body='가상')
        self.client.post('/roster/',{'file':self.workbook([(self.member.name,'01000000007')])})
        batch=RosterBatch.objects.get();self.assertEqual(batch.rows[0]['change_candidates'][0]['id'],str(self.member.pk))
        self.client.post('/roster/',{'batch':str(batch.pk),'action_3':str(self.member.pk),'confirmed':'yes'})
        self.member.refresh_from_db();post.refresh_from_db();self.assertEqual(self.member.phone,'01000000007');self.assertEqual(post.member_id,self.member.pk)
        self.other.refresh_from_db();self.assertTrue(self.other.active)
        self.client.post('/roster/',{'file':self.workbook([(self.member.name,self.member.phone)])})
        new=RosterBatch.objects.order_by('-created_at').first();self.client.post('/roster/',{'batch':str(new.pk),'action_3':str(self.member.pk),'confirmed':'yes'})
        self.assertEqual(Member.objects.count(),2)
    def test_exception_one_time_individual(self):
        ch=self.challenge(exception=True)
        token=f'{ch.pk}:123456'
        self.assertEqual(self.client.post('/exception/',{'token':token}).status_code,302)
        self.client.post('/logout/');self.client.post('/exception/',{'token':token})
        self.assertNotIn('member_id',self.client.session)
    def test_private_request_visibility(self):
        self.member_login();self.client.post('/requests/',{'kind':'correction','body':'가상 정정 요청'})
        self.assertEqual(Request.objects.get().member,self.member)
        self.member_login(self.other);self.assertNotContains(self.client.get('/requests/'),'가상 정정 요청')
    def test_documents_private_original_and_reading(self):
        with tempfile.TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=directory):
            doc=Document.objects.create(case=self.case,title='가상 PDF',original=SimpleUploadedFile('original.pdf',b'%PDF-1.4 synthetic'),reading=SimpleUploadedFile('reading.pdf',b'%PDF-1.4 redacted'),source='가상',acquired_on='2026-01-01',excerpt='가상',redaction_checked=True,state='published')
            self.case.state='published';self.case.save()
            self.assertEqual(Path(doc.original.path).stat().st_mode & 0o777,0o600)
            self.assertEqual(self.client.get(f'/documents/{doc.pk}/reading/').status_code,403)
            self.member_login();self.assertEqual(self.client.get(f'/documents/{doc.pk}/reading/').status_code,200)
            self.assertEqual(self.client.get(f'/documents/{doc.pk}/original/').status_code,403)
            doc.redaction_checked=False;doc.save();self.assertEqual(self.client.get(f'/documents/{doc.pk}/reading/').status_code,403)
            self.assertEqual(self.client.get('/media/reading/reading.pdf').status_code,404)
    def test_case_review_required_and_mobile_order(self):
        self.case.reviewer=self.case.author
        with self.assertRaises(__import__('django').core.exceptions.ValidationError): self.case.full_clean()
        self.staff.user_permissions.add(Permission.objects.get(codename='view_case'));self.staff_login()
        response=self.client.get(f'/admin/portal/case/{self.case.pk}/preview/')
        self.assertContains(response,'grid-template-columns:1fr')
        html=response.content.decode();self.assertLess(html.index('01 · 사건'),html.index('02 · 관련'));self.assertLess(html.index('02 · 관련'),html.index('03 · 현재'))
    def test_draft_hidden(self):
        self.case.state='draft';self.case.save();self.member_login()
        self.assertRedirects(self.client.get(f'/cases/{self.case.pk}/'),f'/#material-E{self.case.pk:02}',fetch_redirect_response=False)
        self.assertNotContains(self.client.get('/'),self.case.title)
    def test_security_headers(self):
        response=self.client.get('/login/');self.assertEqual(response['Cache-Control'],'no-store, private');self.assertIn("script-src 'self'",response['Content-Security-Policy'])
    def case_payload(self,state):
        return {'title':self.case.title,'occurred_on':'2026-01-01','topic':self.case.topic,'state':state,'timeline':'','facts':'','claims':'','unknown':'','status':'','decisions':'','responses':'','issues':'','opinion':'','review_summary':self.case.review_summary,'occurred_precision':'day','sources_reviewed':'on','privacy_reviewed':'on','publication_reason':'가상 자료 검토 확인'}
    def test_admin_author_cannot_self_approve(self):
        self.staff.user_permissions.add(*Permission.objects.filter(codename__in=['change_case','publish_case']))
        self.staff_login();self.case.state='review';self.case.save()
        response=self.client.post(f'/admin/portal/case/{self.case.pk}/change/',self.case_payload('published'))
        self.assertEqual(response.status_code,200);self.case.refresh_from_db();self.assertEqual(self.case.state,'review')
    def test_admin_independent_publish(self):
        self.approver.user_permissions.add(*Permission.objects.filter(codename__in=['change_case','publish_case']))
        self.client.force_login(self.approver);session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        self.case.state='review';self.case.last_editor=self.staff;self.case.save()
        response=self.client.post(f'/admin/portal/case/{self.case.pk}/change/',self.case_payload('published'))
        self.assertEqual(response.status_code,302);self.case.refresh_from_db();self.assertEqual(self.case.state,'published');self.assertEqual(self.case.reviewer,self.approver)
    def test_last_editor_cannot_approve(self):
        self.approver.user_permissions.add(*Permission.objects.filter(codename__in=['change_case','publish_case']))
        self.client.force_login(self.approver);session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        self.case.state='review';self.case.last_editor=self.approver;self.case.save()
        response=self.client.post(f'/admin/portal/case/{self.case.pk}/change/',self.case_payload('published'))
        self.assertEqual(response.status_code,200);self.case.refresh_from_db();self.assertEqual(self.case.state,'review')
    def test_article_edit_resets_approval(self):
        from .admin import ArticleAdmin
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        article=Article(case=self.case,citation='가상 테스트',text='가상',source='https://www.pck.or.kr/',effective_on='2025-01-01',amended_on='2025-01-01',checked_on='2026-01-01',relevance='가상')
        request=RequestFactory().post('/');request.user=self.staff
        form=type('Form',(),{'cleaned_data':{}})()
        ArticleAdmin(Article,AdminSite()).save_model(request,article,form,False)
        self.case.refresh_from_db();self.assertEqual(self.case.state,'review');self.assertIsNone(self.case.reviewer);self.assertEqual(self.case.last_editor,self.staff)
    def test_article_official_sources_and_no_retroactive_rule(self):
        article=Article(case=self.case,citation='가상',text='가상',source='https://unverified.example/',effective_on=datetime.date(2025,1,1),amended_on=datetime.date(2025,1,1),checked_on=datetime.date(2026,1,1),relevance='가상',verified=True,applicable=True)
        with self.assertRaises(__import__('django').core.exceptions.ValidationError):article.full_clean()
        article.source='https://www.pck.or.kr/';article.amendment_source='https://www.pck.or.kr/';article.effective_on=datetime.date(2027,1,1)
        with self.assertRaises(__import__('django').core.exceptions.ValidationError):article.full_clean()
    def test_stale_roster_does_not_overwrite(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='change_member'));self.staff_login()
        self.client.post('/roster/',{'file':self.workbook([(self.member.name,'01000000007')])})
        batch=RosterBatch.objects.get();self.member.phone='01000000008';self.member.save()
        response=self.client.post('/roster/',{'batch':str(batch.pk),'action_3':str(self.member.pk),'confirmed':'yes'})
        self.assertEqual(response.status_code,200);self.member.refresh_from_db();self.assertEqual(self.member.phone,'01000000008')
    def test_unknown_otp_no_account_created(self):
        before=Member.objects.count();self.client.post('/login/',{'name':'가상미등록','phone':'01000000999'})
        self.assertEqual(self.client.post('/otp/',{'code':'123456'}).status_code,400);self.assertEqual(Member.objects.count(),before)
    @override_settings(ADMIN_MFA_SECRETS={'test-editor':'JBSWY3DPEHPK3PXP'})
    def test_individual_mfa_and_replay(self):
        import base64,hashlib,hmac,struct,time
        secret=base64.b32decode('JBSWY3DPEHPK3PXP');counter=int(time.time()/30)
        raw=hmac.new(secret,struct.pack('>Q',counter),hashlib.sha1).digest();index=raw[-1]&15
        code=f'{(struct.unpack(">I",raw[index:index+4])[0]&0x7fffffff)%1000000:06d}'
        self.client.force_login(self.staff);self.assertEqual(self.client.post('/admin-mfa/',{'code':code}).status_code,302)
        session=self.client.session;del session['admin_mfa_until'];session.save()
        self.assertEqual(self.client.post('/admin-mfa/',{'code':code}).status_code,200)
        self.assertNotIn('admin_mfa_until',self.client.session)
        self.client.force_login(self.approver);self.client.post('/admin-mfa/',{'code':code});self.assertNotIn('admin_mfa_until',self.client.session)
    def test_only_approved_correction_summary_public(self):
        self.approver.user_permissions.add(*Permission.objects.filter(codename__in=['change_case','publish_case']))
        self.case.state='review';self.case.last_editor=self.staff;self.case.review_summary='가상 정정 요약';self.case.save()
        self.member_login();self.assertRedirects(self.client.get(f'/cases/{self.case.pk}/'),f'/#material-E{self.case.pk:02}',fetch_redirect_response=False)
        self.client.force_login(self.approver);session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        response=self.client.post(f'/admin/portal/case/{self.case.pk}/change/',self.case_payload('published'))
        self.assertEqual(response.status_code,302);self.assertEqual(ChangeNote.objects.get().summary,'가상 정정 요약')
        self.approver.user_permissions.add(Permission.objects.get(codename='view_case'))
        self.assertContains(self.client.get(f'/admin/portal/case/{self.case.pk}/preview/'),'가상 정정 요약')
        self.member_login();self.assertNotContains(self.client.get('/'),'가상 정정 요약')
