import sqlite3, shutil, json, hashlib, os
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.conf import settings
class Command(BaseCommand):
    help='Backup while the app is stopped; output must be private, outside repository.'
    def add_arguments(self,parser): parser.add_argument('destination')
    def handle(self,*args,**options):
        from django.db import connection
        if connection.vendor != "sqlite": raise CommandError("이 명령은 SQLite 전용입니다. PostgreSQL 서비스의 백업·복구 절차를 사용하세요.")
        dest=Path(options['destination']).resolve()
        if dest==settings.BASE_DIR or settings.BASE_DIR in dest.parents or dest.exists(): raise CommandError('저장소 밖의 새 비공개 디렉터리를 지정하세요.')
        dest.mkdir(parents=True,mode=0o700)
        with sqlite3.connect(settings.DATABASES['default']['NAME']) as src, sqlite3.connect(dest/'portal.sqlite3') as out: src.backup(out)
        if settings.MEDIA_ROOT.exists(): shutil.copytree(settings.MEDIA_ROOT,dest/'private')
        hashes={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}
        (dest/'manifest.json').write_text(json.dumps(hashes))
        for p in dest.rglob('*'):
            os.chmod(p,0o700 if p.is_dir() else 0o600)
        self.stdout.write('컨테이너 내부 사본 생성. 외부 반출·검증 전에는 백업 완료가 아닙니다.')
