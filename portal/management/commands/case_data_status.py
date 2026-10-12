"""Report counts only; never print protected content or change publication state."""
import json
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from portal.models import Case, Document, Article, Decision, MemoImport, ImportCandidate, ReviewedMaterialImport, RegisteredMaterialCase

class Command(BaseCommand):
    help='Read-only case data and publication diagnosis without titles, names or document contents.'

    def handle(self, *args, **options):
        tables=set(connection.introspection.table_names())
        report={'app_mode':settings.APP_MODE,'database_engine':connection.vendor,
                'private_storage_confirmed':settings.PRIVATE_STORAGE_CONFIRMED,
                'real_materials_enabled':settings.REAL_MATERIALS_ENABLED,
                'storage_persistence_verified':False,'counts':{},'missing_tables':[]}
        for label,model in [('cases',Case),('documents',Document),('articles',Article),('decisions',Decision),('imports',MemoImport),('candidates',ImportCandidate),('reviewed_imports',ReviewedMaterialImport),('registered_cases',RegisteredMaterialCase)]:
            if model._meta.db_table not in tables:
                report['counts'][label]=None;report['missing_tables'].append(label)
                continue
            report['counts'][label]=model.objects.count()
        if Case._meta.db_table in tables:
            report['case_states']={state:Case.objects.filter(state=state).count() for state in ('draft','review','published')}
            report['unfiltered_visible_cases']=Case.objects.filter(state='published').count()
        report['note']='Counts describe this process database only. Storage flags do not verify persistence. seed_demo creates a synthetic member only.'
        self.stdout.write(json.dumps(report,ensure_ascii=False,indent=2))
