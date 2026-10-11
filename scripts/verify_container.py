import subprocess,secrets,tempfile,json,time,os
from pathlib import Path
volume='shinsung-verify-'+secrets.token_hex(6)
containers=[]
def run(*args):
    return subprocess.run(['docker',*args],check=True,capture_output=True,text=True).stdout.strip()
with tempfile.TemporaryDirectory(prefix='shinsung-container-') as directory:
    environment=Path(directory)/'synthetic.env'
    environment.write_text('APP_MODE=production\nDJANGO_SECRET_KEY='+secrets.token_urlsafe(64)+'\nALLOWED_HOSTS=localhost,127.0.0.1\n')
    os.chmod(environment,0o600)
    run('volume','create',volume)
    try:
        for generation in (1,2):
            name=volume+'-'+str(generation);containers.append(name)
            run('run','--detach','--name',name,'--env-file',str(environment),'--mount',f'type=volume,src={volume},dst=/data','shinsung-onboarding:local')
            for attempt in range(60):
                try:
                    run('exec',name,'python','-c',"import requests; s=requests.Session();s.trust_env=False;r=s.get('http://127.0.0.1:8000/health/',headers={'X-Forwarded-Proto':'https'}); assert r.status_code==200")
                    break
                except subprocess.CalledProcessError:time.sleep(.2)
            else:raise AssertionError('container not ready')
            if generation==1:
                setup="from portal.models import *; from django.conf import settings; m=Member.objects.create(name='컨테이너검증가상',phone='01000000000',synthetic=True); Post.objects.create(member=m,author_name=m.name,title='보존가상',body='영구검증본문'); settings.MEDIA_ROOT.mkdir(); (settings.MEDIA_ROOT/'test.pdf').write_bytes(b'%PDF-1.4 synthetic')"
                run('exec',name,'python','manage.py','shell','-c',setup)
            else:
                check="from portal.models import *; from django.conf import settings; assert Member.objects.count()==1; assert Post.objects.get().body=='영구검증본문'; assert (settings.MEDIA_ROOT/'test.pdf').read_bytes()==b'%PDF-1.4 synthetic'"
                run('exec',name,'python','manage.py','shell','-c',check)
                assert run('exec',name,'id','-u')=='10001'
                print('PASS: Docker production startup, non-root UID, two replacement containers retain roster/post/private-file data through the same volume')
            run('stop',name);run('rm',name);containers.remove(name)
        result=run('run','--rm','--entrypoint','python','shinsung-onboarding:local','-c',"from pathlib import Path; assert not Path('/app/.git').exists(); assert not Path('/app/.env').exists(); assert not Path('/app/.venv').exists(); assert not Path('/app/runtime/portal.sqlite3').exists(); print('PASS: image excludes checkout metadata, secrets, virtualenv and development DB')")
        print(result)
    finally:
        for name in containers:subprocess.run(['docker','rm','--force',name],capture_output=True)
        run('volume','rm',volume)
