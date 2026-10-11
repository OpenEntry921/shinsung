"""Only synthetic people, telephone numbers and documents. No real church data."""
import base64
import hashlib
import hmac
import io
import json
import struct
import time
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from openpyxl import Workbook
from werkzeug.security import generate_password_hash
from app import create_app
from app.db import db, now
from app.security import encrypt, digest

ORIGIN='https://test.example'

@pytest.fixture
def app(tmp_path):
    return create_app({'APP_ENV':'test','TESTING':True,'APP_SECRET':'virtual-only-secret-'+'x'*40,'DATA_KEY':Fernet.generate_key().decode(),'DATA_DIR':str(tmp_path/'data'),'PUBLIC_ORIGIN':ORIGIN,'POLICY_APPROVED':True})

@pytest.fixture
def client(app):
    return app.test_client()


def member(app,id='m1',name='가상교인A',phone='01000000001',active=1):
    with app.app_context():
        db().execute('INSERT INTO members VALUES(?,?,?,?,?,1,?,?)',(id,encrypt(name),encrypt(phone),digest(phone),active,now(),now()))
    return id


def admin(app,client,id='admin1',roles='roster,content,publish,moderate'):
    with app.app_context():
        db().execute('INSERT OR IGNORE INTO admins VALUES(?,?,?,?,?,1)',(id,id,generate_password_hash('virtual-admin-password'),encrypt('JBSWY3DPEHPK3PXP'),roles))
        db().execute('INSERT INTO sessions VALUES(?,NULL,?,NULL,?,?)',(digest('token-'+id),id,'csrf-'+id,now()+1800))
    client.set_cookie('church_session','token-'+id)
    return {'Origin':ORIGIN,'X-CSRF-Token':'csrf-'+id}


def login(app,client,name='가상교인A',phone='01000000001'):
    r=client.post('/api/auth/request',json={'name':name,'phone':phone},headers={'Origin':ORIGIN})
    token=r.json['challenge_id']
    code=app.extensions['test_sms'][phone]
    response=client.post('/api/auth/verify',json={'challenge_id':token,'code':code},headers={'Origin':ORIGIN})
    assert response.status_code==200
    return {'Origin':ORIGIN,'X-CSRF-Token':response.json['csrf']},token,code


def workbook(rows):
    book=Workbook();sheet=book.active;sheet.title='교인명부'
    sheet.append(['테스트용 가상 명부']);sheet.append(['','이름','전화번호'])
    for name,phone in rows:
        sheet.append(['',name,phone])
    out=io.BytesIO();book.save(out);out.seek(0);return out


def upload(client,headers,rows):
    return client.post('/api/admin/roster/preview',data={'file':(workbook(rows),'virtual.xlsx')},headers=headers)


def test_anonymous_and_non_roster_blocked(app,client):
    for path in ('/cases','/board','/api/cases','/api/posts','/api/documents/missing'):
        assert client.get(path).status_code==401
    assert client.get('/api/admin/members').status_code==403
    r=client.post('/api/auth/request',json={'name':'없음','phone':'01000000009'},headers={'Origin':ORIGIN})
    assert r.status_code==200
    assert not app.extensions['test_sms']
    assert client.post('/api/auth/verify',json={'challenge_id':r.json['challenge_id'],'code':'123456'},headers={'Origin':ORIGIN}).status_code==401
    assert client.get('/api/members').status_code==404


def test_otp_reuse_attempt_limit_expiration(app,client):
    member(app)
    headers,token,code=login(app,client)
    assert client.post('/api/auth/verify',json={'challenge_id':token,'code':code},headers=headers).status_code==401
    with app.app_context():
        db().execute('DELETE FROM rates')
    other=app.test_client()
    r=other.post('/api/auth/request',json={'name':'가상교인A','phone':'01000000001'},headers={'Origin':ORIGIN})
    token=r.json['challenge_id']
    for _ in range(5):
        assert other.post('/api/auth/verify',json={'challenge_id':token,'code':'wrong'},headers={'Origin':ORIGIN}).status_code==401
    assert other.post('/api/auth/verify',json={'challenge_id':token,'code':app.extensions['test_sms']['01000000001']},headers={'Origin':ORIGIN}).status_code==401
    with app.app_context():
        db().execute('DELETE FROM rates');db().execute('UPDATE challenges SET attempts=0,expires=? WHERE id=?',(now()-1,token))
    assert other.post('/api/auth/verify',json={'challenge_id':token,'code':code},headers={'Origin':ORIGIN}).status_code==401


def test_resend_limit_and_generic_response(app,client):
    member(app)
    r1=client.post('/api/auth/request',json={'name':'가상교인A','phone':'01000000001'},headers={'Origin':ORIGIN})
    old=app.extensions['test_sms']['01000000001']
    r2=client.post('/api/auth/request',json={'name':'가상교인A','phone':'01000000001'},headers={'Origin':ORIGIN})
    r3=client.post('/api/auth/request',json={'name':'없는가상','phone':'01000000009'},headers={'Origin':ORIGIN})
    assert r1.json['message']==r2.json['message']==r3.json['message']
    assert app.extensions['test_sms']['01000000001']==old
    assert client.post('/api/auth/verify',json={'challenge_id':r2.json['challenge_id'],'code':old},headers={'Origin':ORIGIN}).status_code==401


def test_missing_sms_configuration_fails_closed(app,client):
    member(app);app.config['APP_ENV']='development'
    r=client.post('/api/auth/request',json={'name':'가상교인A','phone':'01000000001'},headers={'Origin':ORIGIN})
    from app.sms import process_one
    with app.app_context():
        process_one()
        row=db().execute('SELECT * FROM challenges WHERE id=?',(r.json['challenge_id'],)).fetchone()
        assert row['used']==1
        assert db().execute('SELECT COUNT(*) FROM outbox').fetchone()[0]==0
    assert not app.extensions['test_sms']


def test_shared_phone_blocked_and_manual_grant(app,client):
    member(app);member(app,'m2','가상교인B','01000000001')
    response=client.post('/api/auth/request',json={'name':'가상교인A','phone':'01000000001'},headers={'Origin':ORIGIN})
    assert response.status_code==200 and not app.extensions['test_sms']
    admin_client=app.test_client();headers=admin(app,admin_client)
    assert admin_client.post('/api/admin/members/m1/grant',json={'reason':'테스트'},headers=headers).status_code==400
    grant=admin_client.post('/api/admin/members/m1/grant',json={'reason':'가상 본인 확인','identity_confirmed':True},headers=headers).json
    assert client.post('/api/auth/verify',json={'challenge_id':grant['challenge_id'],'code':grant['code']},headers={'Origin':ORIGIN}).status_code==200
    assert client.get('/api/me').json['name']=='가상교인A'
    assert client.post('/api/auth/verify',json={'challenge_id':grant['challenge_id'],'code':grant['code']},headers={'Origin':ORIGIN,'X-CSRF-Token':client.get('/api/me').json['csrf']}).status_code==401


def test_same_name_distinct_phone_and_no_roster_api(app,client):
    member(app);member(app,'m2','가상교인A','01000000002')
    login(app,client)
    assert client.get('/api/me').json['name'].startswith('가상교인A · ')
    assert client.get('/api/admin/members').status_code==403


def test_roster_preview_flags_and_normalization(app,client):
    headers=admin(app,client);member(app)
    r=upload(client,headers,[('가상교인A','010-0000-0001'),('가상교인B',1000000002),('가상교인C','01000000003'),('가상교인C','01000000003'),('가상교인C','01000000004'),('공용가상','01000000004'),('누락가상',None),(None,None)])
    assert r.status_code==200
    rows=r.json['rows'];assert len(rows)==7
    assert rows[0]['existing_id']=='m1'
    assert rows[1]['candidate']=='01000000002' and rows[1]['issue']
    assert rows[2]['duplicate'] and rows[2]['same_name']
    assert rows[4]['shared_phone']
    assert rows[6]['issue']
    assert r.json['missing']==[]


def test_roster_preserves_ids_posts_and_invalidates_old_session(app,client):
    member(app);headers,_,_=login(app,client)
    post=client.post('/api/posts',json={'title':'가상글','body':'가상 내용','real_name_notice':True},headers=headers).json['id']
    ac=app.test_client();ah=admin(app,ac)
    preview=upload(ac,ah,[('가상교인A','01000000002')]).json
    r=ac.post('/api/admin/roster/apply',json={'import_id':preview['import_id'],'decisions':{'3':{'action':'link','member_id':'m1','confirmed':True}}},headers=ah)
    assert r.status_code==200
    assert client.get('/api/posts').status_code==401
    with app.app_context():
        assert db().execute('SELECT member_id FROM posts WHERE id=?',(post,)).fetchone()[0]=='m1'
        assert db().execute('SELECT version FROM members WHERE id=\'m1\'').fetchone()[0]==2
    reimport=upload(ac,ah,[('가상교인A','01000000002')]).json
    assert reimport['rows'][0]['existing_id']=='m1'
    assert ac.post('/api/admin/roster/apply',json={'import_id':reimport['import_id'],'decisions':{}},headers=ah).status_code==200
    missing=upload(ac,ah,[]).json
    assert missing['missing']==['m1']
    assert ac.post('/api/admin/roster/apply',json={'import_id':missing['import_id'],'decisions':{}},headers=ah).status_code==200
    assert ac.get('/api/admin/members').json['items'][0]['active'] is True


def test_roster_confirmations_and_stale_preview(app,client):
    headers=admin(app,client)
    p=upload(client,headers,[('신규가상','01000000001')]).json
    assert client.post('/api/admin/roster/apply',json={'import_id':p['import_id'],'decisions':{'3':{'action':'create'}}},headers=headers).status_code==400
    member(app)
    assert client.post('/api/admin/roster/apply',json={'import_id':p['import_id'],'decisions':{}},headers=headers).status_code==409


def test_csrf_ownership_and_forged_author(app,client):
    member(app);member(app,'m2','가상교인B','01000000002')
    headers,_,_=login(app,client)
    payload={'title':'가상제목','body':'<script>가상</script>','real_name_notice':True,'member_id':'m2','author':'위조'}
    assert client.post('/api/posts',json=payload).status_code==403
    assert client.post('/api/posts',json=payload,headers={'Origin':ORIGIN}).status_code==403
    response=client.post('/api/posts',json=payload,headers=headers);assert response.status_code==201
    post=response.json['id'];detail=client.get('/api/posts/'+post).json
    assert detail['author']=='가상교인A' and 'member_id' not in detail
    assert client.post('/api/admin/cases',json={},headers=headers).status_code==403
    other=app.test_client()
    with app.app_context():db().execute('DELETE FROM rates')
    oh,_,_=login(app,other,'가상교인B','01000000002')
    assert other.put('/api/posts/'+post,json={'title':'위조','body':'위조','expected_updated':detail['updated']},headers=oh).status_code==403
    assert other.delete('/api/posts/'+post,json={'expected_updated':detail['updated']},headers=oh).status_code==403
    r=client.put('/api/posts/'+post,json={'title':'수정','body':'수정','expected_updated':detail['updated']},headers=headers);assert r.status_code==200
    updated=client.get('/api/posts/'+post).json;assert updated['updated']>updated['created']
    assert client.put('/api/posts/'+post,json={'title':'충돌','body':'충돌','expected_updated':detail['updated']},headers=headers).status_code==409


def test_deactivation_logout_and_session_expiry(app,client):
    member(app);headers,_,_=login(app,client)
    ac=app.test_client();ah=admin(app,ac)
    assert ac.post('/api/admin/members/m1',json={'active':False,'reason':'가상 명부 상태 확인'},headers=ah).status_code==200
    assert client.get('/api/cases').status_code==401
    ac.post('/api/admin/members/m1',json={'active':True,'reason':'가상 복구'},headers=ah)
    with app.app_context():db().execute('DELETE FROM rates')
    headers,_,_=login(app,client)
    with app.app_context():db().execute('UPDATE sessions SET expires=? WHERE member_id=\'m1\'',(now()-1,))
    assert client.get('/api/posts').status_code==401
    with app.app_context():db().execute('DELETE FROM rates')
    headers,_,_=login(app,client)
    assert client.post('/api/auth/logout',json={},headers=headers).status_code==200
    assert client.get('/api/posts').status_code==401


def case_publish(app):
    a=app.test_client();ah=admin(app,a,'writer','content')
    response=a.post('/api/admin/cases',json={'title':'가상 검증 사건 (실제 사건 아님)','event_date':'2026-01-01','facts':'가상 테스트 내용','claims_a':'가상 주장 A','claims_b':'가상 주장 B'},headers=ah)
    assert response.status_code==200
    case_id=response.json['id']
    row=a.get('/api/admin/content').json['cases'][0]
    assert a.post('/api/admin/cases/'+case_id+'/state',json={'state':'review','reason':'검토 요청','expected_updated':row['updated']},headers=ah).status_code==200
    b=app.test_client();bh=admin(app,b,'reviewer','publish')
    row=b.get('/api/admin/content').json['cases'][0]
    assert b.post('/api/admin/cases/'+case_id+'/state',json={'state':'published','reason':'가상 자료 검토','expected_updated':row['updated']},headers=bh).status_code==200
    return case_id,a,ah,b,bh


def test_case_workflow_and_private_files(app,client):
    member(app);login(app,client)
    case_id,a,ah,b,bh=case_publish(app)
    assert client.get('/api/cases').json['items'][0]['id']==case_id
    assert client.get('/api/cases/'+case_id).json['data']['claims_a']=='가상 주장 A'
    uploads=[]
    for kind in ('original','reading'):
        r=a.post('/api/admin/documents',data={'case_id':case_id,'kind':kind,'file':(io.BytesIO(b'%PDF-1.4\n virtual only'),'virtual.pdf'),'title':'가상 자료','source':'가상 출처','acquired_date':'2026-01-01'},headers=ah)
        assert r.status_code==201;uploads.append(r.json['id'])
        assert client.get('/api/documents/'+r.json['id']).status_code==403
    original,reading=uploads
    assert b.post('/api/admin/documents/'+original+'/approve',json={'irreversible_redaction_checked':True,'reason':'검토'},headers=bh).status_code==400
    assert b.post('/api/admin/documents/'+reading+'/approve',json={'irreversible_redaction_checked':True,'reason':'가상 가림 확인'},headers=bh).status_code==200
    response=client.get('/api/documents/'+reading)
    assert response.status_code==200 and response.data.startswith(b'%PDF')
    assert 'attachment' in response.headers['Content-Disposition']
    assert client.get('/static/'+reading+'.enc').status_code==404
    assert b.post('/api/admin/documents/'+reading+'/withdraw',json={'reason':'가상 철회'},headers=bh).status_code==200
    assert client.get('/api/documents/'+reading).status_code==403
    content=a.get('/api/admin/content').json['cases'][0]
    assert a.post('/api/admin/cases',json={'id':case_id,'title':'가상 수정','event_date':'2026-01-01','expected_updated':content['updated']},headers=ah).status_code==200
    assert client.get('/api/cases/'+case_id).status_code==404
    assert a.get('/api/admin/revisions/case/'+case_id).json['items']


def test_no_self_publication_or_unverified_clause(app,client):
    headers=admin(app,client)
    case_id=client.post('/api/admin/cases',json={'title':'가상 사건','event_date':'2026-01-01'},headers=headers).json['id']
    row=client.get('/api/admin/content').json['cases'][0]
    client.post('/api/admin/cases/'+case_id+'/state',json={'state':'review','reason':'가상 검토','expected_updated':row['updated']},headers=headers)
    row=client.get('/api/admin/content').json['cases'][0]
    assert client.post('/api/admin/cases/'+case_id+'/state',json={'state':'published','reason':'셀프 승인','expected_updated':row['updated']},headers=headers).status_code==400
    clause_id=client.post('/api/admin/clauses',json={'location':'가상 조문 (테스트용)','content':'실제 조문 아님','source_url':'https://other.example','instrument':'헌법','effective_date':'2026-01-01','checked_date':'2026-01-01','applicable_period':'가상'},headers=headers).json['id']
    second=app.test_client();sh=admin(app,second,'reviewer','publish')
    assert second.post('/api/admin/clauses/'+clause_id+'/verify',json={'reason':'검토','official_source_checked':True,'expected_updated':second.get('/api/admin/content').json['clauses'][0]['updated']},headers=sh).status_code==400


def test_requests_moderation_and_member_appeal(app,client):
    member(app);headers,_,_=login(app,client)
    post=client.post('/api/posts',json={'title':'가상글','body':'가상내용','real_name_notice':True},headers=headers).json['id']
    request_id=client.post('/api/requests',json={'kind':'correction','target':post,'body':'가상 정정 요청'},headers=headers).json['id']
    admin_client=app.test_client();ah=admin(app,admin_client)
    assert admin_client.post('/api/admin/posts/'+post+'/visibility',json={'hidden':True,'reason':'가상 개인정보 노출 검토'},headers=ah).status_code==200
    assert client.get('/api/posts').json['items']==[]
    assert client.get('/api/my-posts').json['items'][0]['reason']=='가상 개인정보 노출 검토'
    assert client.get('/api/posts/'+post).status_code==200
    assert admin_client.put('/api/posts/'+post,json={'title':'관리자 조작','body':'조작'},headers=ah).status_code==401
    assert admin_client.post('/api/admin/requests/'+request_id,json={'status':'resolved','response':'가상 정정 반영'},headers=ah).status_code==200
    assert client.get('/api/requests').json['items'][0]['response']=='가상 정정 반영'
    assert client.get('/api/admin/requests').status_code==403


def test_backup_restore_and_redeployment(app,client,tmp_path):
    member(app);login(app,client)
    backup_path=tmp_path/'backup.enc'
    runner=app.test_cli_runner();r=runner.invoke(args=['backup',str(backup_path)])
    assert r.exit_code==0,r.output
    with app.app_context():assert db().execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    restarted=create_app({k:app.config[k] for k in ('TESTING','APP_ENV','APP_SECRET','DATA_KEY','DATA_DIR','PUBLIC_ORIGIN','POLICY_APPROVED')})
    with restarted.app_context():assert db().execute('SELECT COUNT(*) FROM members').fetchone()[0]==1
    restored=create_app({k:app.config[k] for k in ('TESTING','APP_ENV','APP_SECRET','DATA_KEY','PUBLIC_ORIGIN','POLICY_APPROVED')}|{'DATA_DIR':str(tmp_path/'restored')})
    r=restored.test_cli_runner().invoke(args=['restore',str(backup_path)])
    assert r.exit_code==0,r.output
    with restored.app_context():
        assert db().execute('SELECT COUNT(*) FROM members').fetchone()[0]==1
        assert db().execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==0


def test_private_encryption_and_headers(app,client):
    member(app)
    with app.app_context():
        row=db().execute('SELECT * FROM members').fetchone()
        assert '가상교인A' not in row['name'] and '01000000001' not in row['phone']
    r=client.get('/')
    assert r.status_code==200
    assert r.headers['Cache-Control']=='no-store'
    assert "script-src 'self'" in r.headers['Content-Security-Policy']
    assert 'noindex' in r.headers['X-Robots-Tag']
    assert '회원가입' in r.text and '가상교인A' not in r.text
    app.config['POLICY_APPROVED']=False
    assert client.post('/api/auth/request',json={'name':'가상교인A','phone':'01000000001'},headers={'Origin':ORIGIN}).status_code==503


def test_admin_totp_and_replay(app,client):
    with app.app_context():db().execute('INSERT INTO admins VALUES(?,?,?,?,?,1)',('admin','admin',generate_password_hash('virtual-admin-password'),encrypt('JBSWY3DPEHPK3PXP'),'roster'))
    step=int(time.time()//30);raw=hmac.new(base64.b32decode('JBSWY3DPEHPK3PXP'),struct.pack('>Q',step),hashlib.sha1).digest();offset=raw[-1]&15
    code=f'{(struct.unpack(">I",raw[offset:offset+4])[0]&0x7fffffff)%1000000:06d}'
    data={'username':'admin','password':'virtual-admin-password','code':code}
    r=client.post('/api/admin/login',json=data,headers={'Origin':ORIGIN});assert r.status_code==200
    other=app.test_client();assert other.post('/api/admin/login',json=data,headers={'Origin':ORIGIN}).status_code==401
    assert client.get('/api/admin/content').status_code==403
    assert client.get('/api/admin/members').status_code==200


def test_production_cookie_flags(app,client):
    member(app);headers,_,_=login(app,client)
    with app.app_context():db().execute('DELETE FROM rates')
    app.config['APP_ENV']='production'
    admin_client=app.test_client();ah=admin(app,admin_client)
    grant=admin_client.post('/api/admin/members/m1/grant',json={'reason':'가상 확인','identity_confirmed':True},headers=ah).json
    second=app.test_client();r=second.post('/api/auth/verify',json={'challenge_id':grant['challenge_id'],'code':grant['code']},headers={'Origin':ORIGIN})
    assert 'Secure' in r.headers['Set-Cookie'] and 'HttpOnly' in r.headers['Set-Cookie'] and 'SameSite=Strict' in r.headers['Set-Cookie']


def test_manual_grant_expiry_and_pending_sms_shared_revocation(app,client):
    member(app)
    pending=client.post('/api/auth/request',json={'name':'가상교인A','phone':'01000000001'},headers={'Origin':ORIGIN}).json['challenge_id']
    code=app.extensions['test_sms']['01000000001']
    member(app,'m2','가상교인B','01000000001')
    assert client.post('/api/auth/verify',json={'challenge_id':pending,'code':code},headers={'Origin':ORIGIN}).status_code==401
    ac=app.test_client();ah=admin(app,ac)
    grant=ac.post('/api/admin/members/m1/grant',json={'reason':'가상 확인','identity_confirmed':True},headers=ah).json
    with app.app_context():db().execute('UPDATE challenges SET expires=? WHERE id=?',(now()-1,grant['challenge_id']))
    assert client.post('/api/auth/verify',json={'challenge_id':grant['challenge_id'],'code':grant['code']},headers={'Origin':ORIGIN}).status_code==401


def test_valid_new_roster_and_duplicates_abort_atomically(app,client):
    ah=admin(app,client)
    preview=upload(client,ah,[('신규가상A','01000000001'),('신규가상B','01000000002')]).json
    decisions={str(x['row']):{'action':'create','confirmed':True} for x in preview['rows']}
    assert client.post('/api/admin/roster/apply',json={'import_id':preview['import_id'],'decisions':decisions},headers=ah).status_code==200
    assert len(client.get('/api/admin/members').json['items'])==2
    preview=upload(client,ah,[('중복가상','01000000003'),('중복가상','01000000003')]).json
    decisions={str(x['row']):{'action':'create','confirmed':True} for x in preview['rows']}
    assert client.post('/api/admin/roster/apply',json={'import_id':preview['import_id'],'decisions':decisions},headers=ah).status_code==400
    assert len(client.get('/api/admin/members').json['items'])==2


def test_vendor_accepted_and_rejected_responses(app,monkeypatch):
    from app.security import send_sms
    app.config.update(APP_ENV='development',SOLAPI_KEY='virtual-key',SOLAPI_SECRET='virtual-secret',SMS_SENDER='01000000009')
    class Response:
        status_code=200
        payload={'failedMessageList':[],'groupInfo':{'count':{'registeredSuccess':1}}}
        def json(self):return self.payload
    calls=[]
    def post(url,**kwargs):calls.append((url,kwargs));return Response()
    monkeypatch.setattr('app.security.requests.post',post)
    with app.app_context():
        assert send_sms('01000000001','123456') is True
        assert calls[0][0].endswith('/messages/v4/send-many/detail')
        assert calls[0][1]['json']['messages'][0]['to']=='01000000001'
        assert 'HMAC-SHA256' in calls[0][1]['headers']['Authorization']
        Response.payload={'failedMessageList':[{'statusCode':'virtual failure'}],'groupInfo':{'count':{'registeredSuccess':0}}}
        assert send_sms('01000000001','123456') is False
        Response.payload={}
        assert send_sms('01000000001','123456') is False


def test_retention_purges_private_operational_data(app):
    member(app)
    with app.app_context():
        from app.db import purge_expired
        old=now()-200*86400
        db().execute('INSERT INTO posts(id,member_id,title,body,created,updated,deleted) VALUES(?,?,?,?,?,?,1)',('old','m1','가상 삭제','가상',old,old))
        db().execute('INSERT INTO requests(id,member_id,kind,target,body,status,created,updated) VALUES(?,?,?,?,?,?,?,?)',('old-request','m1','correction','',encrypt('가상'),'resolved',old,old))
        db().execute('INSERT INTO audit(actor,action,target,reason,created) VALUES(?,?,?,?,?)',('test','test','','',old))
        purge_expired()
        assert db().execute('SELECT COUNT(*) FROM posts').fetchone()[0]==0
        assert db().execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0
        assert db().execute('SELECT COUNT(*) FROM audit').fetchone()[0]==0


def test_backup_encrypted_private_files(app,tmp_path):
    with app.app_context():
        file=Path(app.config['DATA_DIR'])/'private'/'virtual.enc'
        file.write_bytes(app.extensions['cipher'].encrypt(b'virtual private document'))
    backup_path=tmp_path/'files-backup.enc'
    assert app.test_cli_runner().invoke(args=['backup',str(backup_path)]).exit_code==0
    other=create_app({k:app.config[k] for k in ('TESTING','APP_ENV','APP_SECRET','DATA_KEY','PUBLIC_ORIGIN','POLICY_APPROVED')}|{'DATA_DIR':str(tmp_path/'files-restored')})
    result=other.test_cli_runner().invoke(args=['restore',str(backup_path)])
    assert result.exit_code==0,result.output
    restored=(Path(other.config['DATA_DIR'])/'private'/'virtual.enc').read_bytes()
    assert other.extensions['cipher'].decrypt(restored)==b'virtual private document'


def test_verified_clause_and_member_pending_display(app,client):
    case_id,a,ah,b,bh=case_publish(app)
    clause=a.post('/api/admin/clauses',json={'location':'가상 조문','content':'실제 조문 아님','source_url':'https://www.pck.or.kr/','instrument':'헌법','effective_date':'2026-01-01','checked_date':'2026-01-01','applicable_period':'가상 기간'},headers=ah).json['id']
    row=a.get('/api/admin/content').json['cases'][0]
    a.post('/api/admin/cases',json={'id':case_id,'title':row['title'],'event_date':row['event_date'],'clause_ids':[clause],'expected_updated':row['updated']},headers=ah)
    row=a.get('/api/admin/content').json['cases'][0]
    a.post('/api/admin/cases/'+case_id+'/state',json={'state':'review','reason':'가상 요청','expected_updated':row['updated']},headers=ah)
    row=b.get('/api/admin/content').json['cases'][0]
    b.post('/api/admin/cases/'+case_id+'/state',json={'state':'published','reason':'가상 재검토','expected_updated':row['updated']},headers=bh)
    member(app);login(app,client)
    detail=client.get('/api/cases/'+case_id).json
    assert detail['clauses'][0]['verified'] is False
    assert '실제 조문 아님' not in detail['clauses'][0]['data']['content']
    row=b.get('/api/admin/content').json['clauses'][0]
    r=b.post('/api/admin/clauses/'+clause+'/verify',json={'official_source_checked':True,'reason':'가상 API 경로 검증 (실제 조문 검증 아님)','expected_updated':row['updated']},headers=bh)
    assert r.status_code==200
    assert client.get('/api/cases/'+case_id).json['clauses'][0]['verified'] is True
