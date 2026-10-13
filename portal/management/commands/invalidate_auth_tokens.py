from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.db import transaction
from portal.models import Challenge

class Command(BaseCommand):
    help = '비밀키 교체 후 기존 세션·OTP 무효화. 교인·관리자·게시글은 보존.'
    def handle(self, *args, **options):
        with transaction.atomic():
            Session.objects.all().delete()
            Challenge.objects.all().delete()
        self.stdout.write('기존 세션·인증번호 무효화 완료. 계정·게시글 보존.')
