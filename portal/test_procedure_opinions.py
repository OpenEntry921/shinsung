"""Fictional update fixtures only; no actual user opinion text copied into tests."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase,override_settings
from portal.opinion_updates import apply_opinion_updates
from portal.test_integrated_timeline import fictional_md
from scripts.prepare_integrated_timeline import parse_document,render,main
from portal.models import Member,CaseComment
from portal.testing import member_session

FAKE_UPDATES={
 'T08':{'id':'OP09','number':8,'related':(17,54),'title':'가상 비교 A','body':('가상 의견 <script>fake()</script>','가상 확인 한계')},
 'T17':{'id':'OP16','number':17,'related':(8,),'title':'가상 비교 B','body':('가상 반대 방향 설명',)},
}

class OpinionUpdateTests(SimpleTestCase):
    def test_idempotent_nonmutating_updates_and_stable_related_links(self):
        entries,_=parse_document(fictional_md());original=deepcopy(entries)
        revised=apply_opinion_updates(entries,FAKE_UPDATES)
        self.assertEqual(entries,original)
        self.assertEqual(revised,apply_opinion_updates(revised,FAKE_UPDATES))
        output=render(revised,'fictional')
        self.assertEqual(output.count('data-opinion="OP09"'),1)
        self.assertEqual(output.count('data-opinion="OP16"'),1)
        self.assertEqual(output.count('<h4>⑤ 우리의 의견</h4>'),2)
        self.assertIn('href="/cases/material/T17/">17번</a>',output)
        self.assertIn('href="/cases/material/T08/">08번</a>',output)
        self.assertIn('href="/cases/material/T53/">54번</a>',output)
        self.assertIn('&lt;script&gt;fake()&lt;/script&gt;',output)
        for old,new in zip(original,revised):
            for field in ('key','number','title','날짜','경과','관련 규정','쟁점','references','source_refs'):
                self.assertEqual(old[field],new[field])
    def test_collision_does_not_replace_another_events_opinion(self):
        entries,_=parse_document(fictional_md())
        entries[0]['supplements']=[{'heading':'우리의 의견 초안 OP16','paragraphs':['가상 기존 의견']}]
        old=deepcopy(entries)
        with self.assertRaises(ValueError):apply_opinion_updates(entries,FAKE_UPDATES)
        self.assertEqual(entries,old)
    def test_generator_reapplies_source_updates_on_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'fake.md';output=Path(directory)/'fake.html'
            source.write_text(fictional_md())
            with patch('portal.opinion_updates.PROCEDURE_OPINIONS',FAKE_UPDATES),patch('sys.argv',['prepare',str(source),'--output',str(output)]),redirect_stdout(StringIO()):
                main();first=output.read_bytes();main();second=output.read_bytes()
            self.assertEqual(first,second)
            self.assertIn(b'data-opinion="OP16"',first)

@override_settings(SECURE_SSL_REDIRECT=False)
class OpinionConnectionTests(TestCase):
    def test_mutual_links_and_existing_real_name_comments_are_preserved(self):
        self.assertEqual(self.client.get('/cases/material/T08/').status_code,302)
        member=Member.objects.create(name='가상 절차 검증',phone='01000000000',synthetic=True)
        comment=CaseComment.objects.create(member=member,author_name=member.name,reading_key='T17',body='가상 기존 성도 의견')
        member_session(self.client,member)
        for key,opinion,target in [('T08','OP09','T17'),('T17','OP16','T08')]:
            response=self.client.get(f'/cases/material/{key}/');body=response.content.decode()
            self.assertEqual(response.status_code,200)
            self.assertTrue(f'data-opinion="{opinion}"><h4>⑤ 우리의 의견</h4>' in body)
            self.assertTrue(f'href="/cases/material/{target}/"' in body)
            self.assertEqual(response.content.count(b'class="reading-area"'),4)
        self.assertEqual(CaseComment.objects.count(),1)
        self.assertEqual(CaseComment.objects.get(pk=comment.pk).reading_key,'T17')
        self.assertEqual(CaseComment.objects.get(pk=comment.pk).body,'가상 기존 성도 의견')
