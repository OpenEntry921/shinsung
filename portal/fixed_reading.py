"""Authenticated encrypted server text; plaintext lives only in process memory."""
import base64
import binascii
import datetime
import gzip
import io
import json
import re
import zlib
from pathlib import Path
from django.conf import settings
from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_BODY = 2 * 1024 * 1024
AAD = b'shinsung-case-reading/v1/RSA-OAEP-SHA256/AES-256-GCM/gzip'
ALGORITHM = 'RSA-OAEP-SHA256+AES-256-GCM'


class ReadingUnavailable(Exception):
    def __init__(self, code='body_invalid'):
        self.code = code
        super().__init__(code)


def reading_path():
    return Path(settings.CASE_READING_ENCRYPTED_PATH)


def oaep():
    return padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=AAD)


def decode_field(value):
    if not isinstance(value, str):
        raise ValueError()
    return base64.b64decode(value, validate=True)


def validate_reading(raw):
    try:
        if len(raw) > MAX_BODY:
            raise ValueError()
        body = json.loads(raw)
        if body['version'] != 1 or body['reviewed'] is not True:
            raise ValueError()
        if not all(isinstance(body[n], str) for n in ('basis_on', 'source_title', 'source_filename')):
            raise ValueError()
        datetime.date.fromisoformat(body['basis_on'])
        entries = body['entries']
        if not entries or len(entries) > 500:
            raise ValueError()
        seen = set()
        aliases = set()
        for entry in entries:
            key = entry['key']
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', key) or key in seen:
                raise ValueError()
            seen.add(key)
            # Partial dates are preserved as labels; ordering metadata is not an occurrence date.
            order = entry['order']
            if order is not None and (len(order) != 3 or any(type(n) is not int for n in order)):
                raise ValueError()
            if order is not None and not (1 <= order[0] <= 9999 and 0 <= order[1] <= 12 and 0 <= order[2] <= 31):
                raise ValueError()
            for name in ('title', 'date_label', 'source', 'overview', 'ordering_note', 'issues', 'needed', 'responses'):
                if not isinstance(entry[name], str):
                    raise ValueError()
            for alias in entry.get('legacy_ids', []):
                if type(alias) is not int or alias <= 0 or alias in aliases:
                    raise ValueError()
                aliases.add(alias)
            for statement in entry['statements']:
                if statement['kind'] not in ('unknown', 'claim', 'opinion'):
                    raise ValueError()
                if statement['presentation'] not in ('summary', 'quotation', 'redacted_quotation'):
                    raise ValueError()
                if not all(isinstance(statement[n], str) for n in ('text', 'source')):
                    raise ValueError()
            for rule in entry['rules']:
                if not all(isinstance(rule[n], str) for n in ('citation', 'description', 'source', 'relevance')):
                    raise ValueError()
        body['dated_entries'] = sorted((e for e in entries if e['order'] is not None), key=lambda e: (*e['order'], e['key']))
        body['uncertain_entries'] = [e for e in entries if e['order'] is None]
        return body
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
        raise ReadingUnavailable('body_invalid') from None


def load_reading():
    # A public demonstration OTP must never unlock the real encrypted deployment body.
    if settings.APP_MODE != 'production' or settings.DEV:
        raise ReadingUnavailable('development_forbidden')
    path = reading_path()
    try:
        if path.stat().st_size > MAX_BODY:
            raise ValueError()
        envelope = json.loads(path.read_bytes())
        if envelope['version'] != 1 or envelope['algorithm'] != ALGORITHM:
            raise ValueError()
        wrapped = decode_field(envelope['wrapped_key'])
        nonce = decode_field(envelope['nonce'])
        ciphertext = decode_field(envelope['ciphertext'])
        if len(nonce) != 12 or len(ciphertext) < 16:
            raise ValueError()
    except FileNotFoundError:
        raise ReadingUnavailable('ciphertext_missing') from None
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise ReadingUnavailable('ciphertext_invalid') from None
    encoded_key = settings.CASE_READING_PRIVATE_KEY
    if not encoded_key:
        raise ReadingUnavailable('private_key_missing')
    try:
        if len(encoded_key) > 16384:
            raise ValueError()
        private = serialization.load_der_private_key(decode_field(encoded_key), password=None)
        if not isinstance(private, rsa.RSAPrivateKey) or not 3072 <= private.key_size <= 8192:
            raise ValueError()
    except (ValueError, TypeError, binascii.Error, UnsupportedAlgorithm):
        raise ReadingUnavailable('private_key_invalid') from None
    try:
        key = private.decrypt(wrapped, oaep())
        if len(key) != 32:
            raise ValueError()
        compressed = AESGCM(key).decrypt(nonce, ciphertext, AAD)
    except (ValueError, InvalidTag):
        raise ReadingUnavailable('decrypt_failed') from None
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(MAX_BODY + 1)
        return validate_reading(raw)
    except (OSError, EOFError, zlib.error):
        raise ReadingUnavailable('body_invalid') from None
