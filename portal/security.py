import hashlib, hmac, secrets, datetime, base64, struct, time, re
import requests
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .models import RateBucket

def phone(value): return re.sub(r'[\s-]', '', str(value).strip())
def keyed(value): return hmac.new(settings.SECRET_KEY.encode(),value.encode(),hashlib.sha256).hexdigest()
def digest(cid, code): return keyed(f'{settings.APP_MODE}:{cid}:{code}')
def limit(key, maximum, seconds):
    with transaction.atomic():
        bucket,_ = RateBucket.objects.select_for_update().get_or_create(key=keyed(key))
        if bucket.start + datetime.timedelta(seconds=seconds) <= timezone.now():
            bucket.start=timezone.now(); bucket.count=0
        if bucket.count >= maximum: return False
        bucket.count += 1; bucket.save(); return True

def send_sms(member, code):
    if settings.DEV:
        if not member.synthetic: return False
        # Synthetic-only development delivery; never exposed in production.
        return True
    if not all((settings.SMS_API_KEY,settings.SMS_API_SECRET,settings.SMS_SENDER)): return False
    date=timezone.now().isoformat(); salt=secrets.token_hex(16)
    signature=hmac.new(settings.SMS_API_SECRET.encode(),(date+salt).encode(),hashlib.sha256).hexdigest()
    try:
        r=requests.post('https://api.solapi.com/messages/v4/send',headers={'Authorization':f'HMAC-SHA256 apiKey={settings.SMS_API_KEY}, date={date}, salt={salt}, signature={signature}'},json={'message':{'to':member.phone,'from':settings.SMS_SENDER,'text':f'[교인 전용 안내] 인증번호 {code} (5분 이내). 타인에게 전달하지 마세요.'}},timeout=10)
        return r.status_code in (200,201)
    except requests.RequestException: return False

def valid_totp(code, username):
    secret=settings.ADMIN_MFA_SECRETS.get(username,'')
    if not secret or not re.fullmatch(r'\d{6}',code): return False
    try: key=base64.b32decode(secret.upper(),casefold=True)
    except Exception: return False
    for offset in (-1,0,1):
        counter=int(time.time()/30)+offset
        raw=hmac.new(key,struct.pack('>Q',counter),hashlib.sha1).digest(); i=raw[-1]&15
        expected=f'{(struct.unpack(">I",raw[i:i+4])[0]&0x7fffffff)%1000000:06d}'
        if hmac.compare_digest(expected,code): return counter
    return False
