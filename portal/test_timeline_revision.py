"""Revision regressions use fictional records; never copy actual case text into fixtures."""
from django.test import TestCase,SimpleTestCase,TransactionTestCase,override_settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from .models import Member,Post,Request,CaseComment
from .testing import member_session
from .reading_registry import reading_entries
from .timeline_revision import KEY_BY_NUMBER,TIMELINE_ORDER,OLD_TO_REVISED
from .test_integrated_timeline import fictional_md
from scripts.prepare_integrated_timeline import parse_document,render


class RevisionInputTests(SimpleTestCase):
    def test_s01_sections_not_invented_pages_and_mapping_validation(self):
        source=fictional_md().replace('A11변경 PDF 1~2쪽','S01 2절 가상 표 3행',1)
        records,sources=parse_document(source)
        self.assertEqual(records[0]['source_refs'][0]['code'],'S01')
        self.assertIsNone(records[0]['source_refs'][0]['pages'])
        self.assertEqual(records[0]['source_refs'][0]['locator'],'2절 가상 표 3행')
        self.assertEqual(sources['S01']['filename'],'fictional.docx')
        text=render(records,'fictional-digest')
        self.assertTrue('2차 정리본 2절 가상 표 3행' in text)
        for bad in (source.replace('2절 가상 표 3행','DOCX 3쪽'),
                    source.replace('검토 기준일 2026년 11월 4일','검토 기준일 2026년 11월 2일'),
                    source.replace('| 41 | 42 | 유지 |','| 41 | 41 | 유지 |'),
                    source.replace('| 70 | 71 | 유지 |','| 70 | 72 | 유지 |')):
            with self.assertRaises(ValueError):parse_document(bad)
    def test_display_mapping_preserves_all_seventy_keys(self):
        self.assertEqual(len(set(TIMELINE_ORDER)),72)
        self.assertEqual(KEY_BY_NUMBER[41],'T71')
        self.assertEqual(KEY_BY_NUMBER[42],'T41')
        self.assertEqual(KEY_BY_NUMBER[71],'T70')
        self.assertEqual(KEY_BY_NUMBER[72],'T72')
        self.assertEqual({f'T{n:02}' for n in range(1,71)} & set(TIMELINE_ORDER),{f'T{n:02}' for n in range(1,71)})


@override_settings(SECURE_SSL_REDIRECT=False)
class RevisionConnectionTests(TestCase):
    def setUp(self):
        self.member=Member.objects.create(name='가상 개정 검증',phone='01000000000',synthetic=True)
        member_session(self.client,self.member)
    def test_shifted_number_keeps_same_url_comment_post_request_and_next_previous(self):
        old=CaseComment.objects.create(member=self.member,author_name=self.member.name,reading_key='T41',body='가상 기존 41 의견')
        post=Post.objects.create(member=self.member,author_name=self.member.name,title='가상 보존 글',body='가상',reading_key='T41')
        request=Request.objects.create(member=self.member,kind='correction',reading_key='T41',comment=old,body='가상 보존 요청')
        response=self.client.get('/cases/material/T41/');html=response.content.decode()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['entry']['number'],'42')
        self.assertTrue('가상 기존 41 의견' in html)
        self.assertFalse('가상 기존 41 의견' in self.client.get('/cases/material/T71/').content.decode())
        self.assertEqual(self.client.get('/cases/material/T71/').context['entry']['number'],'41')
        self.assertEqual(self.client.get('/cases/material/T40/').context['following']['key'],'T71')
        self.assertEqual(response.context['previous']['key'],'T71')
        self.assertEqual(self.client.get('/cases/material/T70/').context['following']['key'],'T72')
        self.assertRedirects(self.client.get(f'/comment-link/{old.pk}/'),f'/cases/material/T41/#comment-{old.pk}',fetch_redirect_response=False)
        self.assertEqual(Post.objects.get(pk=post.pk).reading_key,'T41')
        self.assertEqual(Request.objects.get(pk=request.pk).comment_id,old.pk)
        self.assertEqual(CaseComment.objects.get(pk=old.pk).reading_key,'T41')
        for key in ('T71','T72'):
            self.assertEqual(self.client.post(f'/comments/{key}/',{'body':'가상 신규 의견'}).status_code,302)
        self.assertEqual(CaseComment.objects.count(),3)
    def test_display_is_one_to_seventy_two_while_ids_are_not_renumbered(self):
        entries=reading_entries()
        self.assertEqual([entry['number'] for entry in entries],[f'{n:02}' for n in range(1,73)])
        self.assertEqual(tuple(entry['key'] for entry in entries),TIMELINE_ORDER)
        self.assertEqual(self.client.get('/').content.count(b'class="timeline-card"'),72)
        self.assertEqual(self.client.get('/cases/material/T73/').status_code,404)


class RevisionMigrationTests(TransactionTestCase):
    def test_existing_seventy_namespace_links_survive_new_two_key_constraint(self):
        before=('portal','0014_integrated_timeline_keys');after=('portal','0015_timeline_revision_20261104')
        executor=MigrationExecutor(connection);executor.migrate([before])
        try:
            apps=executor.loader.project_state([before]).apps
            member=apps.get_model('portal','Member').objects.create(name='가상 기존 회원',phone='01000000000',legacy_operator=True)
            comment=apps.get_model('portal','CaseComment').objects.create(member_id=member.pk,author_name=member.name,reading_key='T41',body='가상 의견 보존')
            post=apps.get_model('portal','Post').objects.create(member_id=member.pk,author_name=member.name,title='가상',body='가상',reading_key='T70')
            item=apps.get_model('portal','Request').objects.create(member_id=member.pk,kind='report',comment_id=comment.pk,reading_key='T41',body='가상')
        finally:
            MigrationExecutor(connection).migrate([after])
        self.assertEqual(CaseComment.objects.get(pk=comment.pk).reading_key,'T41')
        self.assertEqual(Post.objects.get(pk=post.pk).reading_key,'T70')
        self.assertEqual(Request.objects.get(pk=item.pk).comment_id,comment.pk)
        self.assertTrue(Member.objects.get(pk=member.pk).legacy_operator)
        for key in ('T71','T72'):
            CaseComment.objects.create(member_id=member.pk,author_name='가상',reading_key=key,body='가상 새 번호')
        self.assertEqual(CaseComment.objects.count(),3)
