"""Durable encrypted OTP outbox. Network latency never reveals roster matches."""
import json
import threading
import time
from flask import current_app
from .db import db, now, purge_expired
from .security import send_sms, encrypt, decrypt


def enqueue(challenge_id, phone, code):
    if current_app.config['APP_ENV']=='test':
        if send_sms(phone,code):
            db().execute('UPDATE challenges SET used=0 WHERE id=?',(challenge_id,))
        return
    db().execute('INSERT INTO outbox VALUES(?,?,?,0)',(challenge_id,encrypt(json.dumps({'phone':phone,'code':code})),now()+300))


def process_one():
    # At most one worker claims a message. Ambiguous transport failures never retry
    # and require a new challenge; no duplicated SMS after a worker crash.
    row=db().execute('UPDATE outbox SET claimed=1 WHERE id=(SELECT id FROM outbox WHERE claimed=0 AND expires>? LIMIT 1) RETURNING *',(now(),)).fetchone()
    if not row:
        return
    challenge=db().execute('SELECT * FROM challenges WHERE id=? AND expires>?',(row['id'],now())).fetchone()
    member=db().execute('SELECT * FROM members WHERE id=? AND version=? AND active=1',(challenge['member_id'],challenge['version'])).fetchone() if challenge else None
    if member:
        payload=json.loads(decrypt(row['payload']))
        if send_sms(payload['phone'],payload['code']):
            db().execute('UPDATE challenges SET used=0 WHERE id=? AND expires>? AND version=(SELECT version FROM members WHERE id=? AND active=1)',(row['id'],now(),member['id']))
    db().execute('DELETE FROM outbox WHERE id=?',(row['id'],))


def start_worker(app):
    def loop():
        last_cleanup=0
        while True:
            try:
                with app.app_context():
                    process_one()
                    if now()-last_cleanup>3600:
                        purge_expired()
                        last_cleanup=now()
            except Exception:
                # Never print exception payloads containing private messages.
                app.logger.error('SMS worker operation failed; check service configuration and storage.')
            time.sleep(2)
    thread=threading.Thread(target=loop,name='sms-outbox',daemon=True)
    app.extensions['sms_worker']=thread
    thread.start()
