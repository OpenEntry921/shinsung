"""Fail closed on each request, including old sessions and revoked consent."""
from django.conf import settings
from django.utils import timezone
from .models import AccessApplication

POLICY_VERSION = '2026-11-01-v1'
POLICY_FIELDS = ('OPERATOR_NAME', 'OPERATOR_CONTACT', 'APPLICATION_RETENTION', 'CHURCH_RECIPIENT', 'CHURCH_CONTACT', 'CHURCH_RETENTION')


def policy_config():
    return {name: getattr(settings, name, '') for name in POLICY_FIELDS}


def registration_ready():
    return all(policy_config().values())


def member_approved(member):
    if not member or not member.active: return False
    return AccessApplication.objects.filter(member=member, approved=True, revoked_at=None,
        consent_version=POLICY_VERSION, privacy_consent_at__isnull=False,
        religious_consent_at__isnull=False, transfer_consent_at__isnull=False,
        roster_checked_at__isnull=False, identity_checked_at__isnull=False).exclude(
        roster_evidence='').exclude(identity_evidence='').exclude(policy_snapshot={}).exists()


def access_valid(request):
    member = request.member
    if member and member.active and member.legacy_operator and request.session.get('member_auth') == 'roster':
        return True
    return bool(member_approved(member) and request.session.get('member_auth') == 'exception'
        and request.session.get('identity_member') == str(member.pk)
        and request.session.get('identity_version') == member.session_version
        and request.session.get('identity_until', 0) > timezone.now().timestamp())
