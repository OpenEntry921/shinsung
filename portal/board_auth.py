"""SMS authentication scoped to the members' question board."""

import re
import secrets
from datetime import timedelta
from hmac import compare_digest
from uuid import UUID

from django.conf import settings
from django.db import OperationalError
from django.db.models import F
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .access import member_approved, registration_ready
from .models import Challenge, Member
from .security import digest, keyed, limit, phone, send_sms

BROWSER_KEY = 'board_browser'
SESSION_KEY = 'board_identity'
CODE_TTL = timedelta(minutes=5)
SESSION_TTL = timedelta(hours=8)
MAX_ATTEMPTS = 5
VERIFY_ERROR = '인증번호를 확인할 수 없습니다. 다시 입력하거나 새 번호를 요청해 주세요.'


def eligible(member):
    return bool(member and member.synthetic == settings.DEV and member_approved(member)
                and Member.objects.filter(active=True, phone=member.phone).count() == 1)


def configured():
    return registration_ready() and (settings.DEV or all((
        settings.SMS_API_KEY, settings.SMS_API_SECRET, settings.SMS_SENDER,
    )))


def board_member(request):
    identity = request.session.get(SESSION_KEY)
    if not identity:
        return None
    member_id, version, expires = identity
    if expires > timezone.now().timestamp():
        member = Member.objects.filter(pk=UUID(member_id), active=True, session_version=version).first()
        if eligible(member):
            return member
    request.session.pop(SESSION_KEY, None)
    return None


def clear_board_session(request):
    request.session.pop(SESSION_KEY, None)
    browser = request.session.pop(BROWSER_KEY, None)
    if browser:
        Challenge.objects.filter(board_browser=browser).delete()


def issue(request, browser):
    name = request.POST.get('name', '').strip()
    number = phone(request.POST.get('phone', ''))
    if not (0 < len(name) <= 80 and re.fullmatch(r'010[0-9]{8}', number)):
        return
    ip = request.META.get('REMOTE_ADDR', '')
    try:
        if not (limit(f'board-sms-ip:{ip}', 30, 3600)
                and limit(f'board-sms-browser:{browser}', 1, 60)
                and limit(f'board-sms-number:{number}', 1, 60)
                and limit(f'board-sms-hour:{number}', 5, 3600)):
            return
        # Invalidate the previous code before looking up or sending a replacement.
        previous = Challenge.objects.filter(board_browser=browser)
        previous.update(used=True)
        if not configured():
            return
        member = Member.objects.filter(name=name, phone=number, active=True).first()
        if not eligible(member):
            return
        code = f'{secrets.randbelow(1_000_000):06d}'
        proof = digest(browser, code)
        if previous.filter(digest=proof).exists():
            code = f'{(int(code) + 1) % 1_000_000:06d}'
            proof = digest(browser, code)
        challenge, _ = Challenge.objects.update_or_create(board_browser=browser, defaults=dict(
            member=member, version=member.session_version, digest=proof,
            expires_at=timezone.now() + CODE_TTL, attempts=0, used=True,
        ))
        if send_sms(member, code):
            Challenge.objects.filter(pk=challenge.pk, digest=proof).update(used=False)
    except OperationalError:
        # SQLite can reject concurrent writes. Leave the request unauthenticated.
        return


@require_http_methods(['GET', 'HEAD', 'POST'])
def login(request):
    if request.member or board_member(request):
        return redirect('posts')
    if request.method == 'POST':
        browser = request.session.get(BROWSER_KEY)
        if browser and request.POST.get('acknowledged') == 'yes':
            issue(request, browser)
            return redirect('board_verify')
        return render(request, 'portal/board_login.html', {'error': '안내를 확인한 뒤 다시 요청해 주세요.'}, status=400)
    if not request.session.get(BROWSER_KEY):
        request.session[BROWSER_KEY] = keyed(secrets.token_hex(32))
    return render(request, 'portal/board_login.html')


def consume(browser, code):
    if not browser or not re.fullmatch(r'[0-9]{6}', code):
        return None
    pending = Challenge.objects.filter(
        board_browser=browser, used=False, expires_at__gt=timezone.now(), attempts__lt=MAX_ATTEMPTS,
    )
    challenge = pending.select_related('member').first()
    if not challenge:
        return None
    member = challenge.member
    matched = (compare_digest(challenge.digest, digest(browser, code))
               and eligible(member) and challenge.version == member.session_version)
    changes = {'attempts': F('attempts') + 1}
    if matched:
        changes['used'] = True
    # The conditional write prevents a replay and rejects a replaced challenge.
    updated = pending.filter(
        pk=challenge.pk, digest=challenge.digest, expires_at=challenge.expires_at,
        attempts=challenge.attempts, expires_at__gt=timezone.now(),
    ).update(**changes)
    return member if matched and updated == 1 else None


@require_http_methods(['GET', 'HEAD', 'POST'])
def verify(request):
    if request.member or board_member(request):
        return redirect('posts')
    if request.method == 'POST':
        try:
            member = consume(request.session.get(BROWSER_KEY), request.POST.get('code', '').strip())
        except OperationalError:
            member = None
        if member:
            request.session.cycle_key()
            request.session.pop(BROWSER_KEY, None)
            request.session[SESSION_KEY] = [
                str(member.pk), member.session_version, (timezone.now() + SESSION_TTL).timestamp(),
            ]
            return redirect('posts')
        return render(request, 'portal/board_verify.html', {'error': VERIFY_ERROR}, status=400)
    return render(request, 'portal/board_verify.html')
