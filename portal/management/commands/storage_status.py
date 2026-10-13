import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from portal.models import Member, Case, Article, CaseStatement, Document, Post

class Command(BaseCommand):
    help = '비밀값·개인정보 없이 DB 종류와 자료 수량 확인. 운영 보존 보장은 아님.'
    def handle(self, *args, **options):
        self.stdout.write(json.dumps({'database': connection.vendor,
            'persistence_operator_confirmed': settings.DATABASE_PERSISTENCE_CONFIRMED,
            'members':Member.objects.count(), 'cases':Case.objects.count(),
            'published_cases':Case.objects.filter(state='published').count(),
            'rules':Article.objects.count(),'statements':CaseStatement.objects.count(),
            'documents':Document.objects.count(),'posts':Post.objects.count()},ensure_ascii=False))
