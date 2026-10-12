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

NOTICE = '가상 데이터 시연 환경입니다. 실제 문자는 발송하지 않으며, 실제 교인 명부를 등록하지 마세요.'


@override_settings(DEV=True, SECURE_SSL_REDIRECT=False, SMS_API_KEY='', SMS_API_SECRET='', SMS_SENDER='')
class DemoLoginTests(TestCase):
    def test_development_notice_and_synthetic_code_without_sms(self):
        call_command('seed_demo', verbosity=0)
        self.assertContains(self.client.get('/login/'), NOTICE)
        with patch('portal.security.requests.post') as sender:
            response = self.client.post('/login/', {'name': '가상교인', 'phone': '01000000000'})
        sender.assert_not_called()
        self.assertContains(response, NOTICE)
        self.assertContains(response, '가상 발송 인증번호')
        self.assertIsNotNone(Challenge.objects.get().member)

    def test_non_synthetic_record_never_gets_development_code(self):
        # A fabricated fixture with synthetic=False represents a roster record.
        Member.objects.create(name='가상테스트명부', phone='01000000009', synthetic=False)
        response = self.client.post('/login/', {'name': '가상테스트명부', 'phone': '01000000009'})
        self.assertNotContains(response, '가상 발송 인증번호')
        self.assertIsNone(Challenge.objects.get().member)

    def test_notice_remains_on_failed_code_entry(self):
        self.assertContains(self.client.post('/otp/', {'code': '000000'}), NOTICE, status_code=400)

    @override_settings(DEV=False)
    def test_production_no_seed_no_notice_no_code_or_auth_without_sms(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo')
        self.assertEqual(Member.objects.count(), 0)
        Member.objects.create(name='가상교인', phone='01000000000', synthetic=True)
        self.assertNotContains(self.client.get('/login/'), NOTICE)
        response = self.client.post('/login/', {'name': '가상교인', 'phone': '01000000000'})
        self.assertNotContains(response, NOTICE)
        self.assertNotContains(response, '가상 발송 인증번호')
        self.assertIsNone(Challenge.objects.get().member)
        self.assertEqual(self.client.post('/otp/', {'code': '000000'}).status_code, 400)
        self.assertNotIn('member_id', self.client.session)


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

    def startup(self, mode):
        environment = dict(self.environment)
        if mode is None:
            environment.pop('APP_MODE', None)
        else:
            environment['APP_MODE'] = mode
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
        if seeded:
            expected += ['seed_demo:start', 'seed_demo:end']
        expected += ['bootstrap_roles:start', 'bootstrap_roles:end', 'collectstatic:start', 'collectstatic:end']
        self.assertEqual(events[:-1], expected)
        self.assertEqual(events[-1], 'gunicorn:config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --timeout 30 --error-logfile -')

    def test_empty_development_db_and_repeat_preserve_id_and_post(self):
        result, events = self.startup('development')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_order(events, seeded=True)
        before = self.snapshot()
        self.assertEqual(len(before['members']), 1)
        member = before['members'][0]
        self.assertEqual((member['name'], member['phone'], member['synthetic']), ('가상교인', '01000000000', True))
        self.manage('shell', '-c',
            "from portal.models import Member,Post; m=Member.objects.get(); "
            "Post.objects.create(member=m,author_name=m.name,title='가상 테스트 글',body='가상 보존 확인')")
        with_post = self.snapshot()
        result, events = self.startup('development')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_order(events, seeded=True)
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
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, ['migrate:start', 'migrate:end', 'seed_demo:start', 'seed_demo:failed'])
        self.assertIn('실제 명부가 있는 DB에는 시연 데이터를 추가하지 않습니다.', result.stderr)
        self.assertNotIn('가상테스트명부', result.stdout + result.stderr)
        self.assertNotIn('01000000009', result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
