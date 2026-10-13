"""Create ciphertext using a recipient PUBLIC key; never accept or print a private key."""
import argparse
import base64
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from portal.fixed_reading import AAD, ALGORITHM, MAX_BODY, oaep, validate_reading, ReadingUnavailable


def encrypt(raw, public):
    validate_reading(raw)
    if not isinstance(public, rsa.RSAPublicKey) or not 3072 <= public.key_size <= 8192:
        raise ValueError()
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    encode = lambda value: base64.b64encode(value).decode('ascii')
    return {'version': 1, 'algorithm': ALGORITHM,
            'wrapped_key': encode(public.encrypt(key, oaep())),
            'nonce': encode(nonce),
            'ciphertext': encode(AESGCM(key).encrypt(nonce, compressed, AAD))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--public-key-file', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        source = Path(args.source).resolve()
        root = Path(__file__).resolve().parents[1]
        if root == source or root in source.parents or source.stat().st_size > MAX_BODY:
            raise ValueError()
        raw = source.read_bytes()
        public = serialization.load_der_public_key(Path(args.public_key_file).read_bytes())
        payload = json.dumps(encrypt(raw, public), separators=(',', ':')).encode('ascii')
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents accidental replacement of the previous approved deployment.
        with output.open('xb') as stream:
            stream.write(payload)
        print(json.dumps({'encrypted': True, 'ciphertext_bytes': len(payload),
                          'ciphertext_sha256': hashlib.sha256(payload).hexdigest()}))
    except (OSError, ValueError, ReadingUnavailable):
        print('Encryption failed: check private source, public key, and output. No content is printed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
