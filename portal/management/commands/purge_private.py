from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from portal.models import *
class Command(BaseCommand):
    help='Apply proposed retention policy. Run daily; review legal retention needs first.'
    def handle(self,*args,**kwargs):
        now=timezone.now()
        Challenge.objects.filter(expires_at__lt=now).delete()
        RateBucket.objects.filter(start__lt=now-timedelta(days=1)).delete()
        RosterBatch.objects.filter(created_at__lt=now-timedelta(hours=1)).delete()
        Post.objects.filter(deleted_at__lt=now-timedelta(days=30)).update(title='삭제된 글',body='',author_name='삭제된 작성자')
        CaseComment.objects.filter(deleted_at__lt=now-timedelta(days=30)).update(body='',author_name='삭제된 작성자',author_label='')
        Request.objects.filter(resolved=True,created_at__lt=now-timedelta(days=90)).delete()
        Revision.objects.filter(created_at__lt=now-timedelta(days=90)).delete()
        Audit.objects.filter(created_at__lt=now-timedelta(days=90)).delete()
        self.stdout.write('보유기간 정리 완료. 백업·명부 삭제는 운영 정책에 따라 별도 확인하세요.')
