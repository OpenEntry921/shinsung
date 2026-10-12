import json
from django.core.management.base import BaseCommand,CommandError
from portal.reviewed_materials import register,ImportRejected

class Command(BaseCommand):
    help='Preview or atomically register a privately reviewed source manifest. Does not seed demo data.'
    def add_arguments(self,parser):
        parser.add_argument('source');parser.add_argument('--plan',required=True)
        parser.add_argument('--author',required=True);parser.add_argument('--reviewer',required=True)
        parser.add_argument('--apply',action='store_true');parser.add_argument('--publish',action='store_true')
        parser.add_argument('--approval-reason',default='')
    def handle(self,*args,**options):
        try:
            counts=register(options['source'],options['plan'],options['author'],options['reviewer'],options['apply'],options['publish'],options['approval_reason'])
        except ImportRejected as exc: raise CommandError(str(exc)) from None
        except Exception: raise CommandError('등록 실패: 원문·검토 파일·권한·필드·저장소를 확인하세요. 자료 내용은 출력하지 않습니다. DB 트랜잭션은 반영하지 않았습니다.') from None
        self.stdout.write(json.dumps(counts,ensure_ascii=False,indent=2))
