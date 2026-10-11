import base64
import hashlib
import hmac
import secrets
import struct
import time
from functools import wraps
import requests
from flask import abort, current_app, g, request, make_response
from .db import db, now


def digest(value):
    return hmac.new(current_app.config['APP_SECRET'].encode(),value.encode(),hashlib.sha256).hexdigest()

def encrypt(value):
    return current_app.extensions['cipher'].encrypt(value.encode()).decode()

def decrypt(value):
    return current_app.extensions['cipher'].decrypt(value.encode()).decode()

def normalize_phone(value):
    return ''.join(c for c in str(value) if c.isdigit())

def valid_phone(value):
    return value.isascii() and value.isdigit() and value.startswith('0') and 9 <= len(value) <= 11

def rate(key, limit, seconds):
    key = digest(key)
    t = now()
    # Atomic shared rate limit across gunicorn workers, backed by DB.
    r = db().execute('''INSERT INTO rates VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN expires<=? THEN 1 ELSE count+1 END,expires=CASE WHEN expires<=? THEN excluded.expires ELSE expires END RETURNING count''',(key,t+seconds,t,t)).fetchone()
    return r['count'] <= limit

def ip_key():
    # Deliberately ignore untrusted X-Forwarded-For. Shared proxy limits are conservative.
    return request.remote_addr or 'unknown'

def load_session():
    g.identity = None
    g.session = None
    token = request.cookies.get('church_session','')
    if not token:
        return
    s = db().execute('SELECT * FROM sessions WHERE token=? AND expires>?',(digest(token),now())).fetchone()
    if not s:
        return
    if s['member_id']:
        who = db().execute('SELECT * FROM members WHERE id=? AND active=1 AND version=?',(s['member_id'],s['version'])).fetchone()
    else:
        who = db().execute('SELECT * FROM admins WHERE id=? AND active=1',(s['admin_id'],)).fetchone()
    if who:
        g.session=s
        g.identity=who

def member_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not g.session or not g.session['member_id']:
            abort(401)
        return fn(*a,**kw)
    return wrapper

def admin_required(role=None):
    def decorate(fn):
        @wraps(fn)
        def wrapper(*a,**kw):
            if not g.session or not g.session['admin_id']:
                abort(403)
            if role and role not in g.identity['roles'].split(','):
                abort(403)
            return fn(*a,**kw)
        return wrapper
    return decorate

def new_session(member=None, admin=None):
    token=secrets.token_urlsafe(32)
    csrf=secrets.token_urlsafe(32)
    db().execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest(token),member['id'] if member else None,admin['id'] if admin else None,member['version'] if member else None,csrf,now()+(1800 if admin else 7200)))
    response=make_response({'ok':True,'csrf':csrf})
    response.set_cookie('church_session',token,secure=current_app.config['APP_ENV']=='production',httponly=True,samesite='Strict',max_age=1800 if admin else 7200,path='/')
    return response

def totp_step(secret, code):
    try:
        key=base64.b32decode(secret.upper()+'='*((8-len(secret)%8)%8))
        for step in range(int(time.time()//30)-1,int(time.time()//30)+2):
            raw=hmac.new(key,struct.pack('>Q',step),hashlib.sha1).digest()
            offset=raw[-1]&15
            val=(struct.unpack('>I',raw[offset:offset+4])[0]&0x7fffffff)%1000000
            if hmac.compare_digest(f'{val:06d}',str(code)):
                return step
    except (ValueError,TypeError):
        pass
    return None

def send_sms(phone, code):
    if current_app.config['APP_ENV']=='test':
        current_app.extensions['test_sms'][phone]=code
        return True
    cfg=current_app.config
    if not all(cfg.get(k) for k in ('SOLAPI_KEY','SOLAPI_SECRET','SMS_SENDER')):
        return False
    date=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    salt=secrets.token_hex(16)
    signature=hmac.new(cfg['SOLAPI_SECRET'].encode(),(date+salt).encode(),hashlib.sha256).hexdigest()
    try:
        r=requests.post('https://api.solapi.com/messages/v4/send-many/detail',headers={'Authorization':f"HMAC-SHA256 apiKey={cfg['SOLAPI_KEY']}, date={date}, salt={salt}, signature={signature}"},json={'messages':[{'to':phone,'from':cfg['SMS_SENDER'],'type':'SMS','text':f'[교인 알림] 인증번호 {code} (5분). 타인에게 전달 금지.'}]},timeout=10)
        # Do not log vendor request/response (phone and code).
        if r.status_code not in (200,201,202):
            return False
        result=r.json()
        return not result.get('failedMessageList', [True]) and result.get('groupInfo',{}).get('count',{}).get('registeredSuccess') == 1
    except (requests.RequestException,ValueError):
        return False
