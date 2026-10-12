from django.db.models.signals import post_save, pre_save, m2m_changed, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Article,Document,Case,CaseEvidence,CaseStatement,Decision,ArticleCaseLink,RegisteredMaterialCase

def affected(obj):
    ids=set()
    if isinstance(obj,(Article,Document,CaseEvidence,CaseStatement,ArticleCaseLink)) and obj.case_id: ids.add(obj.case_id)
    if obj.pk:
        if isinstance(obj,Article): ids.update(obj.related_cases.values_list('pk',flat=True))
        if isinstance(obj,Document):
            ids.update(obj.case_links.values_list('case_id',flat=True))
            ids.update(RegisteredMaterialCase.objects.filter(batch__document=obj).values_list('case_id',flat=True))
            ids.update(CaseEvidence.objects.filter(document=obj).values_list('case_id',flat=True))
            ids.update(obj.decision_set.values_list('cases__pk',flat=True))
        if isinstance(obj,Decision): ids.update(obj.cases.values_list('pk',flat=True))
    return ids-{None}

def invalidate(ids):
    Case.objects.filter(pk__in=ids,state='published').update(state='review')
    Case.objects.filter(pk__in=ids).update(reviewer=None,sources_reviewed=False,privacy_reviewed=False,updated_at=timezone.now())

@receiver(pre_save)
def before_change(sender,instance,**kwargs):
    if sender in (Article,Document,CaseEvidence,CaseStatement,Decision,ArticleCaseLink):
        previous=sender.objects.filter(pk=instance.pk).first()
        instance._previous_case_ids=affected(previous) if previous else set()

@receiver(post_save)
def after_change(sender,instance,**kwargs):
    if sender in (Article,Document,CaseEvidence,CaseStatement,Decision,ArticleCaseLink): invalidate(affected(instance)|getattr(instance,'_previous_case_ids',set()))

@receiver(post_delete)
def after_delete(sender,instance,**kwargs):
    if sender in (Article,Document,CaseEvidence,CaseStatement,Decision,ArticleCaseLink): invalidate(getattr(instance,'_previous_case_ids',set())|({instance.case_id} if hasattr(instance,'case_id') else set()))

@receiver(m2m_changed)
def links_changed(sender,instance,action,reverse,pk_set,**kwargs):
    if sender in (Article.related_cases.through,Decision.cases.through):
        if action in ('pre_remove','pre_clear'): instance._removed_case_ids=affected(instance) if not isinstance(instance,Case) else {instance.pk}
        if action.startswith('post_'):
            ids=affected(instance) if not isinstance(instance,Case) else {instance.pk}
            if not reverse and pk_set: ids.update(pk_set)
            invalidate(ids|getattr(instance,'_removed_case_ids',set()))
    if sender==CaseStatement.supporting_evidence.through and action.startswith('post_'):
        invalidate({instance.case_id} if isinstance(instance,CaseStatement) else {instance.case_id})
