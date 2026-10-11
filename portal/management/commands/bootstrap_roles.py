from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group,Permission
class Command(BaseCommand):
    help='Create separate roster, content editor and publisher roles; assign users explicitly.'
    def handle(self,*args,**kwargs):
        permissions={'명부 관리자':['view_member','change_member'],'내용 편집자':['view_case','add_case','change_case','view_article','add_article','change_article','view_document','add_document','change_document','view_request','change_request','view_revision'],'게시 승인자':['view_case','change_case','publish_case','view_article','change_article','view_document','change_document'],'게시판 관리자':['view_post','change_post','view_request','change_request','view_audit','view_revision']}
        for name,codes in permissions.items():
            group,_=Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(content_type__app_label='portal',codename__in=codes))
        self.stdout.write('운영 역할 준비 완료. 계정의 staff 및 개별 역할은 별도 지정하세요.')
