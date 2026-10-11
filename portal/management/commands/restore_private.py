import sqlite3,shutil,json,hashlib
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.conf import settings
class Command(BaseCommand):
    help='Restore verified backup only into an empty DATA_DIR, with server stopped.'
    def add_arguments(self,p): p.add_argument('source')
    def handle(self,*args,**options):
        src=Path(options['source']).resolve(); dest=settings.DATA_DIR
        if any(dest.iterdir()): raise CommandError('DATA_DIR는 비어 있어야 합니다. 서버를 먼저 중지하세요.')
        manifest=json.loads((src/'manifest.json').read_text())
        for name,digest in manifest.items():
            file=(src/name).resolve()
            if src not in file.parents or hashlib.sha256(file.read_bytes()).hexdigest()!=digest: raise CommandError('백업 무결성 확인 실패')
        with sqlite3.connect(src/'portal.sqlite3') as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise CommandError('DB 무결성 확인 실패')
        shutil.copy2(src/'portal.sqlite3',dest/'portal.sqlite3')
        if (src/'private').exists(): shutil.copytree(src/'private',dest/'private')
        # Restored sessions and pending one-time codes must never resurrect.
        with sqlite3.connect(dest/'portal.sqlite3') as db:
            db.execute('DELETE FROM django_session'); db.execute('DELETE FROM portal_challenge')
        self.stdout.write('복구 완료. 세션·미사용 인증 수단은 무효화했습니다.')
