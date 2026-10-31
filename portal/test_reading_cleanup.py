"""Preserve every original article and common caveat without copying case text."""
import re
from pathlib import Path
from django.test import TestCase,override_settings
from .models import Member
from .testing import member_session

@override_settings(SECURE_SSL_REDIRECT=False)
class ReadingCleanupTests(TestCase):
    def test_each_detail_has_one_article_common_basis_and_final_note(self):
        member=Member.objects.create(name='가상교인',phone='01000000000',synthetic=True)
        member_session(self.client,member)
        for i in range(1,31):
            response=self.client.get(f'/cases/material/E{i:02}/');html=response.content.decode()
            self.assertEqual(response.status_code,200)
            self.assertEqual(html.count('class="case-group direct-case"'),1)
            self.assertEqual(html.count('class="reading-area"'),4)
            self.assertEqual(re.findall(r'id="material-(E\d+)"',html),[f'E{i:02}'])
            self.assertIn('2026년 9월 19일 기준',html)
            self.assertIn('이후 상고 접수·확정·집행·진행 상황은 반영하지 않았습니다.',html)
            self.assertNotIn('church_dispute_strategy_memo.docx',html)
            self.assertIn('no-store',response['Cache-Control'])
