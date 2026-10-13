"""Explicit PostgreSQL configuration; malformed URLs never fall back to SQLite."""
from urllib.parse import urlsplit, parse_qs, unquote
from django.core.exceptions import ImproperlyConfigured

def postgres(url):
    try:
        value = urlsplit(url)
        options = parse_qs(value.query, strict_parsing=True)
        if value.fragment or value.scheme not in ('postgres', 'postgresql') or not value.hostname or not value.username or not value.path.strip('/'):
            raise ValueError
        if set(options) - {'sslmode', 'sslrootcert'} or any(len(v) != 1 for v in options.values()):
            raise ValueError
        sslmode = options.get('sslmode', ['verify-full'])[0]
        if sslmode not in ('verify-full', 'verify-ca', 'require', 'disable'):
            raise ValueError
        return {'ENGINE': 'django.db.backends.postgresql', 'NAME': unquote(value.path[1:]),
                'USER': unquote(value.username), 'PASSWORD': unquote(value.password or ''),
                'HOST': value.hostname, 'PORT': value.port or 5432, 'CONN_MAX_AGE': 60,
                'CONN_HEALTH_CHECKS': True,
                'OPTIONS': {'connect_timeout': 10, 'sslmode': sslmode,
                            **({'sslrootcert': options['sslrootcert'][0]} if 'sslrootcert' in options else {})}}
    except (ValueError, TypeError):
        raise ImproperlyConfigured('DATABASE_URL PostgreSQL 형식 또는 TLS 설정을 확인하세요.') from None
