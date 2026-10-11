from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms import ModelForm
from django.db.models import Q
from django.utils import timezone
from django.forms.models import model_to_dict
from .models import *

admin.site.site_header='교인 전용 사이트 관리'
admin.site.site_title='운영 관리'
admin.site.index_title='명부 · 자료 · 게시판 관리 (추가 인증 필요)'

class TrackedAdmin(admin.ModelAdmin):
    def save_model(self,request,obj,form,change):
        if change:
            old=type(obj).objects.get(pk=obj.pk)
            data={k:str(v) for k,v in model_to_dict(old).items()}
            Revision.objects.create(target=f'{obj._meta.model_name}:{obj.pk}',actor=str(request.user.pk),body=data)
        super().save_model(request,obj,form,change)
        Audit.objects.create(actor=str(request.user.pk),action='change' if change else 'create',target=f'{obj._meta.model_name}:{obj.pk}',reason=form.cleaned_data.get('reason','내용 변경 이력 보존'))
    def has_delete_permission(self,request,obj=None): return False

class MemberForm(ModelForm):
    reason=__import__('django').forms.CharField(label='변경 사유 (연락처·활성 상태 변경 시 필수)')
    class Meta: model=Member; fields=['name','phone','active','label']
    def clean_phone(self):
        from .security import phone
        import re
        value=phone(self.cleaned_data['phone'])
        if not re.fullmatch(r'0\d{8,10}',value): raise ValidationError('정규화된 전화번호를 확인하세요.')
        return value
@admin.register(Member)
class MemberAdmin(TrackedAdmin):
    form=MemberForm
    list_display=['id','name','active','label','updated_at']
    search_fields=['name']
    readonly_fields=['id','session_version','created_at','updated_at','synthetic']
    def has_add_permission(self,request): return False
    def save_model(self,request,obj,form,change):
        # Do not copy roster names or phone numbers into audit/history records.
        obj.save()
        Audit.objects.create(actor=str(request.user.pk),action='member_change',target=str(obj.pk),reason=form.cleaned_data['reason'])

class CaseForm(ModelForm):
    actor = None
    class Meta: model=Case; exclude=['author','reviewer','last_editor']
    def clean(self):
        data=super().clean()
        if not self.instance.pk: self.instance.author=self.actor
        if data.get('state')=='published':
            if self.instance.author_id==self.actor.pk or self.instance.last_editor_id==self.actor.pk or not self.actor.has_perm('portal.publish_case'):
                raise ValidationError('작성자 외 게시 승인 권한자가 확인해야 합니다.')
            if set(self.changed_data)-{'state'}: raise ValidationError('내용 수정은 검토 중으로 저장한 뒤 다른 승인자가 확인해야 합니다.')
            self.instance.reviewer=self.actor
        else: self.instance.reviewer=None
        return data
@admin.register(Case)
class CaseAdmin(TrackedAdmin):
    form=CaseForm
    list_display=['title','occurred_on','state','author','reviewer']
    readonly_fields=['author','reviewer','last_editor','created_at','updated_at']
    def get_form(self,request,obj=None,**kwargs):
        form=super().get_form(request,obj,**kwargs)
        return type('ActorCaseForm',(form,),{'actor':request.user})
    def save_model(self,request,obj,form,change):
        if not change: obj.author=request.user
        if obj.state=='published':
            if not request.user.has_perm('portal.publish_case') or obj.author_id==request.user.pk or obj.last_editor_id==request.user.pk: raise PermissionDenied('작성자 외 승인 권한자가 직접 확인해야 합니다.')
            obj.reviewer=request.user
        else: obj.reviewer=None; obj.last_editor=request.user
        obj.full_clean()
        old_state=Case.objects.filter(pk=obj.pk).values_list('state',flat=True).first() if change else None
        super().save_model(request,obj,form,change)
        if obj.state=='published' and old_state!='published' and obj.review_summary.strip():
            ChangeNote.objects.create(case=obj,summary=obj.review_summary.strip())
            obj.review_summary=''; obj.save(update_fields=['review_summary'])

@admin.register(Article)
class ArticleAdmin(TrackedAdmin):
    list_display=['citation','case','verified','applicable']
    def save_model(self,request,obj,form,change):
        super().save_model(request,obj,form,change)
        Case.objects.filter(pk=obj.case_id).update(state='review',reviewer=None,last_editor=request.user,updated_at=timezone.now())

@admin.register(Document)
class DocumentAdmin(TrackedAdmin):
    list_display=['title','case','state','redaction_checked']
    # File URLs are never presented as public storage paths.
    readonly_fields=['original_download']
    def original_download(self,obj):
        from django.utils.html import format_html
        if not obj.pk: return '저장 후 관리자 전용 다운로드 가능'
        return format_html('<a href="/documents/{}/original/">원본 다운로드</a>',obj.pk)
    def save_model(self,request,obj,form,change):
        if obj.state=='published' and (not request.user.has_perm('portal.publish_case') or obj.case.author_id==request.user.pk): raise PermissionDenied('작성자 외 게시 승인 권한이 필요합니다.')
        super().save_model(request,obj,form,change)
        fields={'state':'review','reviewer':None,'updated_at':timezone.now()}
        if set(form.changed_data)-{'state','redaction_checked'}: fields['last_editor']=request.user
        Case.objects.filter(pk=obj.case_id).update(**fields)

class ModerationForm(ModelForm):
    class Meta: model=Post; fields=['hidden','moderation_reason']
    def clean(self):
        data=super().clean()
        if not data.get('moderation_reason','').strip(): raise ValidationError('관리자 조치 사유를 기록하세요.')
        return data
@admin.register(Post)
class PostAdmin(TrackedAdmin):
    form=ModerationForm
    fields=['member','author_name','title','body','created_at','updated_at','deleted_at','hidden','moderation_reason']
    readonly_fields=['member','author_name','title','body','created_at','updated_at','deleted_at']
    list_display=['title','author_name','hidden','created_at']
    def has_add_permission(self,request): return False

@admin.register(Request)
class RequestAdmin(TrackedAdmin):
    readonly_fields=['member','kind','case','post','body','created_at']
    fields=['member','kind','case','post','body','created_at','response','resolved']
    list_display=['kind','resolved','created_at']
    def has_add_permission(self,request): return False
    def save_model(self,request,obj,form,change):
        if obj.resolved and not obj.response.strip(): raise ValidationError('처리 사유·답변이 필요합니다.')
        super().save_model(request,obj,form,change)

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
@admin.register(Audit)
class AuditAdmin(ReadOnlyAdmin):
    list_display=['action','target','actor','created_at']
@admin.register(Revision)
class RevisionAdmin(ReadOnlyAdmin):
    list_display=['target','actor','created_at']
# OTP hashes, secrets, sessions and raw roster batches are deliberately not registered.

@admin.register(ChangeNote)
class ChangeNoteAdmin(ReadOnlyAdmin):
    list_display=['case','published_at']
