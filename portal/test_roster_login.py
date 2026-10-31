"""Credential-only paths never grant access, in either mode."""
from django.test import TestCase, override_settings
from .models import Member,AccessApplication
from .testing import member_session, approve

@override_settings(SECURE_SSL_REDIRECT=False)
class RosterLoginTests(TestCase):
    def test_name_phone_and_legacy_sessions_cannot_read_any_private_route(self):
        member=Member.objects.create(name='가상 교인',phone='01000000000',synthetic=True)
        for development in (True, False):
            with override_settings(DEV=development):
                self.client.post('/login/',{'name':member.name,'phone':member.phone})
                self.assertNotIn('member_id',self.client.session)
                session=self.client.session
                session.update(dict(member_id=str(member.pk),member_version=member.session_version,member_auth='roster'))
                session.save()
                for path in ('/','/cases/material/E01/','/posts/','/requests/','/comments/E01/'):
                    self.assertEqual(self.client.get(path).status_code,302)
                self.assertEqual(self.client.get('/documents/1/reading/').status_code,403)

    def test_approval_consent_and_verification_each_required_and_revocation_flushes_session(self):
        member=Member.objects.create(name='가상 교인',phone='01000000000',synthetic=True)
        application=approve(member)
        for field, value in [('approved',False),('privacy_consent_at',None),('religious_consent_at',None),('transfer_consent_at',None),('roster_checked_at',None),('identity_checked_at',None),('identity_evidence',''),('consent_version','old')]:
            member_session(self.client,member)
            old=getattr(application,field)
            type(application).objects.filter(pk=application.pk).update(**{field:value})
            self.assertEqual(self.client.get('/').status_code,302,field)
            self.assertNotIn('member_id',self.client.session)
            type(application).objects.filter(pk=application.pk).update(**{field:old})
        member_session(self.client,member)
        application.refresh_from_db()
        from .access import member_approved
        self.assertTrue(member_approved(member), repr(list(AccessApplication.objects.values('approved','consent_version','identity_evidence'))))
        self.assertEqual(self.client.get('/').status_code,200, dict(self.client.session))
        from django.utils import timezone
        type(application).objects.filter(pk=application.pk).update(revoked_at=timezone.now())
        self.assertEqual(self.client.get('/cases/material/E01/').status_code,302)
