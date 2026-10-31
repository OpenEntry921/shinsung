"""Exercise deployment startup on isolated databases containing only fabricated data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from .models import Challenge, Member

@override_settings(DEV=True,SECURE_SSL_REDIRECT=False,SMS_API_KEY='',SMS_API_SECRET='',SMS_SENDER='')
class DemoLoginTests(TestCase):
    def test_demo_and_existing_members_are_not_automatically_authorized(self):
        call_command('seed_demo',verbosity=0)
        member=Member.objects.get()
        self.client.post('/login/', {'name': member.name, 'phone': member.phone})
        self.assertNotIn('member_id', self.client.session)
        self.assertEqual(self.client.get('/').status_code,302)



class DevelopmentStartupTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='shinsung-startup-test-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root = Path(__file__).resolve().parent.parent
        self.events = self.directory / 'events'
        self.bin = self.directory / 'bin'
        self.bin.mkdir()
        # Keep both SQLite and collectstatic outputs outside the checkout.
        (self.directory / 'startup_test_settings.py').write_text(
            'from config.settings import *\n'
            f'STATIC_ROOT = {str(self.directory / "static")!r}\n'
        )
        python_wrapper = textwrap.dedent('''\
            import os, subprocess, sys
            from pathlib import Path
            event = Path(os.environ['STARTUP_TEST_EVENTS'])
            command = sys.argv[2]
            with event.open('a') as stream: stream.write(command + ':start\\n')
            result = subprocess.run([sys.executable, *sys.argv[1:]])
            with event.open('a') as stream:
                stream.write(command + (':end\\n' if result.returncode == 0 else ':failed\\n'))
            raise SystemExit(result.returncode)
        ''')
        # Record the unchanged final command; do not open a server port during unit tests.
        gunicorn_wrapper = textwrap.dedent('''\
            import os, sys
            from pathlib import Path
            with Path(os.environ['STARTUP_TEST_EVENTS']).open('a') as stream:
                stream.write('gunicorn:' + ' '.join(sys.argv[1:]) + '\\n')
        ''')
        for name, contents in [('python', python_wrapper), ('gunicorn', gunicorn_wrapper)]:
            script = self.bin / name
            script.write_text(f'#!{sys.executable}\n' + contents)
            script.chmod(0o700)
        self.environment = dict(
            os.environ,
            DJANGO_SETTINGS_MODULE='startup_test_settings',
            DJANGO_SECRET_KEY='synthetic-startup-test-secret-never-use-in-production',
            DATA_DIR=str(self.directory / 'data'),
            PYTHONPATH=os.pathsep.join([str(self.directory), str(self.root)]),
            PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
            STARTUP_TEST_EVENTS=str(self.events),
        )

    def startup(self, mode, demo=None):
        environment = dict(self.environment)
        if mode is None:
            environment.pop('APP_MODE', None)
        else:
            environment['APP_MODE'] = mode
        environment.pop('DEMO_LOGIN_ENABLED', None)
        if demo is not None: environment['DEMO_LOGIN_ENABLED'] = demo
        self.events.write_text('')
        result = subprocess.run(
            ['sh', 'scripts/start-production.sh'], cwd=self.root, env=environment,
            capture_output=True, text=True, timeout=40,
        )
        events = self.events.read_text().splitlines()
        return result, events

    def manage(self, *arguments):
        environment = dict(self.environment, APP_MODE='development')
        return subprocess.run(
            [sys.executable, 'manage.py', *arguments], cwd=self.root, env=environment,
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout

    def snapshot(self):
        output = self.manage('shell', '-c',
            "import json; from portal.models import Member,Post; "
            "print(json.dumps({'members':list(Member.objects.values('id','name','phone','synthetic')), "
            "'posts':list(Post.objects.values('id','member_id','body'))},default=str))")
        return json.loads(output.splitlines()[-1])

    def assert_order(self, events, seeded):
        expected = ['migrate:start', 'migrate:end']
        if seeded: expected += ['seed_demo:start', 'seed_demo:end']
        expected += ['bootstrap_roles:start', 'bootstrap_roles:end', 'collectstatic:start', 'collectstatic:end']
        self.assertEqual(events[:-1], expected)
        self.assertEqual(events[-1], 'gunicorn:config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --timeout 30 --error-logfile -')

    def test_empty_development_db_and_repeat_preserve_id_and_post(self):
        result, events = self.startup('development')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_order(events, seeded=False)
        before = self.snapshot()
        self.assertEqual(before['members'], [])
        self.manage('shell', '-c', "from portal.models import Member; Member.objects.create(name='가상',phone='01000000000',synthetic=True)")
        member = self.snapshot()['members'][0]
        self.manage('shell', '-c',
            "from portal.models import Member,Post; m=Member.objects.get(); "
            "Post.objects.create(member=m,author_name=m.name,title='가상 테스트 글',body='가상 보존 확인')")
        with_post = self.snapshot()
        result, events = self.startup('development')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_order(events, seeded=False)
        self.assertEqual(self.snapshot(), with_post)
        self.assertEqual(self.snapshot()['posts'][0]['member_id'], member['id'])

    def test_production_missing_and_invalid_modes_do_not_seed(self):
        for mode in ('production', None, '', 'Development', 'invalid'):
            with self.subTest(mode=mode):
                result, events = self.startup(mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_order(events, seeded=False)
                self.assertEqual(self.snapshot()['members'], [])
                environment = dict(self.environment)
                if mode is None: environment.pop('APP_MODE', None)
                else: environment['APP_MODE'] = mode
                subprocess.run(
                    [sys.executable, '-c', 'from django.conf import settings; assert not settings.DEV; assert settings.SESSION_COOKIE_SECURE; assert settings.SECURE_SSL_REDIRECT'],
                    cwd=self.root, env=environment, capture_output=True, text=True, check=True,
                )

    def test_roster_refusal_stops_startup_and_preserves_data_without_pii_error(self):
        self.manage('migrate', '--noinput')
        self.manage('shell', '-c',
            "from portal.models import Member,Post; "
            "m=Member.objects.create(name='가상테스트명부',phone='01000000009',synthetic=False); "
            "Post.objects.create(member=m,author_name=m.name,title='가상 보존 글',body='가상 보존 확인')")
        before = self.snapshot()
        result, events = self.startup('development')
        self.assertEqual(result.returncode, 0)
        self.assert_order(events, seeded=False)
        self.assertNotIn('가상테스트명부', result.stdout + result.stderr)
        self.assertNotIn('01000000009', result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_opt_in_startup_prepares_login_and_restart_preserves_member_and_comment(self):
        result, events = self.startup('development', demo='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_order(events, seeded=True)
        self.manage('shell', '-c',
            "from django.test import Client; from portal.models import Member,CaseComment,AccessApplication; "
            "m=Member.objects.get(); assert m.synthetic and m.active and m.legacy_operator; "
            "assert AccessApplication.objects.count()==0; c=Client(); "
            "r=c.post('/login/',{'name':'가상교인','phone':'01000000000'}); assert r.status_code==302 and r.url=='/'; "
            "assert c.get('/').status_code==200; "
            "assert all(c.get(f'/cases/material/E{i:02}/').status_code==200 for i in range(1,31)); "
            "r=c.post('/comments/E01/',{'body':'가상 시작 검증 의견'}); assert r.status_code==302")
        before = self.manage('shell', '-c',
            "import json; from portal.models import Member,CaseComment,Audit; "
            "print(json.dumps({'member':list(Member.objects.values_list('id','session_version')), "
            "'comments':list(CaseComment.objects.values_list('id','member_id','reading_key','body')), "
            "'grants':Audit.objects.filter(action='synthetic_login_enable').count()},default=str))").splitlines()[-1]
        result, events = self.startup('development', demo='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_order(events, seeded=True)
        after = self.manage('shell', '-c',
            "import json; from portal.models import Member,CaseComment,Audit; "
            "print(json.dumps({'member':list(Member.objects.values_list('id','session_version')), "
            "'comments':list(CaseComment.objects.values_list('id','member_id','reading_key','body')), "
            "'grants':Audit.objects.filter(action='synthetic_login_enable').count()},default=str))").splitlines()[-1]
        self.assertEqual(before, after)
        self.manage('shell', '-c',
            "from django.test import Client; from portal.models import CaseComment; c=Client(); "
            "assert c.post('/login/',{'name':'가상교인','phone':'01000000000'}).status_code==302; "
            "comment=CaseComment.objects.get(); "
            "assert c.post(f'/comments/E01/{comment.pk}/',{'action':'delete'}).status_code==302; "
            "comment.refresh_from_db(); assert comment.deleted_at is not None")

    def test_opt_in_rejects_production_and_real_roster_without_starting_gunicorn(self):
        result, events = self.startup('production', demo='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, ['migrate:start','migrate:end','seed_demo:start','seed_demo:failed'])
        self.assertEqual(self.snapshot()['members'], [])
        self.manage('shell', '-c',
            "from portal.models import Member; Member.objects.create(name='가상실제명부구분',phone='01000000009',synthetic=False)")
        before = self.snapshot()
        result, events = self.startup('development', demo='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1], 'seed_demo:failed')
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn('가상실제명부구분', result.stdout + result.stderr)

    def test_non_true_demo_values_do_not_enable_login(self):
        for value in ('false', '', 'True', '1'):
            with self.subTest(value=value):
                result, events = self.startup('development', demo=value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_order(events, seeded=False)
                self.assertEqual(self.snapshot()['members'], [])
