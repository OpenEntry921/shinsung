"""Generated fixtures use fictional bytes; the existing C02 connection is checked separately."""
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase,override_settings
from django.template import Context,Template
from portal.public_case_documents import APPROVED,catalog,page_targets,public_links
from portal.models import Member,CaseComment
from portal.testing import member_session

class PublicCopyTests(SimpleTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);(self.base/'data').mkdir();(self.base/'static/case-documents').mkdir(parents=True)
        self.rows=[]
        for code,file in APPROVED.items():
            data=b'\xff\xd8\xfffictional' if code=='C02' else b'%PDF-fictional'
            (self.base/'static/case-documents'/file).write_bytes(data)
            self.rows.append(dict(id=code,title='Fictional '+code,file='static/case-documents/'+file,url='/static/case-documents/'+file,
                                  pages=1 if code=='C02' else (21 if code=='E01' else 18),bytes=len(data),status='redacted_copy'))
        self.save()
    def save(self):
        (self.base/'data/case_documents.json').write_text(json.dumps({'documents':self.rows}))
    def test_exact_ids_metadata_missing_size_signature_path_and_duplicate(self):
        documents,errors=catalog(self.base);self.assertEqual(len(documents),28);self.assertEqual(errors,[])
        self.assertEqual(documents['A11변경']['logical'],'case-documents/A11-change.pdf')
        (self.base/'static/case-documents/A01.pdf').unlink()
        documents,errors=catalog(self.base);self.assertNotIn('A01',documents);self.assertEqual(len(documents),27)
        self.rows[0]['file']='static/case-documents/../private.pdf';self.save()
        self.assertNotIn(self.rows[0]['id'],catalog(self.base)[0])
        self.rows[0]['id']=self.rows[1]['id'];self.save();self.assertEqual(catalog(self.base)[0],{})
    def test_pages_manifest_url_and_image_do_not_use_json_url(self):
        self.assertEqual(page_targets('2~4·7쪽',18),[2,7])
        self.assertEqual(page_targets('1~18쪽 특히 11·13쪽',18),[1,11,13])
        for invalid in ('0쪽','19쪽','5~2쪽','-1쪽','abc2쪽','1.5쪽'):
            with self.assertRaises(ValueError):page_targets(invalid,18)
        with override_settings(BASE_DIR=self.base),patch('portal.public_case_documents.staticfiles_storage.url',return_value='/assets/hashed.pdf'):
            links=public_links('A05','2·7쪽')['public_links']
            self.assertEqual([x['url'] for x in links],['/assets/hashed.pdf#page=2','/assets/hashed.pdf#page=7'])
            self.assertEqual(public_links('C02','1장')['public_links'][0]['url'],'/assets/hashed.pdf')
            self.assertTrue(public_links('S01')['public_missing'])
            self.assertTrue(public_links('A05','99쪽')['public_unavailable'])
            html=Template("{% load timeline_tags %}{% timeline_document 'A05' '2·7쪽' %}").render(Context({}))
            self.assertEqual(html.count('target="_blank"'),2)
            self.assertIn('noopener noreferrer',html)
            self.assertNotIn('원문 연결이 준비되지',html)
    def test_existing_source_locator_metadata_is_complete_and_stable(self):
        from portal.reading_registry import reading_entries
        entries=reading_entries()
        self.assertEqual(len(entries),72)
        for entry in entries:
            self.assertEqual(set(entry['sources']),set(entry['source_locators']))
        self.assertEqual(entries[0]['source_locators']['A01'],'2·7쪽')
        self.assertEqual(sum(len(e['source_references']) for e in entries),156)
        self.assertEqual(sum(r['code']=='S01' for e in entries for r in e['source_references']),16)

    def test_repeated_same_document_uses_each_original_locator(self):
        entry={'key':'T28','source_references':[{'code':'A06','locator':'4쪽'},{'code':'A06','locator':'43쪽'}]}
        with patch('portal.public_case_documents.public_links',return_value={'public_unavailable':True}) as resolver:
            Template("{% load timeline_tags %}{% timeline_document 'A06' %}{% timeline_document 'A06' %}").render(Context({'entry':entry}))
            self.assertEqual([call.args for call in resolver.call_args_list],[('A06','4쪽'),('A06','43쪽')])

    def test_private_document_fallback_is_not_bypassed(self):
        with patch('portal.public_case_documents.public_links',return_value={'public_unavailable':True}):
            html=Template("{% load timeline_tags %}{% timeline_document 'A01' '1쪽' %}").render(Context({'document_links':{'A01':type('Doc',(),{'pk':123})()}}))
            self.assertIn('/documents/123/reading/',html)

@override_settings(SECURE_SSL_REDIRECT=False)
class ProtectedTimelineRegressionTests(TestCase):
    def test_missing_public_files_do_not_break_protected_drafts_or_create_rows(self):
        self.assertEqual(self.client.get('/cases/material/T05/').status_code,302)
        member=Member.objects.create(name='가상 문서 검증',phone='01000000000',synthetic=True)
        member_session(self.client,member)
        response=self.client.get('/cases/material/T05/')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'data-opinion="OP15"',response.content)
        self.assertEqual(response.content.count(b'class="reading-area"'),4)
        self.assertEqual(CaseComment.objects.count(),0)


@override_settings(SECURE_SSL_REDIRECT=False)
class C02ConnectionTests(TestCase):
    def test_existing_c02_reference_uses_manifest_image_once_without_pdf_fragment(self):
        from django.contrib.staticfiles.storage import staticfiles_storage
        from portal.reading_registry import reading_entries
        entry=next(e for e in reading_entries() if e['key']=='T57')
        self.assertEqual(entry['number'],'58')
        self.assertEqual(entry['sources'],['C02'])
        self.assertEqual(entry['source_locators']['C02'],'1쪽')
        self.assertEqual(self.client.get('/cases/material/T57/').status_code,302)
        member=Member.objects.create(name='가상 이미지 연결',phone='01000000000',synthetic=True)
        member_session(self.client,member)
        response=self.client.get('/cases/material/T57/')
        self.assertEqual(response.status_code,200)
        url=staticfiles_storage.url('case-documents/C02.jpg')
        self.assertEqual(response.content.count(('href="'+url+'"').encode()),1)
        self.assertNotIn((url+'#page=').encode(),response.content)
        self.assertIn('원문 보기(개인정보 가림)'.encode(),response.content)
        self.assertNotIn('개인정보 가림 사본 연결 확인 필요'.encode(),response.content)
        self.assertEqual(response.content.count(b'class="reading-area"'),4)
        self.assertIn(b'rel="noopener noreferrer"',response.content)
        self.assertEqual(CaseComment.objects.count(),0)
