"""Only fictional members and opinions. Do not print confidential reading HTML."""
import datetime
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.core.exceptions import ValidationError
from django.core.management import call_command
from .models import Member, CaseComment, Challenge, Revision, Request, Post, Case, Article, Document
from .security import digest

@override_settings(SECURE_SSL_REDIRECT=False, DEV=True)
class DiscussionTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상 작성자',phone='01000000000',synthetic=True)
        self.other=Member.objects.create(name='가상 작성자',phone='01000000001',synthetic=True,label='가상 구분')
        self.roster()
    def roster(self, member=None):
        member=member or self.member
        self.client.logout()
        session=self.client.session
        session.update({'member_id':str(member.pk),'member_version':member.session_version,'member_auth':'roster'})
        session.save()
    def verify(self,member=None):
        member=member or self.member
        ch=Challenge(member=member,version=member.session_version,exception=True,expires_at=timezone.now()+datetime.timedelta(minutes=15))
        ch.digest=digest(str(ch.pk),'fictional-one-use-token');ch.save()
        response=self.client.post('/exception/',{'token':f'{ch.pk}:fictional-one-use-token'})
        self.assertEqual(response.status_code,302)
        return ch
    def create(self,key='E01',parent=None,body='가상 의견'):
        data={'body':body}
        if parent: data['parent']=parent.pk
        return self.client.post(f'/comments/{key}/',data)
    def test_weak_session_cannot_write_and_exception_is_one_use_expiring(self):
        self.assertEqual(self.create().status_code,403)
        ch=self.verify()
        self.assertEqual(self.create().status_code,302)
        self.assertEqual(CaseComment.objects.get().member_id,self.member.pk)
        self.assertEqual(CaseComment.objects.get().author_name,self.member.name)
        self.assertTrue(CaseComment.objects.get().author_label.startswith('교인 '))
        self.client.post('/logout/')
        self.client.post('/exception/',{'token':f'{ch.pk}:fictional-one-use-token'})
        self.assertNotIn('identity_member',self.client.session)
        self.roster();self.assertEqual(self.create().status_code,403)
        self.verify();session=self.client.session;session['identity_until']=0;session.save()
        self.assertEqual(self.create().status_code,403)
    def test_threads_edit_delete_and_private_history(self):
        self.verify();self.create();parent=CaseComment.objects.get()
        self.create(parent=parent,body='가상 답글');child=CaseComment.objects.exclude(pk=parent.pk).get()
        self.assertEqual(child.parent_id,parent.pk)
        self.assertEqual(self.create(parent=child).status_code,400)
        self.assertEqual(self.create(key='E02',parent=parent).status_code,400)
        self.assertEqual(self.client.post(f'/comments/E01/{parent.pk}/',{'action':'edit','body':'수정한 가상 의견'}).status_code,302)
        self.assertEqual(Revision.objects.get(target=f'comment:{parent.pk}').body['body'],'가상 의견')
        self.verify(self.other)
        for action in ('edit','delete'):
            self.assertEqual(self.client.post(f'/comments/E01/{parent.pk}/',{'action':action,'body':'금지'}).status_code,404)
        self.verify();self.client.post(f'/comments/E01/{parent.pk}/',{'action':'delete'})
        html=self.client.get('/').content.decode()
        self.assertTrue('작성자가 삭제한 의견입니다.' in html and '가상 답글' in html)
        self.assertFalse('수정한 가상 의견' in html)
        self.assertEqual(CaseComment.objects.get(pk=child.pk).parent_id,parent.pk)
    def test_spoof_unknown_parent_model_validation_rate_and_csrf(self):
        self.verify()
        for field in ('member_id','author_name','author_id'):
            self.assertEqual(self.client.post('/comments/E01/',{'body':'가상 의견',field:'위조'}).status_code,400)
        self.assertEqual(self.create(key='E31').status_code,404)
        self.assertEqual(self.client.post('/comments/E01/',{'body':'가상 유지','parent':'invalid'}).status_code,400)
        self.assertEqual(CaseComment.objects.count(),0)
        root=CaseComment.objects.create(member=self.member,author_name=self.member.name,reading_key='E01',body='가상')
        with self.assertRaises(ValidationError):
            CaseComment(reading_key='E02',member=self.member,author_name=self.member.name,body='가상',parent=root).full_clean()
        secure=Client(enforce_csrf_checks=True)
        session=secure.session;session.update(dict(self.client.session));session.save()
        self.assertEqual(secure.post('/comments/E01/',{'body':'가상'}).status_code,403)
        from unittest.mock import patch
        with patch('portal.discussions.limit',return_value=False):
            response=self.create(body='보존할 가상 입력')
            self.assertEqual(response.status_code,429)
            self.assertTrue('보존할 가상 입력' in response.content.decode())
    def test_escaping_hidden_private_requests_and_verified_display(self):
        self.verify();self.create(body='<script>fictional()</script>');comment=CaseComment.objects.get()
        response=self.client.get('/');html=response.content.decode()
        self.assertFalse('<script>fictional()' in html);self.assertTrue('&lt;script&gt;fictional()' in html)
        self.assertFalse(self.member.phone in html)
        self.assertTrue('no-store' in response['Cache-Control'] and 'private' in response['Cache-Control'])
        self.assertEqual(response['X-Robots-Tag'],'noindex, nofollow')
        comment.hidden=True;comment.moderation_reason='privacy';comment.moderation_note='가상 비공개 근거';comment.save()
        html=self.client.get('/').content.decode()
        self.assertFalse('fictional()' in html or '가상 비공개 근거' in html)
        self.assertTrue('개인정보 노출' in html)
        response=self.client.post('/requests/',{'kind':'response','reading_key':'E01','comment':comment.pk,'body':'가상 비공개 반론'})
        self.assertEqual(response.status_code,302)
        item=Request.objects.get();self.assertEqual(item.comment_id,comment.pk)
        self.assertFalse('가상 비공개 반론' in self.client.get('/').content.decode())
        self.verify(self.other)
        self.assertFalse('가상 비공개 반론' in self.client.get('/requests/').content.decode())
        self.assertEqual(self.client.post('/requests/',{'kind':'report','reading_key':'E02','comment':comment.pk,'body':'가상'}).status_code,200)
        item.public_excerpt='가상 검토된 공개 반론';item.public_approved=True;item.full_clean();item.save()
        html=self.client.get('/').content.decode()
        self.assertTrue('가상 검토된 공개 반론' in html);self.assertFalse('가상 비공개 반론' in html)
    def test_all_records_and_batched_queries_survive_without_case_db(self):
        self.verify()
        for i in range(1,31):
            self.create(key=f'E{i:02}',body=f'가상 토론 {i}')
        with CaptureQueriesContext(connection) as queries: response=self.client.get('/')
        html=response.content.decode()
        self.assertEqual(html.count('class="case-group direct-case"'),30)
        self.assertEqual(html.count('class="reading-area"'),120)
        self.assertEqual(html.count('⑤ 성도님의 생각'),30)
        self.assertEqual(sum('FROM "portal_casecomment"' in q['sql'] for q in queries.captured_queries),1)
        self.assertEqual((Case.objects.count(),Article.objects.count(),Document.objects.count()),(0,0,0))
        for i in range(1,31): self.assertTrue(f'id="discussion-E{i:02}"' in html)
    def test_inactive_and_guest_no_read_or_write_admin_not_member(self):
        self.verify();self.create(body='가상 보호의견')
        self.member.active=False;self.member.save()
        for url in ('/','/comments/E01/','/portal/templates/portal/direct_case_reading.html'):
            response=self.client.get(url);self.assertEqual(response.status_code,302)
            self.assertFalse('가상 보호의견' in response.content.decode())
        self.assertEqual(self.client.post('/comments/E01/',{'body':'가상'}).status_code,302)
        from django.contrib.auth.models import User,Permission
        admin=User.objects.create_user('fictional-admin',is_staff=True)
        admin.user_permissions.add(Permission.objects.get(codename='view_case'))
        self.client.force_login(admin);session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        response=self.client.get('/');self.assertEqual(response.status_code,200)
        self.assertTrue('교인 명의의 의견을 작성할 수 없습니다' in response.content.decode())
        self.assertEqual(self.client.post('/comments/E01/',{'body':'가상'}).status_code,302)
    def test_post_links_retention_and_existing_data(self):
        old=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 기존 글',body='보존')
        self.verify();self.create();comment=CaseComment.objects.get()
        self.assertEqual(self.client.post('/posts/new/',{'title':'가상 연결','body':'가상','reading_key':'E30'}).status_code,302)
        self.assertEqual(Post.objects.exclude(pk=old.pk).get().reading_key,'E30')
        self.assertEqual(Post.objects.get(pk=old.pk).member_id,self.member.pk)
        CaseComment.objects.filter(pk=comment.pk).update(deleted_at=timezone.now()-datetime.timedelta(days=31))
        Revision.objects.create(target=f'comment:{comment.pk}',actor=str(self.member.pk),body={'body':'가상 이력'})
        Revision.objects.update(created_at=timezone.now()-datetime.timedelta(days=91))
        call_command('purge_private',verbosity=0)
        comment.refresh_from_db();self.assertEqual(comment.body,'');self.assertEqual(Revision.objects.count(),0)

from django.test import TransactionTestCase
from django.db.migrations.executor import MigrationExecutor

class DiscussionMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_member_post_request_and_case_ids(self):
        old=('portal','0009_alter_reviewedmaterialimport_source_digest')
        new=('portal','0010_member_discussions')
        executor=MigrationExecutor(connection)
        executor.migrate([old])
        try:
            apps=executor.loader.project_state([old]).apps
            member=apps.get_model('portal','Member').objects.create(name='가상 이관 검증',phone='01000000000')
            user=apps.get_model('auth','User').objects.create(username='fictional-migration')
            case=apps.get_model('portal','Case').objects.create(title='가상 보존 사건',topic='가상',occurred_precision='unknown',author_id=user.pk)
            post=apps.get_model('portal','Post').objects.create(member_id=member.pk,author_name=member.name,title='가상 보존 글',body='가상 보존 본문',case_id=case.pk)
            item=apps.get_model('portal','Request').objects.create(member_id=member.pk,kind='correction',case_id=case.pk,post_id=post.pk,body='가상 보존 요청')
        finally:
            executor=MigrationExecutor(connection);executor.migrate([new])
        self.assertEqual(Member.objects.get(pk=member.pk).name,'가상 이관 검증')
        self.assertEqual(Post.objects.get(pk=post.pk).case_id,case.pk)
        self.assertEqual(Post.objects.get(pk=post.pk).reading_key,'')
        self.assertEqual(Request.objects.get(pk=item.pk).post_id,post.pk)
        self.assertEqual(Request.objects.get(pk=item.pk).case_id,case.pk)
        self.assertEqual(CaseComment.objects.count(),0)

@override_settings(SECURE_SSL_REDIRECT=False, DEV=True)
class DiscussionAdministrationTests(TestCase):
    def test_moderator_cannot_rewrite_and_private_revisions_require_admin_mfa(self):
        from django.contrib.auth.models import User, Permission
        member=Member.objects.create(name='가상 관리자 검증',phone='01000000000',synthetic=True)
        item=CaseComment.objects.create(member=member,author_name=member.name,reading_key='E01',body='가상 보존 의견')
        user=User.objects.create_user('fictional-moderator',is_staff=True)
        user.user_permissions.add(*Permission.objects.filter(codename__in=['view_casecomment','change_casecomment','view_revision'],content_type__app_label='portal'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(f'/admin/portal/casecomment/{item.pk}/change/').status_code,302)
        session=self.client.session;session['admin_mfa_until']=timezone.now().timestamp()+300;session.save()
        response=self.client.post(f'/admin/portal/casecomment/{item.pk}/change/',{'hidden':'on','moderation_reason':'privacy','moderation_note':'가상 내부 근거','body':'금지된 대필','author_name':'금지된 작성자','_save':'저장'})
        self.assertEqual(response.status_code,302)
        item.refresh_from_db();self.assertTrue(item.hidden)
        self.assertEqual(item.body,'가상 보존 의견');self.assertEqual(item.author_name,member.name)
        self.assertEqual(Revision.objects.get(target=f'casecomment:{item.pk}').body['body'],'가상 보존 의견')
        self.client.logout()
        session=self.client.session;session.update({'member_id':str(member.pk),'member_version':member.session_version,'member_auth':'exception'});session.save()
        self.assertEqual(self.client.post('/comments/E01/',{'body':'검증되지 않은 과거 세션'}).status_code,403)
        self.assertEqual(self.client.get('/admin/portal/revision/').status_code,302)
