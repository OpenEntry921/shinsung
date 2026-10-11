import base64
import getpass
import json
import os
import secrets
import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path
import click
from werkzeug.security import generate_password_hash
from .db import db, now, audit
from .security import encrypt


def register(app):
    @app.cli.command('create-admin')
    @click.option('--username',prompt=True)
    @click.option('--roles',default='roster,content,publish,moderate',help='comma separated roster,content,publish,moderate')
    def create_admin(username,roles):
        if not set(roles.split(',')) <= {'roster','content','publish','moderate'}:
            raise click.ClickException('Invalid roles')
        password=getpass.getpass('Password (12+ characters): ')
        if len(password)<12:
            raise click.ClickException('Password too short')
        totp=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
        admin_id=secrets.token_hex(16)
        db().execute('INSERT INTO admins VALUES(?,?,?,?,?,1)',(admin_id,username,generate_password_hash(password),encrypt(totp),roles))
        audit('server-cli','admin_created',admin_id)
        click.echo('Authenticator setup secret (shown once, do not store in logs): '+totp)
        click.echo('Add to your authenticator app with account '+username+', issuer Shinsung, 6 digits, 30 seconds.')

    @app.cli.command('disable-admin')
    @click.argument('username')
    def disable_admin(username):
        row=db().execute('SELECT id FROM admins WHERE username=?',(username,)).fetchone()
        if not row:
            raise click.ClickException('Administrator not found')
        db().execute('UPDATE admins SET active=0 WHERE id=?',(row['id'],))
        db().execute('DELETE FROM sessions WHERE admin_id=?',(row['id'],))
        audit('server-cli','admin_disabled',row['id'])

    @app.cli.command('backup')
    @click.argument('output',type=click.Path())
    def backup(output):
        """Encrypted, consistent DB + private file snapshot. Store outside DATA_DIR."""
        root=Path(app.config['DATA_DIR'])
        connection=db()
        connection.execute('BEGIN IMMEDIATE')
        try:
            with tempfile.TemporaryDirectory() as temp:
                snapshot=Path(temp)
                source=sqlite3.connect(app.config['DB_PATH'])
                target=sqlite3.connect(snapshot/'church.db')
                source.backup(target)
                source.close();target.close()
                shutil.copytree(root/'private',snapshot/'private')
                (snapshot/'manifest.json').write_text(json.dumps({'schema':1,'created':now()}))
                archive=snapshot/'snapshot.tar.gz'
                with tarfile.open(archive,'w:gz') as pack:
                    for name in ('church.db','private','manifest.json'):
                        pack.add(snapshot/name,arcname=name)
                with open(output,'xb') as destination:
                    os.chmod(output,0o600)
                    destination.write(app.extensions['cipher'].encrypt(archive.read_bytes()))
        finally:
            connection.execute('ROLLBACK')
        click.echo('Encrypted backup created. Keep DATA_KEY in a separate secure location.')

    @app.cli.command('restore')
    @click.argument('backup_file',type=click.Path(exists=True))
    def restore(backup_file):
        """Only restore to an empty DATA_DIR with all web workers stopped."""
        root=Path(app.config['DATA_DIR'])
        if db().execute('SELECT COUNT(*) FROM members').fetchone()[0] or db().execute('SELECT COUNT(*) FROM admins').fetchone()[0] or any((root/'private').iterdir()):
            raise click.ClickException('Restore only to an empty, stopped instance')
        raw=app.extensions['cipher'].decrypt(Path(backup_file).read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/'snapshot.tar.gz'; archive.write_bytes(raw)
            with tarfile.open(archive,'r:gz') as pack:
                pack.extractall(Path(temp)/'snapshot',filter='data')
            snapshot=Path(temp)/'snapshot'
            test=sqlite3.connect(snapshot/'church.db')
            if test.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise click.ClickException('Backup database integrity check failed')
            # Sessions and unused OTPs must not become valid again after restoration.
            test.execute('DELETE FROM outbox');test.execute('DELETE FROM sessions');test.execute('DELETE FROM challenges');test.execute('DELETE FROM imports');test.commit();test.close()
            db().close()
            for suffix in ('','-wal','-shm'):
                Path(app.config['DB_PATH']+suffix).unlink(missing_ok=True)
            shutil.copy2(snapshot/'church.db',root/'church.db')
            shutil.copytree(snapshot/'private',root/'private',dirs_exist_ok=True)
        click.echo('Restored. Restart workers and verify health and protected documents.')

    @app.cli.command('purge-expired')
    def purge_expired():
        from .db import purge_expired as purge
        purge()
        click.echo('Expired operational records removed.')
