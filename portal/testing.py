"""Fictional approval fixtures for tests; never used by runtime or startup."""
from django.utils import timezone
from .models import AccessApplication
from .access import POLICY_VERSION


def approve(member):
    return AccessApplication.objects.get_or_create(member=member, defaults=dict(
        name='가상 신청자', phone='01000000000', consent_version=POLICY_VERSION,
        privacy_consent_at=timezone.now(), religious_consent_at=timezone.now(), transfer_consent_at=timezone.now(),
        policy_snapshot={'fixture':'synthetic-only'}, roster_checked_at=timezone.now(), roster_evidence='가상 대조 기록',
        identity_checked_at=timezone.now(), identity_evidence='가상 별도 대면 확인 기록', approved=True))[0]


def member_session(client, member):
    approve(member)
    session=client.session
    session.update(dict(member_id=str(member.pk), member_version=member.session_version, member_auth='exception',
        identity_member=str(member.pk), identity_version=member.session_version, identity_until=timezone.now().timestamp()+3600))
    session.save()
    from django.conf import settings
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
