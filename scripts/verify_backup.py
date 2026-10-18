import os,sys,tempfile,subprocess,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent;python=sys.executable
with tempfile.TemporaryDirectory(prefix='shinsung-recovery-') as d:
    base=Path(d);original=base/'source';backup=base/'backup';restored=base/'restored'
    environ=dict(os.environ,APP_MODE='development',DATA_DIR=str(original))
    def command(*args,env=environ):
        return subprocess.run([python,'manage.py',*args],cwd=root,env=env,check=True,capture_output=True,text=True).stdout
    command('migrate','--noinput')
    setup="from portal.models import *; from django.contrib.sessions.models import Session; from django.utils import timezone; import datetime; m=Member.objects.create(name='복구검증가상',phone='01000000000',synthetic=True); Post.objects.create(member=m,author_name=m.name,title='복구가상글',body='복구검증본문'); root=CaseComment.objects.create(reading_key='E01',member=m,author_name=m.name,body='가상원댓글'); reply=CaseComment.objects.create(reading_key='E01',member=m,author_name=m.name,body='가상답글',parent=root); Revision.objects.create(target='comment:'+str(root.pk),actor=str(m.pk),body={'body':'가상이전내용'}); Request.objects.create(member=m,kind='correction',reading_key='E01',comment=root,body='가상요청'); Session.objects.create(session_key='synthetic-session',session_data='synthetic',expire_date=timezone.now()+datetime.timedelta(hours=1)); Challenge.objects.create(member=m,digest='synthetic-hash',expires_at=timezone.now()+datetime.timedelta(minutes=5))"
    command('shell','-c',setup)
    (original/'private').mkdir();(original/'private/test.pdf').write_bytes(b'%PDF-1.4 synthetic backup check')
    command('backup_private',str(backup))
    recovery=dict(environ,DATA_DIR=str(restored));command('restore_private',str(backup),env=recovery)
    check="from portal.models import *; from django.contrib.sessions.models import Session; from django.conf import settings; assert Member.objects.count()==1; assert Post.objects.get().body=='복구검증본문'; root=CaseComment.objects.get(parent=None); reply=CaseComment.objects.exclude(parent=None).get(); assert reply.parent_id==root.pk and reply.member_id==Member.objects.get().pk; assert root.reading_key=='E01' and root.body=='가상원댓글'; assert Revision.objects.get(target='comment:'+str(root.pk)).body['body']=='가상이전내용'; assert Request.objects.get().comment_id==root.pk; assert (settings.MEDIA_ROOT/'test.pdf').read_bytes()==b'%PDF-1.4 synthetic backup check'; assert Session.objects.count()==0; assert Challenge.objects.count()==0"
    command('shell','-c',check,env=recovery);command('migrate','--noinput',env=recovery);command('shell','-c',check,env=recovery)
    print('PASS: database and private-file backup/restore, checksums, preserved comment/reply/request/revision and post/member IDs, session/OTP invalidation and repeat migration')
    try: command('restore_private',str(backup),env=recovery)
    except subprocess.CalledProcessError: print('PASS: restore refuses nonempty DATA_DIR')
    else: raise AssertionError('unsafe overwrite permitted')
    damaged=base/'damaged';import shutil;shutil.copytree(backup,damaged);(damaged/'private/test.pdf').write_bytes(b'tampered')
    try: command('restore_private',str(damaged),env=dict(environ,DATA_DIR=str(base/'empty')))
    except subprocess.CalledProcessError: print('PASS: checksum mismatch prevents restore')
    else: raise AssertionError('tampering permitted')
