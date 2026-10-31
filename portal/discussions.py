"""Server-only discussion forms, grouped reads, and verified member writes."""
from django import forms
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import CaseComment, Request, Revision, Audit
from .reading_registry import READING_KEYS
from .security import limit


def identity_verified(request):
    from .access import access_valid
    return access_valid(request)


class CommentForm(forms.Form):
    body = forms.CharField(label='의견 내용', max_length=10000, strip=True,
                           widget=forms.Textarea(attrs={'rows': 4}))


def discussion_context(request, key, error=None):
    # Query only the selected event, including its one-level replies.
    groups = {key: {'key': key, 'roots': [], 'responses': [], 'form': CommentForm(auto_id=f'id_{key}_%s')} for key in (key,)}
    nodes = {}
    for comment in CaseComment.objects.filter(reading_key=key):
        node = {'item': comment, 'replies': [], 'own': bool(request.member and comment.member_id == request.member.pk)}
        nodes[comment.pk] = node
        if not comment.parent_id:
            groups[comment.reading_key]['roots'].append(node)
    for node in nodes.values():
        item = node['item']
        if item.parent_id in nodes:
            nodes[item.parent_id]['replies'].append(node)
    for response in Request.objects.filter(public_approved=True, kind='response', reading_key=key).only('reading_key', 'public_excerpt', 'created_at', 'id').order_by('created_at', 'pk'):
        groups[response.reading_key]['responses'].append(response)
    if error:
        groups[error['key']]['error'] = error
    return {'discussions': groups, 'identity_verified': identity_verified(request)}


def failure(request, key, form, action, parent=None, pk=None, status=400):
    context = discussion_context(request, key, {'key': key, 'form': form, 'action': action, 'parent': parent, 'pk': pk})
    context.update(detail_context(request, key, context))
    return render(request, 'portal/reading_detail.html', context, status=status)


@require_POST
def comment_write(request, key, pk=None):
    from django.http import Http404
    if key not in READING_KEYS:
        raise Http404
    if not identity_verified(request):
        return HttpResponseForbidden('의견 작성·수정·삭제에는 관리자 신원 확인 후 발급된 개인별 일회용 접속 수단이 필요합니다. /exception/에서 접속하세요.')
    form = CommentForm(request.POST)
    action = request.POST.get('action', 'create')
    parent_id = request.POST.get('parent', '')
    allowed = limit('comment:'+str(request.member.pk), 30, 3600)
    if not allowed:
        form.is_valid()
        form.add_error(None, '작성 요청이 너무 많습니다. 잠시 후 다시 시도하세요.')
        return failure(request, key, form, action, parent_id or None, pk, 429)
    if any(field in request.POST for field in ('member', 'member_id', 'author_name', 'author_label', 'author_id')):
        form.is_valid()
        form.add_error(None, '작성자 정보는 서버에서 지정합니다.')
        return failure(request, key, form, action, parent_id or None, pk)
    if action not in ('create', 'edit', 'delete') or (action == 'create') != (pk is None):
        return HttpResponseForbidden('잘못된 의견 요청입니다.')
    # Bound forms are retained in the reading page on validation/rate-limit errors.
    valid = form.is_valid() if action != 'delete' else True
    if not valid:
        return failure(request, key, form, action, parent_id or None, pk)
    with transaction.atomic():
        if pk:
            comment = get_object_or_404(CaseComment.objects.select_for_update(), pk=pk, reading_key=key,
                                        member=request.member, deleted_at=None, hidden=False)
            Revision.objects.create(target=f'comment:{comment.pk}', actor=str(request.member.pk),
                                    body={'body': comment.body, 'action': action})
            if action == 'edit':
                comment.body = form.cleaned_data['body']
                comment.edited = True
            else:
                comment.deleted_at = timezone.now()
            comment.save()
        else:
            parent = None
            if parent_id:
                try:
                    parent = CaseComment.objects.select_for_update().filter(pk=int(parent_id), reading_key=key, parent=None, hidden=False, deleted_at=None).first()
                except (ValueError, OverflowError):
                    pass
                if not parent:
                    form.add_error(None, '이 사건의 삭제·숨김되지 않은 최상위 의견에만 답글을 연결할 수 있습니다.')
                    return failure(request, key, form, action, parent_id)
            comment = CaseComment(reading_key=key, member=request.member, author_name=request.member.name,
                                  author_label=request.member.display_label, body=form.cleaned_data['body'], parent=parent)
            comment.full_clean()
            comment.save()
        Audit.objects.create(actor=str(request.member.pk), action='comment_'+action, target=f'comment:{comment.pk}', reason='본인 확인 교인 요청')
    return redirect(f'/cases/material/{key}/#comment-{comment.pk}')


def detail_context(request, key, discussion=None):
    from django.http import Http404
    from .reading_registry import reading_entries
    entries = reading_entries()
    if key not in READING_KEYS: raise Http404
    index = next(i for i, e in enumerate(entries) if e['key'] == key)
    return dict(discussion or discussion_context(request, key), selected_key=key,
                entry=entries[index], previous=entries[index-1] if index else None,
                following=entries[index+1] if index+1 < len(entries) else None)
