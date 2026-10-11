"""Use the managed cloud proxy and its public CA bundle without disabling TLS."""
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

root = Path(__file__).resolve().parent.parent
command = ['docker', 'build', '--tag', 'shinsung-onboarding:local']
proxy = os.environ.get('HTTPS_PROXY')
if proxy:
    host = urlparse(proxy).hostname
    command += ['--network=host', '--add-host', f'{host}:{socket.gethostbyname(host)}',
                '--build-arg', 'HTTP_PROXY', '--build-arg', 'HTTPS_PROXY', '--build-arg', 'NO_PROXY=']
ca = os.environ.get('SSL_CERT_FILE')
if ca:
    bundle = Path(ca).read_bytes()
    if b'BEGIN CERTIFICATE' not in bundle or b'PRIVATE KEY' in bundle:
        raise SystemExit('A public trust certificate bundle is required.')
    command += ['--secret', f'id=build_ca,src={ca}']
command += ['.']
with tempfile.TemporaryDirectory(prefix='shinsung-docker-') as configuration:
    environment = dict(os.environ)
    environment.setdefault('DOCKER_CONFIG', configuration)
    with tempfile.NamedTemporaryFile(prefix='shinsung-build-',suffix='.log',delete=False) as log:
        result = subprocess.run(command,cwd=root,env=environment,stdout=log,stderr=log)
        logfile = Path(log.name)
    # Never display proxy values or credential user-info from error output.
    contents = logfile.read_text(errors='replace')
    for name in ('HTTP_PROXY','HTTPS_PROXY'):
        if os.environ.get(name): contents = contents.replace(os.environ[name], '[configured proxy]')
    logfile.write_text(contents)
print(f'Image build exit status: {result.returncode}; private build log: {logfile}')
raise SystemExit(result.returncode)
