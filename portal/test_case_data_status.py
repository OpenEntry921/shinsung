import io
import json
from unittest.mock import patch
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from .models import Case

@override_settings(APP_MODE='development', DEV=True)
class CaseDataStatusTests(TestCase):
    def report(self):
        out=io.StringIO();call_command('case_data_status',stdout=out)
        return json.loads(out.getvalue())
    def test_empty_database_counts(self):
        report=self.report()
        self.assertEqual(report['counts']['cases'],0)
        self.assertEqual(report['unfiltered_visible_cases'],0)
        self.assertFalse(report['storage_persistence_verified'])
    def test_counts_without_content_or_mutation(self):
        author=User.objects.create(username='fictitious-status-editor')
        for state in ('draft','review','published'):
            Case.objects.create(title='가상 비공개 제목',overview='가상 비공개 내용',state=state,author=author)
        report=self.report()
        self.assertEqual(report['case_states'],{'draft':1,'review':1,'published':1})
        self.assertEqual(report['unfiltered_visible_cases'],1)
        self.assertNotIn('가상 비공개',json.dumps(report,ensure_ascii=False))
        self.assertEqual(self.report(),report)
        self.assertEqual(Case.objects.count(),3)
    def test_pre_migration_schema_report(self):
        with patch('django.db.connection.introspection.table_names',return_value=[]):
            report=self.report()
        self.assertEqual(report['counts']['cases'],None)
        self.assertIn('imports',report['missing_tables'])
        self.assertNotIn('unfiltered_visible_cases',report)
