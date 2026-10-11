from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from portal.models import Member
class Command(BaseCommand):
    help='Create one explicitly synthetic development member, never a real roster.'
    def handle(self,*args,**kwargs):
        if not settings.DEV: raise CommandError('개발 모드에서만 가능합니다.')
        if Member.objects.filter(synthetic=False).exists(): raise CommandError('실제 명부가 있는 DB에는 시연 데이터를 추가하지 않습니다.')
        Member.objects.get_or_create(name='가상교인',phone='01000000000',defaults={'synthetic':True})
        self.stdout.write('가상교인 / 01000000000 (개발 전용). 실제 사건 데이터 없음.')
