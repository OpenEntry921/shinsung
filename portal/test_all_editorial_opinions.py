"""Regression metadata and fictional records only; opinions remain in their canonical source."""
from copy import deepcopy
from django.test import SimpleTestCase,TestCase,override_settings
from portal.opinion_updates import PROCEDURE_OPINIONS,apply_opinion_updates
from portal.timeline_revision import KEY_BY_NUMBER
from portal.reading_registry import reading_entries
from portal.test_integrated_timeline import fictional_md
from scripts.prepare_integrated_timeline import parse_document
from portal.models import Member,CaseComment
from portal.testing import member_session

EXISTING_IDS={'T05':'OP15','T08':'OP09','T15':'OP07','T17':'OP16','T27':'OP13','T33':'OP10',
              'T35':'OP06','T40':'OP08','T45':'OP04','T57':'OP01','T58':'OP02','T59':'OP05',
              'T60':'OP11','T62':'OP12','T67':'OP03','T70':'OP14'}

class EditorialSourceTests(SimpleTestCase):
    def test_complete_unique_identity_mapping_and_existing_sixteen_ids(self):
        self.assertEqual(len(PROCEDURE_OPINIONS),72)
        self.assertEqual(set(PROCEDURE_OPINIONS),set(KEY_BY_NUMBER.values()))
        self.assertEqual({u['id'] for u in PROCEDURE_OPINIONS.values()},{f'OP{n:02}' for n in range(1,73)})
        for key,opinion in EXISTING_IDS.items():self.assertEqual(PROCEDURE_OPINIONS[key]['id'],opinion)
        for key,opinion in PROCEDURE_OPINIONS.items():
            self.assertEqual(KEY_BY_NUMBER[opinion['number']],key)
            self.assertTrue(bool(opinion['title']) and bool(opinion['body']))
            self.assertEqual(len(set(opinion['related'])),len(opinion['related']))
            for n in opinion['related']:self.assertIn(n,KEY_BY_NUMBER)
    def test_bad_key_number_related_and_template_payload_fail_closed(self):
        entries,_=parse_document(fictional_md())
        fake={'T08':{'id':'OP09','number':8,'related':(17,),'title':'가상','body':('가상 의견',)}}
        for change in ({'number':41},{'related':(73,)},{'body':('{{ fake }}',)}):
            bad=deepcopy(fake);bad['T08'].update(change)
            with self.assertRaises(ValueError):apply_opinion_updates(entries,bad)

@override_settings(SECURE_SSL_REDIRECT=False)
class EveryOpinionPageTests(TestCase):
    def test_one_editorial_per_event_without_inserting_or_moving_reader_comments(self):
        self.assertEqual(self.client.get('/cases/material/T01/').status_code,302)
        member=Member.objects.create(name='가상 전체 의견 검증',phone='01000000000',synthetic=True)
        old=CaseComment.objects.create(member=member,author_name=member.name,reading_key='T08',body='가상 기존 성도 의견')
        member_session(self.client,member)
        for entry in reading_entries():
            opinion=PROCEDURE_OPINIONS[entry['key']]
            response=self.client.get('/cases/material/'+entry['key']+'/');body=response.content.decode()
            self.assertEqual(response.status_code,200)
            self.assertEqual(body.count('data-opinion='),1)
            self.assertEqual(body.count('<h4>⑤ 우리의 의견</h4>'),1)
            self.assertTrue('data-opinion="'+opinion['id']+'"' in body)
            self.assertEqual(body.count('class="reading-area"'),4)
            self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(CaseComment.objects.count(),1)
        self.assertEqual(CaseComment.objects.get(pk=old.pk).reading_key,'T08')
        self.assertEqual(CaseComment.objects.get(pk=old.pk).body,'가상 기존 성도 의견')
