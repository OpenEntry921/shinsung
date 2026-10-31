from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from portal.models import Member, Audit


class Command(BaseCommand):
    help = 'Create the synthetic development member; optionally restore its own login.'

    def add_arguments(self, parser):
        parser.add_argument('--enable-login', action='store_true',
                            help='Explicitly enable only this synthetic development member login.')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEV:
            raise CommandError('개발 모드에서만 가능합니다.')
        if Member.objects.filter(synthetic=False).exists():
            raise CommandError('실제 명부가 있는 DB에는 시연 데이터를 추가하지 않습니다.')
        matches = Member.objects.select_for_update().filter(phone='01000000000')
        if matches.count() > 1 or (matches.exists() and matches.first().name != '가상교인'):
            raise CommandError('가상 계정과 기존 계정의 충돌을 확인하세요. 데이터를 변경하지 않았습니다.')
        member, created = Member.objects.get_or_create(
            name='가상교인', phone='01000000000', defaults={'synthetic': True})
        if options['enable_login'] and (created or not member.active or not member.legacy_operator):
            member.active = True
            member.legacy_operator = True
            member.save()
            Audit.objects.create(actor='management:seed_demo', action='synthetic_login_enable',
                                 target=str(member.pk), reason='명시적 개발용 가상교인 접속 복구')
        self.stdout.write('가상교인 / 01000000000 (개발 전용). 사건·댓글·신청 데이터를 생성하거나 변경하지 않았습니다.')
        if options['enable_login']:
            self.stdout.write('개발용 가상교인 로그인 활성화 완료. 관리자 권한은 부여하지 않았습니다.')
