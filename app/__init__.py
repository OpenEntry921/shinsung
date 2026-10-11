import os
import secrets
from pathlib import Path
from cryptography.fernet import Fernet
from flask import Flask, abort, g, request, render_template
from werkzeug.exceptions import HTTPException
from .db import init, db
from .security import load_session


def create_app(config=None):
    app=Flask(__name__)
    app.config.update(APP_ENV=os.environ.get('APP_ENV','production'),APP_SECRET=os.environ.get('APP_SECRET',''),DATA_KEY=os.environ.get('DATA_KEY',''),DATA_DIR=os.environ.get('DATA_DIR','data'),PUBLIC_ORIGIN=os.environ.get('PUBLIC_ORIGIN',''),CONTACT_TEXT=os.environ.get('CONTACT_TEXT','운영자 문의처 미설정'),POLICY_APPROVED=os.environ.get('POLICY_APPROVED')=='1',MAX_CONTENT_LENGTH=8*1024*1024,MAX_FORM_MEMORY_SIZE=8*1024*1024)
    for key in ('SOLAPI_KEY','SOLAPI_SECRET','SMS_SENDER'):
        app.config[key]=os.environ.get(key,'')
    if config:
        app.config.update(config)
    if app.config['APP_ENV']=='test' and not app.config.get('TESTING'):
        raise RuntimeError('Test SMS mode requires explicit TESTING configuration; cannot serve from environment.')
    for key in ('POLICY_CONTROLLER','POLICY_BASIS','POLICY_ROSTER_RETENTION','POLICY_DOCUMENT_RETENTION','POLICY_BACKUP_RETENTION'):
        app.config.setdefault(key,os.environ.get(key,''))
    if app.config['APP_ENV']=='production' and app.config['POLICY_APPROVED'] and not all(app.config[k] for k in ('POLICY_CONTROLLER','POLICY_BASIS','POLICY_ROSTER_RETENTION','POLICY_DOCUMENT_RETENTION','POLICY_BACKUP_RETENTION')):
        raise RuntimeError('Finalize controller, processing basis and retention policy before approving access.')
    if app.config['APP_ENV'] not in ('production','development','test'):
        raise RuntimeError('Invalid APP_ENV')
    if len(app.config['APP_SECRET'])<32 or not app.config['DATA_KEY']:
        raise RuntimeError('Set APP_SECRET (32+ characters) and DATA_KEY (Fernet key).')
    if app.config['APP_ENV']=='production' and not app.config['PUBLIC_ORIGIN'].startswith('https://'):
        raise RuntimeError('Production requires HTTPS PUBLIC_ORIGIN.')
    root=Path(app.config['DATA_DIR']).resolve()
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    (root/'private').mkdir(exist_ok=True,mode=0o700)
    app.config['DATA_DIR']=str(root)
    app.config['DB_PATH']=str(root/'church.db')
    app.extensions['cipher']=Fernet(app.config['DATA_KEY'].encode())
    app.extensions['test_sms']={}
    with app.app_context():
        init()

    @app.teardown_appcontext
    def close(_):
        conn=g.pop('db',None)
        if conn:
            conn.close()

    @app.before_request
    def protect():
        if request.path=='/healthz':
            return None
        load_session()
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('Origin')!=app.config['PUBLIC_ORIGIN']:
                abort(403,'요청 출처를 확인할 수 없습니다.')
            if g.session and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),g.session['csrf']):
                abort(403,'세션 확인 후 다시 시도하세요.')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Robots-Tag']='noindex, nofollow, noarchive'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        if app.config['APP_ENV']=='production':
            response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.errorhandler(HTTPException)
    def error(err):
        if request.path.startswith('/api/'):
            return {'error':err.description},err.code
        return render_template('error.html',code=err.code,message=err.description),err.code

    @app.get('/healthz')
    def health():
        db().execute('SELECT 1')
        return {'status':'ok'}

    from .routes import bp
    app.register_blueprint(bp)
    from .cli import register
    register(app)
    return app
