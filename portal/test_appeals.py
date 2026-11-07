"""The new claim namespace must preserve old preparation events and comments."""
import hashlib
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .appeals import appeal_data, presented, ROOT
from .models import AppealComment, AppealReview, PreparationComment, PreparationReview, Member, CaseComment
from .preparation import SESSION_KEY, preparation_data
from .testing import member_session


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False)
class AppealTests(TestCase):
    def login(self, client=None):
        return (client or self.client).post('/prepare/', {'name':'준비위원','phone':'01011111111'})

    def test_catalog_source_order_original_headings_and_references(self):
        data=appeal_data();rows=data['entries']
        self.assertEqual(len(rows),46)
        self.assertEqual([g['id'] for g in data['groups']],['I','II','III','IV','V','VI','VII','VIII','IX','X'])
        self.assertEqual([r['order'] for r in rows],list(range(1,47)))
        self.assertEqual(len({r['id'] for r in rows}),46)
        source_numbers={g:set() for g in ('I','II','III','IV','V','VI','VII','VIII','IX','X')}
        for row in rows:
            source_numbers[row['group']].add(row['original_number'].split()[0])
            self.assertEqual(row['printed_pages'],[p-2 for p in row['pdf_pages']])
            self.assertTrue(all(row[k] for k in ('quote','summary','evidence','draft','questions')))
            self.assertNotIn(row['id'], {r['key'] for r in preparation_data()['entries']})
            for page,url in presented(row)['source_links']:
                self.assertEqual(url,f'/prepare/documents/appeal-body/#page={page-3}')
        for g,n in [('I',3),('III',9),('IV',4),('V',3),('VI',2),('VII',3),('VIII',3),('IX',4),('X',2)]:
            self.assertEqual(source_numbers[g],{str(i) for i in range(1,n+1)})
        # Actual stable keys, not event display numbers.
        construction=next(r for r in rows if r['id']=='AP26-construction-orders')
        self.assertEqual(construction['related_keys'],['T03'])
        raw=(ROOT/'appeal_claims.json').read_text()
        import re
        self.assertIsNone(re.search(r'01[016789][- ]?\d{3,4}[- ]?\d{4}',raw))

    def test_landing_search_status_and_legacy_links(self):
        self.login()
        response=self.client.get('/prepare/')
        self.assertContains(response,'상고 주장별 반박 준비표')
        self.assertEqual(len(response.context['rows']),46)
        self.assertContains(response,'/prepare/events/')
        self.assertEqual(len(self.client.get('/prepare/events/').context['rows']),72)
        self.assertEqual(len(self.client.get('/prepare/?q=AP26-construction-orders').context['rows']),1)
        self.assertTrue(self.client.get('/prepare/?q=T03').context['rows'])
        self.assertTrue(self.client.get('/prepare/?q=03').context['rows'])
        self.assertContains(self.client.get('/prepare/?q=NO-SUCH-CLAIM'),'검색 조건에 맞는 상고 항목이 없습니다.')
        item=AppealReview.objects.create(claim_id='AP26-construction-orders',status='reviewing',revised_draft='<b>가상 검토 초안</b>',evidence_notes='가상 확보 기록')
        result=self.client.get('/prepare/?status=reviewing')
        self.assertEqual([r['id'] for r in result.context['rows']],[item.claim_id])
        self.assertContains(result,'&lt;b&gt;가상 검토 초안&lt;/b&gt;')
        self.assertContains(self.client.get('/prepare/claims/'+item.claim_id+'/'),'가상 확보 기록')

    def test_comment_namespace_validation_escape_and_persistence(self):
        self.login()
        old=PreparationComment.objects.create(reading_key='T18',author_name='가상 이전 작성자',kind='other',body='가상 기존 사건 의견')
        payload={'author_name':'가상 직접 기재','kind':'argument','source_reference':'가상 자료1쪽','body':'<script>fiction()</script> 가상 새 주장 의견'}
        key='AP26-speech-motive'
        result=self.client.post(f'/prepare/claims/{key}/comments/',payload)
        comment=AppealComment.objects.get()
        self.assertEqual(result.status_code,302)
        self.assertIn(f'#appeal-comment-{comment.pk}',result.url)
        self.assertContains(self.client.get(f'/prepare/claims/{key}/'),'&lt;script&gt;fiction()&lt;/script&gt;')
        self.assertNotContains(self.client.get(f'/prepare/claims/{key}/'),'가상 기존 사건 의견')
        self.assertNotContains(self.client.get('/prepare/claims/AP26-scope-quash/'),'가상 새 주장 의견')
        self.assertContains(self.client.get('/prepare/events/T18/'),'가상 기존 사건 의견')
        self.assertEqual(PreparationComment.objects.get().pk,old.pk)
        self.assertEqual(CaseComment.objects.count(),0)
        self.client.post('/prepare/logout/');self.login()
        self.assertContains(self.client.get(f'/prepare/claims/{key}/'),'가상 새 주장 의견')
        comment.hidden=True;comment.save()
        self.assertNotContains(self.client.get(f'/prepare/claims/{key}/'),'가상 새 주장 의견')
        self.assertEqual(self.client.post('/prepare/claims/T18/comments/',payload).status_code,404)
        with self.assertRaises(ValidationError):
            AppealReview(claim_id='T18').full_clean()
        payload['author_name']=' '
        self.assertEqual(self.client.post(f'/prepare/claims/{key}/comments/',payload).status_code,400)

    def test_authentication_separation_documents_and_expiry(self):
        key='AP26-scope-quash'
        for url in ['/prepare/claims/'+key+'/', '/prepare/documents/appeal-body/', '/prepare/documents/judgment/', '/prepare/events/']:
            self.assertRedirects(self.client.get(url),'/prepare/',fetch_redirect_response=False)
        member=Member.objects.create(name='가상 일반 교인',phone='01000000000',synthetic=True)
        member_session(self.client,member)
        self.assertRedirects(self.client.get('/prepare/documents/appeal-body/'),'/prepare/',fetch_redirect_response=False)
        self.login()
        for code in ('appeal-body','judgment'):
            r=self.client.get('/prepare/documents/'+code+'/')
            self.assertEqual(r.status_code,200)
            self.assertEqual(r['Content-Type'],'application/pdf')
            self.assertIn('no-store',r['Cache-Control']);self.assertIn('noindex',r['X-Robots-Tag'])
            body=b''.join(r.streaming_content);self.assertTrue(body.startswith(b'%PDF-'))
            if code=='appeal-body':self.assertEqual(hashlib.sha256(body).hexdigest(),appeal_data()['reading_copy']['sha256'])
        self.assertEqual(self.client.get('/prepare/documents/unknown/').status_code,404)
        self.assertNotContains(self.client.get('/prepare/'),'private_documents/')
        self.assertEqual(self.client.get('/prepare/claims/T18/').status_code,404)
        session=self.client.session;session[SESSION_KEY]=timezone.now().timestamp()-1;session.save()
        self.assertRedirects(self.client.get('/prepare/documents/appeal-body/'),'/prepare/',fetch_redirect_response=False)

    def test_csrf_methods_and_throttling(self):
        c=Client(enforce_csrf_checks=True);c.get('/prepare/');token=c.cookies['csrftoken'].value
        c.post('/prepare/',{'name':'준비위원','phone':'01011111111','csrfmiddlewaretoken':token})
        url='/prepare/claims/AP26-scope-quash/comments/'
        self.assertEqual(c.post(url,{'body':'가상'}).status_code,403)
        self.assertEqual(c.get(url).status_code,405)
        self.assertEqual(c.post('/prepare/documents/appeal-body/').status_code,403)
        self.login()
        with patch('portal.appeals.limit',return_value=False):
            self.assertEqual(self.client.post(url,{'author_name':'가상','kind':'other','body':'가상'}).status_code,429)
        self.assertEqual(AppealComment.objects.count(),0)

    def test_private_source_not_collected_static_and_bad_digest_fails_closed(self):
        from django.contrib.staticfiles import finders
        self.assertIsNone(finders.find('appeal-body.redacted.pdf'))
        self.assertIsNone(finders.find('private_documents/appeal-body.redacted.pdf'))
        self.login()
        data=dict(appeal_data());data['reading_copy']={'sha256':'0'*64}
        with patch('portal.appeals.appeal_data',return_value=data):
            self.assertEqual(self.client.get('/prepare/documents/appeal-body/').status_code,404)
        self.assertEqual(self.client.get('/static/private_documents/appeal-body.redacted.pdf').status_code,404)


class AppealMigrationPreservationTests(TransactionTestCase):
    def test_additive_migration_preserves_old_comments_review_and_member(self):
        old_target=[('portal','0017_preparationcomment_preparationreview')]
        executor=MigrationExecutor(connection);latest=executor.loader.graph.leaf_nodes('portal')
        try:
            executor.migrate(old_target);apps=executor.loader.project_state(old_target).apps
            comment=apps.get_model('portal','PreparationComment').objects.create(reading_key='T18',author_name='가상 작성',kind='other',body='가상 보존 의견')
            apps.get_model('portal','PreparationReview').objects.create(reading_key='T18',status='reviewing',revised_draft='가상 기존 초안')
            member=apps.get_model('portal','Member').objects.create(name='가상 이전 교인',phone='01000000000',synthetic=True)
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(PreparationComment.objects.get(pk=comment.pk).body,'가상 보존 의견')
            self.assertEqual(PreparationReview.objects.get(reading_key='T18').revised_draft,'가상 기존 초안')
            self.assertTrue(Member.objects.filter(pk=member.pk).exists())
            self.assertEqual(AppealComment.objects.count(),0);self.assertEqual(AppealReview.objects.count(),0)
        finally:
            MigrationExecutor(connection).migrate(latest)
