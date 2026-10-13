"""Scoped migration for the confirmed member-only SQLite installation."""
import hashlib
import sqlite3
import tempfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from portal.models import Member, Audit

class Command(BaseCommand):
    help = '외부 PostgreSQL 백업에서 교인 ID를 보존해 이관. 다른 업무 데이터가 있으면 중지.'
    def add_arguments(self, parser):
        parser.add_argument('--backup-sha', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--expected-members', type=int, default=1)
    def handle(self, *args, **options):
        try:
            return self.transfer(options)
        except CommandError:
            raise
        except Exception:
            raise CommandError('이관 실패. 백업·접속·원본 및 대상의 수량을 확인하세요. 개인정보는 출력하지 않습니다.') from None
    def transfer(self, options):
        digest = options['backup_sha']
        if connection.vendor != 'postgresql' or not settings.DATABASE_PERSISTENCE_CONFIRMED or len(digest) != 64:
            raise CommandError('보존 조건을 확인한 PostgreSQL 대상과 검증된 백업 SHA-256이 필요합니다.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT data FROM shinsung_sqlite_backups WHERE sha256=%s', [digest])
            result = cursor.fetchone()
        if not result or hashlib.sha256(bytes(result[0])).hexdigest() != digest:
            raise CommandError('검증된 외부 백업이 없습니다.')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'snapshot.sqlite3'; path.write_bytes(bytes(result[0])); path.chmod(0o600)
            with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as source:
                source.row_factory = sqlite3.Row
                if source.execute('pragma integrity_check').fetchone()[0] != 'ok':
                    raise CommandError('원본 무결성 오류')
                # Current installation contains members only. Do not silently drop accounts or business data.
                tables = [r[0] for r in source.execute("select name from sqlite_master where type='table'")]
                skipped = {'portal_member','portal_challenge','portal_ratebucket','portal_audit'}
                for table in tables:
                    if (table.startswith('portal_') and table not in skipped) or table == 'auth_user':
                        if source.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]:
                            raise CommandError('현재 교인 전용 이관 범위를 넘는 관리자·업무 데이터가 있습니다. 이관을 중지합니다.')
                rows = list(source.execute('select * from portal_member'))
        if len(rows) != options['expected_members'] or options['expected_members'] < 1:
            raise CommandError('백업의 교인 수가 예상 수량과 다릅니다. 이관을 중지합니다.')
        if not options['apply']:
            self.stdout.write(f'교인 {len(rows)}건 이관 예정. 원본 변경 없음. 세션·인증번호는 이관하지 않습니다.')
            return
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('LOCK TABLE portal_member IN EXCLUSIVE MODE')
            if Audit.objects.filter(action='sqlite_member_migration', target=digest).exists():
                self.stdout.write('이미 이관한 백업입니다. 기존 기록을 유지합니다.')
                return
            from django.contrib.auth.models import User
            from django.apps import apps
            ignored = {'audit','challenge','ratebucket'}
            business_exists = any(model.objects.exists() for model in apps.get_app_config('portal').get_models() if model._meta.model_name not in ignored)
            if business_exists or User.objects.exists():
                raise CommandError('대상 업무 DB가 비어 있지 않습니다. 기존 기록을 덮어쓰지 않습니다.')
            for row in rows:
                values = {f.attname: f.to_python(row[f.column]) for f in Member._meta.fields if f.column in row.keys()}
                # Django SQLite stores timezone-aware timestamps as naive UTC.
                from datetime import timezone as utc
                from django.utils.timezone import is_naive
                for key in ('created_at', 'updated_at'):
                    if is_naive(values[key]): values[key] = values[key].replace(tzinfo=utc.utc)
                values['session_version'] += 1
                obj = Member(**values)
                obj.save_base(raw=True, force_insert=True)
            Audit.objects.create(actor='migration', action='sqlite_member_migration', target=digest, reason='외부 백업 SHA 확인; 내부 ID·교인 기록 보존; 기존 세션 무효화')
        self.stdout.write(f'교인 {len(rows)}건 이관 완료. 외부 백업 보존. 운영 화면 검증은 별도입니다.')
