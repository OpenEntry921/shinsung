import io
import json
import secrets
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from flask import Blueprint, abort, current_app, g, request, render_template, send_file, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from .db import db, now, audit, revision
from .security import digest, encrypt, decrypt, normalize_phone, member_required, admin_required, new_session, rate, ip_key, totp_step
from . import roster
from .sms import enqueue

bp=Blueprint('main',__name__)
DUMMY_PASSWORD=generate_password_hash('unused-random-dummy-password')


def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):
        abort(400,'JSON 객체가 필요합니다.')
    return data

def text(data,key,maximum=20000,required=False):
    value=data.get(key,'')
    if not isinstance(value,str) or len(value)>maximum or (required and not value.strip()):
        abort(400,f'{key} 항목을 확인하세요.')
    return value.strip()

def uid():
    return secrets.token_hex(16)

def member_name(member):
    return decrypt(member['name'])

def display_name(member):
    if not hasattr(g,'display_names'):
        from collections import Counter
        records=[(x['id'],decrypt(x['name'])) for x in db().execute('SELECT id,name FROM members')]
        counts=Counter(name for _,name in records)
        g.display_names={member_id:name+(f' · {member_id[:8]}' if counts[name]>1 else '') for member_id,name in records}
    return g.display_names[member['id']]


def json_fields(data, fields):
    return {key:text(data,key) for key in fields}

CASE_FIELDS=('facts','chronology','claims_a','claims_b','unknown','sources','status','decisions','reply_a','reply_b','issues','needed','opinion','opinion_basis','decision_body','case_number','decision_date','decision_scope','finality','document_date')
CLAUSE_FIELDS=('location','content','source_url','amended_date','effective_date','checked_date','applicable_period','current_difference','relation','instrument')


@bp.get('/')
def home():
    if g.session and g.session['member_id']:
        return render_template('member.html')
    if g.session and g.session['admin_id']:
        return render_template('admin.html')
    return render_template('login.html')

@bp.get('/admin')
def admin_page():
    if g.session and g.session['admin_id']:
        return render_template('admin.html')
    return render_template('admin_login.html')

@bp.get('/privacy')
def privacy():
    return render_template('privacy.html')

@bp.get('/robots.txt')
def robots():
    return 'User-agent: *\nDisallow: /\n',200,{'Content-Type':'text/plain'}

@bp.get('/api/me')
def me():
    if not g.session:
        abort(401)
    return {'type':'admin' if g.session['admin_id'] else 'member','name':g.identity['username'] if g.session['admin_id'] else display_name(g.identity),'csrf':g.session['csrf'],'roles':g.identity['roles'].split(',') if g.session['admin_id'] else []}

@bp.post('/api/auth/request')
def auth_request():
    if not current_app.config['POLICY_APPROVED']:
        abort(503,'운영 정책 확정 후 로그인을 개방합니다.')
    data=body()
    name=text(data,'name',100,True)
    phone=normalize_phone(text(data,'phone',40,True))
    if not rate('request-ip:'+ip_key(),20,3600):
        abort(429,'요청이 많습니다. 잠시 후 다시 시도하세요.')
    allowed=rate('request-phone:'+phone,5,3600) and rate('cooldown:'+phone,1,60)
    # Identical response for unknown, shared, limited and failed deliveries.
    token=uid()
    candidates=db().execute('SELECT * FROM members WHERE phone_key=? AND active=1',(digest(phone),)).fetchall()
    matched=[x for x in candidates if member_name(x)==name]
    if allowed and len(candidates)==1 and len(matched)==1:
        member=matched[0]
        code=f'{secrets.randbelow(1000000):06d}'
        db().execute("INSERT INTO challenges VALUES(?,?,?,?,?,0,1,'sms')",(token,member['id'],member['version'],digest(token+':'+code),now()+300))
        enqueue(token,decrypt(member['phone']),code)
    return {'challenge_id':token,'message':'입력 정보가 확인되고 인증이 가능하면 인증번호가 발송됩니다. 받지 못한 경우 운영자에게 문의하세요.'}

@bp.post('/api/auth/verify')
def auth_verify():
    if not current_app.config['POLICY_APPROVED']:
        abort(503)
    data=body()
    token=text(data,'challenge_id',100,True)
    code=text(data,'code',100,True)
    if not rate('verify:'+ip_key(),50,3600):
        abort(429)
    connection=db()
    connection.execute('BEGIN IMMEDIATE')
    try:
        row=connection.execute('SELECT * FROM challenges WHERE id=?',(token,)).fetchone()
        if not row or row['used'] or row['expires']<=now() or row['attempts']>=5:
            abort(401,'인증 정보를 확인하거나 다시 요청하세요.')
        connection.execute('UPDATE challenges SET attempts=attempts+1 WHERE id=?',(token,))
        valid=secrets.compare_digest(row['hash'],digest(token+':'+code))
        member=connection.execute('SELECT * FROM members WHERE id=? AND active=1 AND version=?',(row['member_id'],row['version'])).fetchone()
        if member and row['kind']=='sms' and connection.execute('SELECT COUNT(*) FROM members WHERE phone_key=? AND active=1',(member['phone_key'],)).fetchone()[0]!=1:
            member=None
        if not valid or not member:
            connection.execute('COMMIT')
            abort(401,'인증 정보를 확인하거나 다시 요청하세요.')
        connection.execute('UPDATE challenges SET used=1 WHERE id=?',(token,))
        response=new_session(member=member)
        connection.execute('COMMIT')
        return response
    except BaseException:
        if connection.in_transaction:
            connection.execute('ROLLBACK')
        raise

@bp.post('/api/auth/logout')
def logout():
    if g.session:
        db().execute('DELETE FROM sessions WHERE token=?',(g.session['token'],))
    response=make_response({'ok':True})
    response.delete_cookie('church_session',path='/',secure=current_app.config['APP_ENV']=='production',httponly=True,samesite='Strict')
    return response

@bp.post('/api/admin/login')
def admin_login():
    data=body()
    username=text(data,'username',100,True)
    if not rate('admin-ip:'+ip_key(),10,900) or not rate('admin-user:'+username,5,900):
        abort(429)
    admin=db().execute('SELECT * FROM admins WHERE username=? AND active=1',(username,)).fetchone()
    password_ok=check_password_hash(admin['password'] if admin else DUMMY_PASSWORD,text(data,'password',200,True))
    step=totp_step(decrypt(admin['totp']),text(data,'code',10)) if admin and password_ok else None
    if step is None:
        abort(401,'관리자 인증 정보를 확인하세요.')
    try:
        db().execute('INSERT INTO totp_used VALUES(?,?)',(admin['id'],step))
    except sqlite3.IntegrityError:
        abort(401,'이미 사용한 인증번호입니다.')
    audit(admin['id'],'admin_login')
    return new_session(admin=admin)

@bp.get('/cases')
@member_required
def cases_page():
    return render_template('member.html')

@bp.get('/board')
@member_required
def board_page():
    return render_template('member.html')

@bp.get('/api/cases')
@member_required
def cases():
    q=request.args.get('q','')[:200]
    start=request.args.get('start','')[:10]
    end=request.args.get('end','9999-12-31')[:10]
    rows=db().execute("SELECT id,title,event_date,topic,created,updated FROM cases WHERE state='published' AND (title LIKE ? OR topic LIKE ?) AND event_date>=? AND event_date<=? ORDER BY event_date,id",('%'+q+'%','%'+q+'%',start,end)).fetchall()
    return {'items':[dict(x) for x in rows]}

@bp.get('/api/cases/<case_id>')
@member_required
def case_detail(case_id):
    row=db().execute("SELECT * FROM cases WHERE id=? AND state='published'",(case_id,)).fetchone()
    if not row:
        abort(404)
    item=dict(row)
    item['data']=json.loads(item['data'])
    item.pop('author'); item.pop('reviewer')
    ids=item['data'].pop('clause_ids',[])
    item['clauses']=[]
    for clause_id in ids:
        clause=db().execute('SELECT * FROM clauses WHERE id=?',(clause_id,)).fetchone()
        if clause:
            item['clauses'].append({'id':clause_id,'verified':bool(clause['verified']),'data':json.loads(clause['data']) if clause['verified'] else {'location':'확인 중','content':'공식 출처와 사건 당시 적용 여부 확인 중'}})
    item['documents']=[{'id':x['id'],'title':x['title'],'metadata':json.loads(x['metadata'])} for x in db().execute("SELECT * FROM documents WHERE case_id=? AND kind='reading' AND approved=1",(case_id,))]
    return item

@bp.get('/api/documents/<doc_id>')
def download(doc_id):
    row=db().execute('SELECT * FROM documents WHERE id=?',(doc_id,)).fetchone()
    if not g.session:
        abort(401)
    if not row:
        abort(404)
    if g.session['member_id']:
        case=db().execute("SELECT id FROM cases WHERE id=? AND state='published'",(row['case_id'],)).fetchone()
        if row['kind']!='reading' or not row['approved'] or not case:
            abort(403)
    elif 'content' not in g.identity['roles'].split(',') and 'publish' not in g.identity['roles'].split(','):
        abort(403)
    raw=current_app.extensions['cipher'].decrypt((Path(current_app.config['DATA_DIR'])/'private'/row['path']).read_bytes())
    # Force download: never execute PDF/JPEG as inline active content.
    return send_file(io.BytesIO(raw),mimetype='application/octet-stream',as_attachment=True,download_name='document'+json.loads(row['metadata'])['extension'])

@bp.get('/api/posts')
@member_required
def posts():
    q=request.args.get('q','')[:200]
    rows=db().execute('SELECT * FROM posts WHERE deleted=0 AND hidden=0 AND (title LIKE ? OR body LIKE ?) ORDER BY created DESC LIMIT 500',('%'+q+'%','%'+q+'%')).fetchall()
    return {'items':[post_view(x,False) for x in rows]}

def post_view(row, detail=True):
    result=dict(row)
    member=db().execute('SELECT * FROM members WHERE id=?',(row['member_id'],)).fetchone()
    result['author']=display_name(member)
    result['own']=g.identity['id']==row['member_id']
    result.pop('member_id')
    if not detail:
        result.pop('body')
    return result

@bp.get('/api/posts/<post_id>')
@member_required
def post_detail(post_id):
    row=db().execute('SELECT * FROM posts WHERE id=? AND deleted=0 AND (hidden=0 OR member_id=?)',(post_id,g.identity['id'])).fetchone()
    if not row:
        abort(404)
    return post_view(row)

@bp.post('/api/posts')
@member_required
def create_post():
    if not rate('post:'+g.identity['id'],10,3600):
        abort(429)
    data=body()
    if data.get('real_name_notice') is not True:
        abort(400,'실명 표시 안내를 확인하세요.')
    title=text(data,'title',200,True)
    content=text(data,'body',20000,True)
    case_id=text(data,'case_id',40) or None
    if case_id and not db().execute("SELECT id FROM cases WHERE id=? AND state='published'",(case_id,)).fetchone():
        abort(400)
    post_id=uid()
    db().execute('INSERT INTO posts(id,member_id,case_id,title,body,created,updated) VALUES(?,?,?,?,?,?,?)',(post_id,g.identity['id'],case_id,title,content,now(),now()))
    return {'id':post_id},201

@bp.route('/api/posts/<post_id>',methods=['PUT','DELETE'])
@member_required
def change_post(post_id):
    connection=db()
    connection.execute('BEGIN IMMEDIATE')
    try:
        row=connection.execute('SELECT * FROM posts WHERE id=? AND deleted=0',(post_id,)).fetchone()
        if not row:
            abort(404)
        if row['member_id']!=g.identity['id']:
            abort(403)
        data=body()
        if data.get('expected_updated')!=row['updated']:
            abort(409,'다른 수정이 있습니다. 다시 열어주세요.')
        revision('post',post_id,dict(row),g.identity['id'])
        timestamp=max(now(),row['updated']+1)
        if request.method=='DELETE':
            connection.execute('UPDATE posts SET deleted=1,updated=? WHERE id=?',(timestamp,post_id))
        else:
            connection.execute('UPDATE posts SET title=?,body=?,updated=? WHERE id=?',(text(data,'title',200,True),text(data,'body',20000,True),timestamp,post_id))
        connection.execute('COMMIT')
    except BaseException:
        connection.execute('ROLLBACK')
        raise
    return {'ok':True}

@bp.post('/api/requests')
@member_required
def submit_request():
    if not rate('request-member:'+g.identity['id'],10,3600):
        abort(429)
    data=body()
    kind=text(data,'kind',30,True)
    if kind not in ('report','correction','evidence','appeal'):
        abort(400)
    target=text(data,'target',100)
    content=text(data,'body',20000,True)
    request_id=uid()
    db().execute('INSERT INTO requests(id,member_id,kind,target,body,created,updated) VALUES(?,?,?,?,?,?,?)',(request_id,g.identity['id'],kind,target,encrypt(content),now(),now()))
    return {'id':request_id},201

@bp.get('/api/requests')
@member_required
def own_requests():
    rows=db().execute('SELECT id,kind,target,status,response,created,updated FROM requests WHERE member_id=? ORDER BY created DESC',(g.identity['id'],)).fetchall()
    return {'items':[dict(x) for x in rows]}

@bp.get('/api/admin/members')
@admin_required('roster')
def admin_members():
    return {'items':[{'id':x['id'],'name':decrypt(x['name']),'phone':decrypt(x['phone']),'active':bool(x['active']),'version':x['version']} for x in db().execute('SELECT * FROM members ORDER BY created')]}

@bp.post('/api/admin/roster/preview')
@admin_required('roster')
def roster_preview():
    upload=request.files.get('file')
    if not upload or not upload.filename.lower().endswith('.xlsx'):
        abort(400,'XLSX 파일을 선택하세요.')
    return roster.preview(upload.read())

@bp.post('/api/admin/roster/apply')
@admin_required('roster')
def roster_apply():
    data=body()
    if not isinstance(data.get('decisions'),dict):
        abort(400)
    return roster.apply(text(data,'import_id',100,True),data['decisions'])

@bp.post('/api/admin/members/<member_id>')
@admin_required('roster')
def member_status(member_id):
    data=body()
    reason=text(data,'reason',1000,True)
    if not isinstance(data.get('active'),bool):
        abort(400)
    connection=db()
    connection.execute('BEGIN IMMEDIATE')
    try:
        if not connection.execute('SELECT id FROM members WHERE id=?',(member_id,)).fetchone():
            abort(404)
        connection.execute('UPDATE members SET active=?,version=version+1,updated=? WHERE id=?',(int(data['active']),now(),member_id))
        connection.execute('DELETE FROM sessions WHERE member_id=?',(member_id,))
        connection.execute('UPDATE challenges SET used=1 WHERE member_id=?',(member_id,))
        audit(g.identity['id'],'member_active' if data['active'] else 'member_inactive',member_id,reason)
        connection.execute('COMMIT')
    except BaseException:
        connection.execute('ROLLBACK'); raise
    return {'ok':True}

@bp.post('/api/admin/members/<member_id>/grant')
@admin_required('roster')
def grant(member_id):
    data=body()
    reason=text(data,'reason',1000,True)
    if data.get('identity_confirmed') is not True:
        abort(400,'별도 신원 확인을 완료해야 합니다.')
    member=db().execute('SELECT * FROM members WHERE id=? AND active=1',(member_id,)).fetchone()
    if not member:
        abort(404)
    token=uid(); code=secrets.token_urlsafe(24)
    db().execute("INSERT INTO challenges VALUES(?,?,?,?,?,0,0,'manual')",(token,member_id,member['version'],digest(token+':'+code),now()+900))
    audit(g.identity['id'],'personal_grant',member_id,reason)
    return {'challenge_id':token,'code':code,'expires_in':900,'message':'확인한 본인에게만 안전하게 전달하세요. 1회 사용 후 폐기됩니다.'}

@bp.get('/api/admin/content')
@admin_required()
def admin_content():
    if not {'content','publish'}.intersection(g.identity['roles'].split(',')):
        abort(403)
    cases=[{**dict(x),'data':json.loads(x['data'])} for x in db().execute('SELECT * FROM cases ORDER BY event_date')]
    clauses=[{**dict(x),'data':json.loads(x['data'])} for x in db().execute('SELECT * FROM clauses')]
    documents=[{k:x[k] for k in ('id','case_id','kind','title','approved','author','reviewer','created')}|{'metadata':json.loads(x['metadata'])} for x in db().execute('SELECT * FROM documents')]
    return {'cases':cases,'clauses':clauses,'documents':documents}

@bp.post('/api/admin/cases')
@admin_required('content')
def save_case():
    data=body()
    case_id=text(data,'id',40) or uid()
    title=text(data,'title',200,True)
    event_date=text(data,'event_date',10,True)
    try:
        from datetime import date
        date.fromisoformat(event_date)
    except ValueError:
        abort(400,'발생일을 확인하세요.')
    topic=text(data,'topic',200)
    details=json_fields(data,CASE_FIELDS)
    clause_ids=data.get('clause_ids',[])
    if not isinstance(clause_ids,list) or len(clause_ids)>50 or any(not isinstance(x,str) for x in clause_ids):
        abort(400)
    details['clause_ids']=clause_ids
    connection=db(); connection.execute('BEGIN IMMEDIATE')
    try:
        old=connection.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
        if old:
            if data.get('expected_updated')!=old['updated']:
                abort(409,'다른 수정이 있습니다.')
            revision('case',case_id,dict(old),g.identity['id'])
            connection.execute("UPDATE cases SET title=?,event_date=?,topic=?,data=?,state='draft',author=?,reviewer=NULL,updated=? WHERE id=?",(title,event_date,topic,json.dumps(details,ensure_ascii=False),g.identity['id'],max(now(),old['updated']+1),case_id))
        else:
            connection.execute("INSERT INTO cases VALUES(?,?,?,?,?,'draft',?,NULL,?,?)",(case_id,title,event_date,topic,json.dumps(details,ensure_ascii=False),g.identity['id'],now(),now()))
        audit(g.identity['id'],'case_saved',case_id)
        connection.execute('COMMIT')
    except BaseException:
        connection.execute('ROLLBACK'); raise
    return {'id':case_id}

@bp.post('/api/admin/cases/<case_id>/state')
@admin_required()
def case_state(case_id):
    data=body(); state=text(data,'state',20,True); reason=text(data,'reason',1000,True)
    if state not in ('draft','review','published'):
        abort(400)
    needed='publish' if state=='published' else 'content'
    if needed not in g.identity['roles'].split(','):
        abort(403)
    connection=db(); connection.execute('BEGIN IMMEDIATE')
    try:
        row=connection.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
        if not row:
            abort(404)
        if data.get('expected_updated')!=row['updated']:
            abort(409)
        if state=='published' and (row['state']!='review' or row['author']==g.identity['id']):
            abort(400,'검토 중 상태에서 작성자 외 승인자가 게시해야 합니다.')
        revision('case',case_id,dict(row),g.identity['id'])
        connection.execute('UPDATE cases SET state=?,reviewer=?,updated=? WHERE id=?',(state,g.identity['id'] if state=='published' else None,max(now(),row['updated']+1),case_id))
        audit(g.identity['id'],'case_'+state,case_id,reason)
        connection.execute('COMMIT')
    except BaseException:
        connection.execute('ROLLBACK'); raise
    return {'ok':True}

@bp.post('/api/admin/clauses')
@admin_required('content')
def save_clause():
    data=body(); clause_id=text(data,'id',40) or uid()
    details=json_fields(data,CLAUSE_FIELDS)
    # Editorial verification is a separate action by a second administrator.
    connection=db(); connection.execute('BEGIN IMMEDIATE')
    try:
        old=connection.execute('SELECT * FROM clauses WHERE id=?',(clause_id,)).fetchone()
        if old:
            if data.get('expected_updated')!=old['updated']:
                abort(409,'다른 조문 수정이 있습니다. 다시 열어주세요.')
            revision('clause',clause_id,dict(old),g.identity['id'])
        timestamp=max(now(),old['updated']+1) if old else now()
        connection.execute('INSERT INTO clauses VALUES(?,?,0,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,verified=0,author=excluded.author,updated=excluded.updated',(clause_id,json.dumps(details,ensure_ascii=False),g.identity['id'],timestamp))
        audit(g.identity['id'],'clause_saved',clause_id)
        connection.execute('COMMIT')
    except BaseException:
        connection.execute('ROLLBACK'); raise
    return {'id':clause_id}

@bp.post('/api/admin/clauses/<clause_id>/verify')
@admin_required('publish')
def verify_clause(clause_id):
    data=body(); reason=text(data,'reason',1000,True)
    row=db().execute('SELECT * FROM clauses WHERE id=?',(clause_id,)).fetchone()
    if not row:
        abort(404)
    if data.get('expected_updated')!=row['updated']:
        abort(409,'조문이 수정되었습니다. 다시 확인하세요.')
    details=json.loads(row['data'])
    source=urlparse(details['source_url'])
    if source.scheme!='https' or not (source.hostname=='pck.or.kr' or (source.hostname or '').endswith('.pck.or.kr')):
        abort(400,'통합 총회 공식 출처(HTTPS pck.or.kr)가 필요합니다.')
    if row['author']==g.identity['id'] or not all(details[x] for x in ('location','content','checked_date','effective_date','applicable_period','instrument')) or data.get('official_source_checked') is not True:
        abort(400,'작성자 외 검토자가 출처·시행일·적용 여부를 확인해야 합니다.')
    changed=db().execute('UPDATE clauses SET verified=1 WHERE id=? AND updated=?',(clause_id,row['updated']))
    if changed.rowcount!=1:
        abort(409,'조문이 수정되었습니다. 다시 확인하세요.')
    audit(g.identity['id'],'clause_verified',clause_id,reason)
    return {'ok':True}

@bp.post('/api/admin/documents')
@admin_required('content')
def upload_document():
    upload=request.files.get('file')
    case_id=request.form.get('case_id','')
    kind=request.form.get('kind','original')
    if not upload or kind not in ('original','reading') or not db().execute('SELECT id FROM cases WHERE id=?',(case_id,)).fetchone():
        abort(400)
    raw=upload.read()
    if raw.startswith(b'%PDF-'):
        extension='.pdf'
    elif raw.startswith(b'\x89PNG\r\n\x1a\n'):
        extension='.png'
    elif raw.startswith(b'\xff\xd8\xff'):
        extension='.jpg'
    else:
        abort(400,'PDF, PNG, JPEG만 가능합니다.')
    metadata={k:request.form.get(k,'')[:2000] for k in ('source','acquired_date','excerpt','excerpt_scope','redaction_reason')}
    if not metadata['source'] or not metadata['acquired_date']:
        abort(400,'출처와 확보일이 필요합니다.')
    metadata['extension']=extension
    doc_id=uid(); path=doc_id+'.enc'
    (Path(current_app.config['DATA_DIR'])/'private'/path).write_bytes(current_app.extensions['cipher'].encrypt(raw))
    try:
        db().execute('INSERT INTO documents VALUES(?,?,?,?,?,?,0,?,NULL,?)',(doc_id,case_id,kind,request.form.get('title','자료')[:200],path,json.dumps(metadata,ensure_ascii=False),g.identity['id'],now()))
    except BaseException:
        (Path(current_app.config['DATA_DIR'])/'private'/path).unlink(missing_ok=True)
        raise
    audit(g.identity['id'],'document_uploaded',doc_id)
    return {'id':doc_id},201

@bp.post('/api/admin/documents/<doc_id>/approve')
@admin_required('publish')
def approve_document(doc_id):
    data=body(); reason=text(data,'reason',1000,True)
    row=db().execute('SELECT * FROM documents WHERE id=?',(doc_id,)).fetchone()
    if not row:
        abort(404)
    if row['kind']!='reading' or row['author']==g.identity['id'] or data.get('irreversible_redaction_checked') is not True:
        abort(400,'작성자 외 검토자가 열람본의 복구 불가능한 가림과 전체 내용을 확인해야 합니다.')
    db().execute('UPDATE documents SET approved=1,reviewer=? WHERE id=?',(g.identity['id'],doc_id))
    audit(g.identity['id'],'document_approved',doc_id,reason)
    return {'ok':True}

@bp.post('/api/admin/documents/<doc_id>/withdraw')
@admin_required('publish')
def withdraw_document(doc_id):
    reason=text(body(),'reason',1000,True)
    db().execute('UPDATE documents SET approved=0 WHERE id=?',(doc_id,))
    audit(g.identity['id'],'document_withdrawn',doc_id,reason)
    return {'ok':True}

@bp.get('/api/admin/requests')
@admin_required('moderate')
def admin_requests():
    return {'items':[{**dict(x),'body':decrypt(x['body'])} for x in db().execute('SELECT * FROM requests ORDER BY created DESC')]}

@bp.post('/api/admin/requests/<request_id>')
@admin_required('moderate')
def resolve_request(request_id):
    data=body(); status=text(data,'status',20,True); response=text(data,'response',20000,True)
    if status not in ('open','review','resolved','declined'):
        abort(400)
    db().execute('UPDATE requests SET status=?,response=?,updated=? WHERE id=?',(status,response,now(),request_id))
    audit(g.identity['id'],'request_'+status,request_id,'처리 응답 기록')
    return {'ok':True}

@bp.get('/api/admin/posts')
@admin_required('moderate')
def admin_posts():
    # No editing API for administrators. Content moderation changes visibility only.
    return {'items':[{**dict(x),'author':display_name(db().execute('SELECT * FROM members WHERE id=?',(x['member_id'],)).fetchone())} for x in db().execute('SELECT * FROM posts ORDER BY created DESC LIMIT 500')]}

@bp.post('/api/admin/posts/<post_id>/visibility')
@admin_required('moderate')
def moderate(post_id):
    data=body(); reason=text(data,'reason',1000,True)
    if not isinstance(data.get('hidden'),bool):
        abort(400)
    db().execute('UPDATE posts SET hidden=?,reason=? WHERE id=?',(int(data['hidden']),reason,post_id))
    audit(g.identity['id'],'post_hidden' if data['hidden'] else 'post_restored',post_id,reason)
    return {'ok':True}

@bp.get('/api/admin/audit')
@admin_required()
def audit_list():
    return {'items':[dict(x) for x in db().execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500')]}

@bp.get('/api/changes')
@member_required
def changes():
    # Only safe publication/correction summaries for published cases; private revisions excluded.
    rows=db().execute("SELECT audit.action,audit.target,audit.reason,audit.created FROM audit JOIN cases ON cases.id=audit.target WHERE cases.state='published' AND audit.action IN ('case_published') ORDER BY audit.id DESC LIMIT 100").fetchall()
    return {'items':[dict(x) for x in rows]}

@bp.get('/api/my-posts')
@member_required
def my_posts():
    return {'items':[post_view(x,False) for x in db().execute('SELECT * FROM posts WHERE member_id=? AND deleted=0 ORDER BY created DESC',(g.identity['id'],))]}

@bp.get('/api/admin/revisions/<kind>/<target>')
@admin_required()
def admin_revisions(kind,target):
    roles=g.identity['roles'].split(',')
    if (kind=='post' and 'moderate' not in roles) or (kind in ('case','clause') and not {'content','publish'}.intersection(roles)) or kind not in ('case','clause','post'):
        abort(403)
    return {'items':[{**dict(x),'payload':json.loads(decrypt(x['payload']))} for x in db().execute('SELECT * FROM revisions WHERE kind=? AND target=? ORDER BY id DESC LIMIT 100',(kind,target))]}
