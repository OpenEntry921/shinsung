"""Layout checks contain no confidential case text."""
from django.test import TestCase,override_settings
from .models import Member

@override_settings(APP_MODE='production',DEV=False,SECURE_SSL_REDIRECT=False)
class ReadingCleanupTests(TestCase):
    def test_login_body_without_sources_links_and_single_final_note(self):
        self.assertRedirects(self.client.get('/'),'/login/',fetch_redirect_response=False)
        Member.objects.create(name='가상교인',phone='01000000000',synthetic=False)
        response=self.client.post('/login/',{'name':'가상교인','phone':'01000000000'},follow=True)
        self.assertEqual(response.status_code,200)
        html=response.content.decode()
        self.assertFalse('출처:' in html)
        self.assertFalse('출처 문서는' in html)
        self.assertFalse('church_dispute_strategy_memo.docx' in html)
        self.assertFalse('이 사건 직접 링크' in html)
        self.assertEqual(html.count('class="case-group direct-case"'),30)
        self.assertEqual(html.count('class="reading-area"'),120)
        for i in range(1,31):self.assertTrue(f'id="material-E{i:02}"' in html)
        note='반론 자료를 별도로 확보하지 않았으며 상대방 입장을 추정하지 않습니다. 이후 상고 접수·확정·집행·진행 상황은 반영하지 않았습니다.'
        self.assertEqual(html.count(note),1)
        self.assertGreater(html.index(note),html.rindex('</article>'))
        self.assertLess(html.index(note),html.index('<footer>'))
        self.assertTrue('2026년 9월 19일 기준' in html)
        self.assertIn('no-store',response['Cache-Control'])
        self.assertRedirects(self.client.get('/cases/material/E30/'),'/#material-E30',fetch_redirect_response=False)
