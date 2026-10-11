import json
import sqlite3
import time
from flask import current_app, g

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS members(id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,phone_key TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,version INTEGER NOT NULL DEFAULT 1,created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS phone_idx ON members(phone_key);
CREATE TABLE IF NOT EXISTS admins(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,totp TEXT NOT NULL,roles TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,member_id TEXT,admin_id TEXT,version INTEGER,csrf TEXT NOT NULL,expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS challenges(id TEXT PRIMARY KEY,member_id TEXT,version INTEGER,hash TEXT NOT NULL,expires INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,used INTEGER NOT NULL DEFAULT 0,kind TEXT NOT NULL DEFAULT 'sms');
CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,payload TEXT NOT NULL,expires INTEGER NOT NULL,claimed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS rates(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY,admin_id TEXT NOT NULL,payload TEXT NOT NULL,expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,title TEXT NOT NULL,event_date TEXT NOT NULL,topic TEXT NOT NULL,data TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'draft',author TEXT NOT NULL,reviewer TEXT,created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS clauses(id TEXT PRIMARY KEY,data TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,author TEXT NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,path TEXT NOT NULL,metadata TEXT NOT NULL,approved INTEGER NOT NULL DEFAULT 0,author TEXT NOT NULL,reviewer TEXT,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY,member_id TEXT NOT NULL,case_id TEXT,title TEXT NOT NULL,body TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,deleted INTEGER NOT NULL DEFAULT 0,hidden INTEGER NOT NULL DEFAULT 0,reason TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,member_id TEXT NOT NULL,kind TEXT NOT NULL,target TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',response TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,target TEXT NOT NULL,payload TEXT NOT NULL,actor TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS totp_used(admin_id TEXT NOT NULL,step INTEGER NOT NULL,PRIMARY KEY(admin_id,step));
'''

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DB_PATH'], timeout=15, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=15000')
    return g.db

def init():
    db().executescript(SCHEMA)

def now():
    return int(time.time())

def audit(actor, action, target='', reason=''):
    db().execute('INSERT INTO audit(actor,action,target,reason,created) VALUES(?,?,?,?,?)',(actor,action,target,reason,now()))

def revision(kind, target, payload, actor):
    # Private historical data; never returned in member APIs.
    db().execute('INSERT INTO revisions(kind,target,payload,actor,created) VALUES(?,?,?,?,?)',(kind,target,current_app.extensions['cipher'].encrypt(json.dumps(payload,ensure_ascii=False).encode()).decode(),actor,now()))


def purge_expired():
    t=now()
    connection=db()
    connection.execute('BEGIN IMMEDIATE')
    try:
        for table in ('sessions','challenges','imports','rates','outbox'):
            connection.execute(f'DELETE FROM {table} WHERE expires<=?',(t,))
        connection.execute('DELETE FROM totp_used WHERE step<?',(t//30-2,))
        connection.execute("DELETE FROM revisions WHERE kind='post' AND created<?",(t-30*86400,))
        connection.execute('DELETE FROM posts WHERE deleted=1 AND updated<?',(t-30*86400,))
        connection.execute('DELETE FROM audit WHERE created<?',(t-90*86400,))
        connection.execute("DELETE FROM requests WHERE status IN ('resolved','declined') AND updated<?",(t-180*86400,))
        connection.execute('COMMIT')
    except BaseException:
        connection.execute('ROLLBACK')
        raise
