import io
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from .models import Member, Post, CaseComment, Audit, AccessApplication

@override_settings(DEV=True, SECURE_SSL_REDIRECT=False)
class DemoActivationTests(TestCase):
    def run_command(self, enable=True):
        call_command('seed_demo', enable_login=enable, stdout=io.StringIO())

    def test_explicit_activation_preserves_existing_id_posts_and_comments_and_is_repeatable(self):
        member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True,active=False)
        post=Post.objects.create(member=member,author_name=member.name,title='가상 기존 글',body='가상 보존')
        comment=CaseComment.objects.create(member=member,author_name=member.name,reading_key='E01',body='가상 기존 의견')
        self.run_command();member.refresh_from_db();version=member.session_version
        self.assertTrue(member.active and member.legacy_operator)
        self.run_command();member.refresh_from_db()
        self.assertEqual(member.session_version,version)
        self.assertEqual(Member.objects.count(),1)
        self.assertEqual(Post.objects.get(pk=post.pk).member_id,member.pk)
        self.assertEqual(CaseComment.objects.get(pk=comment.pk).body,'가상 기존 의견')
        self.assertEqual(Audit.objects.filter(action='synthetic_login_enable').count(),1)
        self.assertEqual(AccessApplication.objects.count(),0)
        self.assertRedirects(self.client.post('/login/',{'name':'가상교인','phone':'01000000000'}),'/',fetch_redirect_response=False)
        self.assertContains(self.client.get('/'),'공동 상황판')
        self.assertContains(self.client.get('/cases/material/E01/'),'가상 기존 의견')

    def test_new_demo_requires_explicit_option_and_has_no_admin_account(self):
        self.run_command(enable=False)
        self.assertFalse(Member.objects.get().legacy_operator)
        self.assertEqual(self.client.post('/login/',{'name':'가상교인','phone':'01000000000'}).status_code,200)
        self.run_command()
        self.assertEqual(self.client.post('/login/',{'name':'가상교인','phone':'01000000000'}).status_code,302)
        self.assertEqual(self.client.get('/admin/').status_code,302)
        from django.contrib.auth.models import User
        self.assertEqual(User.objects.count(),0)

    def test_production_real_roster_and_conflicting_records_are_never_changed(self):
        with override_settings(DEV=False):
            with self.assertRaises(CommandError): self.run_command()
        self.assertEqual(Member.objects.count(),0)
        member=Member.objects.create(name='가상 실제명부표시',phone='01000000001',synthetic=False)
        with self.assertRaises(CommandError): self.run_command()
        self.assertEqual(Member.objects.count(),1)
        member.delete()
        Member.objects.create(name='가상 다른 계정',phone='01000000000',synthetic=True)
        with self.assertRaises(CommandError): self.run_command()
        self.assertEqual(Member.objects.count(),1)

    def test_synthetic_login_and_existing_session_cannot_read_production_or_mixed_data(self):
        self.run_command()
        self.client.post('/login/',{'name':'가상교인','phone':'01000000000'})
        self.assertEqual(self.client.get('/').status_code,200)
        with override_settings(DEV=False):
            self.assertEqual(self.client.get('/cases/material/E01/').status_code,302)
            self.assertEqual(self.client.post('/login/',{'name':'가상교인','phone':'01000000000'}).status_code,200)
        self.client.post('/login/',{'name':'가상교인','phone':'01000000000'})
        Member.objects.create(name='가상 명부 유입',phone='01000000001',synthetic=False)
        self.assertEqual(self.client.get('/cases/material/E01/').status_code,302)
        self.assertEqual(self.client.post('/login/',{'name':'가상교인','phone':'01000000000'}).status_code,200)
