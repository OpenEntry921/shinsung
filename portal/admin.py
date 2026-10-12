from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms import ModelForm
from django.forms.models import BaseInlineFormSet
from django.urls import path
from django.shortcuts import get_object_or_404,render
from .case_services import case_context,publication_errors
from django.db.models import Q
from django.utils import timezone
from django.forms.models import model_to_dict
from .models import *

admin.site.site_header='교인 전용 사이트 관리'
admin.site.site_title='운영 관리'
admin.site.index_title='명부 · 자료 · 게시판 관리 (추가 인증 필요)'

class TrackedAdmin(admin.ModelAdmin):
    def private_log(self,request,obj,flag):
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType
        return LogEntry.objects.create(user_id=request.user.pk,content_type=ContentType.objects.get_for_model(obj),object_id=str(obj.pk),object_repr=f'{obj._meta.model_name}:{obj.pk}',action_flag=flag,change_message='보호된 관리자 변경 이력 참조')
    def log_addition(self,request,obj,message): return self.private_log(request,obj,1)
    def log_change(self,request,obj,message): return self.private_log(request,obj,2)
    def save_model(self,request,obj,form,change):
        if change:
            old=type(obj).objects.get(pk=obj.pk)
            data={k:str(v) for k,v in model_to_dict(old).items()}
            Revision.objects.create(target=f'{obj._meta.model_name}:{obj.pk}',actor=str(request.user.pk),body=data)
        super().save_model(request,obj,form,change)
        if isinstance(obj,(Article,Document,Decision,CaseEvidence,CaseStatement,ArticleCaseLink)):
            from .signals import affected
            Case.objects.filter(pk__in=affected(obj)|getattr(obj,'_previous_case_ids',set())).update(last_editor=request.user)
        Audit.objects.create(actor=str(request.user.pk),action='change' if change else 'create',target=f'{obj._meta.model_name}:{obj.pk}',reason=form.cleaned_data.get('reason','내용 변경 이력 보존'))
    def save_related(self,request,form,formsets,change):
        super().save_related(request,form,formsets,change)
        if isinstance(form.instance,(Article,Document,Decision,CaseEvidence,CaseStatement,ArticleCaseLink)):
            from .signals import affected
            Case.objects.filter(pk__in=affected(form.instance)|getattr(form.instance,'_previous_case_ids',set())).update(last_editor=request.user)
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
            self.instance.sources_reviewed=data.get('sources_reviewed',False)
            self.instance.privacy_reviewed=data.get('privacy_reviewed',False)
            self.instance.publication_reason=data.get('publication_reason','')
            errors=publication_errors(self.instance) if self.instance.pk else ['초안으로 먼저 저장하세요.']
            if errors: raise ValidationError(errors)
            if set(self.changed_data)-{'state','publication_reason','sources_reviewed','privacy_reviewed'}: raise ValidationError('내용 수정은 검토 중으로 저장한 뒤 다른 승인자가 확인해야 합니다.')
            self.instance.reviewer=self.actor
        else: self.instance.reviewer=None
        return data
@admin.register(Case)
class CaseAdmin(TrackedAdmin):
    form=CaseForm
    list_display=['title','date_display','state','status_as_of','materials_as_of','author','reviewer']
    def date_display(self,obj): return obj.date_label
    fieldsets=[('사건·근거 자료',{'fields':('title','topic','overview','occurred_precision','occurred_on','occurred_year','occurred_month','occurred_until','period_description','related_cases','timeline','facts','claims','unknown')}),('현재 상황·검토',{'fields':('status','status_as_of','materials_as_of','decisions','responses','issues','additional_materials','opinion')}),('검토·게시',{'fields':('state','sources_reviewed','privacy_reviewed','publication_reason','review_summary','author','reviewer','last_editor','created_at','updated_at')})]
    change_form_template='admin/portal/case/change_form.html'
    def get_urls(self):
        return [path('<int:pk>/preview/',self.admin_site.admin_view(self.preview),name='portal_case_preview')]+super().get_urls()
    def preview(self,request,pk):
        case=get_object_or_404(Case,pk=pk)
        if not self.has_view_permission(request,case): raise PermissionDenied()
        return render(request,'portal/case.html',case_context(case,preview=True))
    readonly_fields=['author','reviewer','last_editor','created_at','updated_at']
    def get_form(self,request,obj=None,**kwargs):
        form=super().get_form(request,obj,**kwargs)
        return type('ActorCaseForm',(form,),{'actor':request.user})
    def save_related(self,request,form,formsets,change):
        super().save_related(request,form,formsets,change)
        if any(formset.has_changed() if hasattr(formset,'has_changed') else any(item.has_changed() for item in formset.forms) for formset in formsets):
            Case.objects.filter(pk=form.instance.pk).update(last_editor=request.user)
    def save_model(self,request,obj,form,change):
        if not change: obj.author=request.user
        if obj.state=='published':
            if not request.user.has_perm('portal.publish_case') or obj.author_id==request.user.pk or obj.last_editor_id==request.user.pk: raise PermissionDenied('작성자 외 승인 권한자가 직접 확인해야 합니다.')
            obj.reviewer=request.user
        else:
            obj.reviewer=None; obj.last_editor=request.user
            if set(form.changed_data)-{'state','sources_reviewed','privacy_reviewed','publication_reason','review_summary'}:
                obj.sources_reviewed=False;obj.privacy_reviewed=False
        obj.full_clean()
        old_state=Case.objects.filter(pk=obj.pk).values_list('state',flat=True).first() if change else None
        super().save_model(request,obj,form,change)
        if obj.state=='published' and old_state!='published':
            Audit.objects.create(actor=str(request.user.pk),action='case_publish',target=str(obj.pk),reason=obj.publication_reason)
        if obj.state=='published' and old_state!='published' and obj.review_summary.strip():
            ChangeNote.objects.create(case=obj,summary=obj.review_summary.strip())
            obj.review_summary=''; obj.save(update_fields=['review_summary'])

@admin.register(Article)
class ArticleAdmin(TrackedAdmin):
    list_display=['citation','case','verified','applicability_status']
    readonly_fields=['applicable']
    def save_model(self,request,obj,form,change):
        super().save_model(request,obj,form,change)
        ids={obj.case_id}|set(obj.related_cases.values_list('pk',flat=True))
        Case.objects.filter(pk__in=ids).update(state='review',reviewer=None,last_editor=request.user,updated_at=timezone.now())

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
        if obj.state=='published' and (not request.user.has_perm('portal.publish_case') or (obj.case and obj.case.author_id==request.user.pk)): raise PermissionDenied('작성자 외 게시 승인 권한이 필요합니다.')
        super().save_model(request,obj,form,change)
        fields={'state':'review','reviewer':None,'updated_at':timezone.now()}
        if set(form.changed_data)-{'state','redaction_checked'}: fields['last_editor']=request.user
        ids={obj.case_id}|set(obj.case_links.values_list('case_id',flat=True))
        Case.objects.filter(pk__in=ids).update(**fields)

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

class ReviewInlineSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if self.instance.state=='published' and any(form.has_changed() for form in self.forms): raise ValidationError('영역별 내용 수정은 먼저 초안·검토 중으로 저장한 뒤 다른 승인자가 게시하세요.')
class StatementForm(ModelForm):
    class Meta: model=CaseStatement; exclude=[]
    def clean(self):
        data=super().clean()
        case=data.get('case')
        case_id=case.pk if case else self.instance.case_id
        if any(evidence.case_id!=case_id for evidence in data.get('supporting_evidence',[])): raise ValidationError('추가 근거도 같은 사건의 자료를 선택하세요.')
        return data
class StatementInline(admin.StackedInline):
    model=CaseStatement
    form=StatementForm
    formset=ReviewInlineSet
    extra=0
    verbose_name_plural='사건 설명: 사실·주장·미확인·의견 및 경과'
class EvidenceInline(admin.TabularInline):
    model=CaseEvidence
    formset=ReviewInlineSet
    extra=0
    verbose_name_plural='근거 자료와 페이지·문단·증거번호'
class ArticleInline(admin.StackedInline):
    model=Article
    readonly_fields=['applicable']
    formset=ReviewInlineSet
    extra=0
    verbose_name_plural='관련 통합 헌법·시행규정'
class ArticleCaseLinkInline(admin.StackedInline):
    model=ArticleCaseLink
    formset=ReviewInlineSet
    extra=0
    verbose_name_plural='공유 조문의 이 사건 적용 정보'
CaseAdmin.inlines=[EvidenceInline,StatementInline,ArticleInline,ArticleCaseLinkInline]

class DocumentForm(ModelForm):
    class Meta: model=Document; exclude=[]
    def clean(self):
        data=super().clean()
        if self.files:
            from .memo_import import require_private_environment
            require_private_environment()
        return data
DocumentAdmin.form=DocumentForm

@admin.register(CaseEvidence)
class EvidenceAdmin(TrackedAdmin):
    list_display=['case','document','locator','checked']
@admin.register(CaseStatement)
class StatementAdmin(TrackedAdmin):
    form=StatementForm
    list_display=['case','kind','source_note']
@admin.register(Decision)
class DecisionAdmin(TrackedAdmin):
    list_display=['institution','case_number','outcome','finality','verified']
    filter_horizontal=['cases']
    def save_related(self,request,form,formsets,change):
        super().save_related(request,form,formsets,change)
        Case.objects.filter(pk__in=form.instance.cases.values_list('pk',flat=True)).update(last_editor=request.user)
@admin.register(MemoImport)
class MemoImportAdmin(ReadOnlyAdmin):
    list_display=['id','basis_on','created_at']
@admin.register(ImportCandidate)
class ImportCandidateAdmin(TrackedAdmin):
    list_display=['id','topic','state','reviewed','case']
    readonly_fields=['batch','key','internal_excerpt','source_locator','article_hints','date_candidates','case','state']
    fields=['batch','key','topic','title','internal_excerpt','source_locator','neutral_summary','required_originals','article_hints','date_candidates','occurred_precision','occurred_on','occurred_year','occurred_month','occurred_until','period_description','reviewed','case','state']
    def has_add_permission(self,request): return False

@admin.register(ArticleCaseLink)
class ArticleCaseLinkAdmin(TrackedAdmin):
    list_display=['case','article','applicability_status']

@admin.register(ReviewedMaterialImport)
class ReviewedImportAdmin(ReadOnlyAdmin):
    list_display=['key','basis_on','created_at']

@admin.register(RegisteredMaterialCase)
class RegisteredCaseAdmin(ReadOnlyAdmin):
    list_display=['key','case','verification']
