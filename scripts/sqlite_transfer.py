#!/usr/bin/env python3
"""Operator-only external backup. Never prints records or the PostgreSQL password.
Requires psycopg[binary]. Run before redeploying the old SQLite container.
"""
import argparse
import getpass
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import psycopg

TABLE = 'shinsung_sqlite_backups'

def archive(source, dsn):
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    params = conninfo_to_dict(dsn)
    params.setdefault('sslmode', 'verify-full')
    dsn = make_conninfo(**params)
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError('원본 SQLite 파일이 없습니다.')
    with tempfile.TemporaryDirectory() as directory:
        snapshot = Path(directory)/'snapshot.sqlite3'
        with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(snapshot) as dst:
            src.backup(dst)
            if dst.execute('pragma integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite 무결성 검증 실패')
            members = dst.execute('select count(*) from portal_member').fetchone()[0]
            counts = {label: dst.execute('select count(*) from '+table).fetchone()[0] for label, table in [('users','auth_user'),('cases','portal_case'),('documents','portal_document'),('posts','portal_post')]}
        os.chmod(snapshot, 0o600)
        raw = snapshot.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with psycopg.connect(dsn, connect_timeout=10) as db:
        db.execute(f'CREATE TABLE IF NOT EXISTS {TABLE} (sha256 varchar(64) PRIMARY KEY, data bytea NOT NULL, created_at timestamptz NOT NULL DEFAULT now())')
        db.execute(f'INSERT INTO {TABLE} (sha256,data) VALUES (%s,%s) ON CONFLICT (sha256) DO NOTHING', (digest,raw))
    # Verify the committed external copy using a new connection.
    with psycopg.connect(dsn, connect_timeout=10) as db:
        restored = bytes(db.execute(f'SELECT data FROM {TABLE} WHERE sha256=%s', (digest,)).fetchone()[0])
        if restored != raw or hashlib.sha256(restored).hexdigest() != digest:
            raise ValueError('외부 백업 검증 실패')
    return {'sha256': digest, 'bytes': len(raw), 'members': members, 'external_copy_verified': True, **counts}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--persistence-confirmed', action='store_true', required=True, help='DB 서비스의 보존 조건을 실제 확인한 뒤에만 사용')
    args = parser.parse_args()
    try:
        import json
        result = archive(args.source, getpass.getpass('새 PostgreSQL 접속 URL (입력 숨김): '))
        print(json.dumps(result))
    except Exception:
        raise SystemExit('백업 실패. 원본은 변경하지 않았습니다. 접속·권한·보존 조건을 확인하세요. 비밀정보는 출력하지 않습니다.') from None

if __name__ == '__main__':
    main()
