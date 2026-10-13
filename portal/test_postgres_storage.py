"""Fictional records only. PostgreSQL-specific tests run against a local test DB."""
import hashlib, io, sqlite3, tempfile
from pathlib import Path
from unittest import skipUnless
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.contrib.sessions.models import Session
from .models import Member, Post, Challenge
from config.database import postgres

class DatabaseConfigurationTests(SimpleTestCase):
    def test_url_and_tls_validation(self):
        config=postgres('postgresql://fictional:p%40ss@localhost:5432/fictional?sslmode=verify-full')
        self.assertEqual(config['PASSWORD'],'p@ss')
        self.assertEqual(config['OPTIONS']['sslmode'],'verify-full')
        self.assertEqual(postgres('postgresql://fictional@localhost/fictional')['OPTIONS']['sslmode'],'verify-full')
        for url in ('', 'sqlite:///tmp/db','postgresql://','postgresql://u@host/db?sslmode=prefer','postgresql://u@host/db?secret=foo','postgresql://u@host/db?sslmode=require&sslmode=disable'):
            with self.assertRaises(ImproperlyConfigured): postgres(url)

class KeyRotationTests(TestCase):
    def test_tokens_cleared_accounts_and_posts_preserved(self):
        m=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        post=Post.objects.create(member=m,author_name=m.name,title='가상',body='가상')
        Session.objects.create(session_key='fictional',session_data='fictional',expire_date='2030-01-01T00:00:00Z')
        call_command('invalidate_auth_tokens',stdout=io.StringIO())
        self.assertFalse(Session.objects.exists());self.assertTrue(Member.objects.filter(pk=m.pk).exists());self.assertTrue(Post.objects.filter(pk=post.pk).exists())

@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL test database')
@override_settings(DATABASE_PERSISTENCE_CONFIRMED=True)
class MemberMigrationTests(TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fictional.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute('create table portal_member (id text,name text,phone text,label text,active integer,synthetic integer,session_version integer,created_at text,updated_at text)')
                db.execute('create table auth_user (id integer)')
                db.execute('create table portal_case (id integer)')
                db.execute("insert into portal_member values ('11111111111141118111111111111111','가상교인','01000000000','',1,1,3,'2001-01-01 00:00:00','2001-01-01 00:00:00')")
            self.raw=path.read_bytes()
        self.digest=hashlib.sha256(self.raw).hexdigest()
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE IF NOT EXISTS shinsung_sqlite_backups (sha256 varchar(64) PRIMARY KEY,data bytea NOT NULL)')
            cursor.execute('INSERT INTO shinsung_sqlite_backups VALUES (%s,%s) ON CONFLICT DO NOTHING',[self.digest,self.raw])
    def test_preview_repeat_id_preservation_and_existing_target_refusal(self):
        call_command('migrate_sqlite_members',backup_sha=self.digest,stdout=io.StringIO())
        self.assertEqual(Member.objects.count(),0)
        call_command('migrate_sqlite_members',backup_sha=self.digest,apply=True,stdout=io.StringIO())
        member=Member.objects.get();self.assertEqual(member.pk.hex,'11111111111141118111111111111111');self.assertEqual(member.session_version,4)
        from datetime import datetime, timezone
        self.assertEqual(member.created_at, datetime(2001,1,1,tzinfo=timezone.utc))
        call_command('migrate_sqlite_members',backup_sha=self.digest,apply=True,stdout=io.StringIO())
        self.assertEqual(Member.objects.count(),1)
    def test_bad_hash_and_nonempty_target(self):
        with self.assertRaises(CommandError):call_command('migrate_sqlite_members',backup_sha='0'*64,apply=True)
        Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        with self.assertRaises(CommandError):call_command('migrate_sqlite_members',backup_sha=self.digest,apply=True)
    def test_local_backup_commands_refuse_postgres(self):
        for cmd in ('backup_private','restore_private'):
            with self.assertRaises(CommandError):call_command(cmd,'/tmp/fictitious-backup-output')
