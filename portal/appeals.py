"""Appeal-centric preparation. All views reuse the isolated preparation session."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from django import forms
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .models import AppealComment, AppealReview, PreparationReview, PreparationComment
from .preparation import preparation_required, preparation_data
from .security import limit

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def appeal_data():
    data = json.loads((ROOT / 'appeal_claims.json').read_text(encoding='utf-8'))
    entries = data['entries']
    ids = [r['id'] for r in entries]
    if len(ids) != len(set(ids)) or not all(re.fullmatch(r'AP26-[a-z-]+', key) for key in ids):
        raise ValueError('Invalid appeal claim IDs')
    events = {r['key'] for r in preparation_data()['entries']}
    groups = {g['id'] for g in data['groups']}
    for row in entries:
        if row['group'] not in groups or not set(row['related_keys']) <= events:
            raise ValueError('Invalid appeal references')
        if not row['pdf_pages'] or not all(4 <= p <= 18 for p in row['pdf_pages']):
            raise ValueError('Invalid appeal source pages')
    if [r['order'] for r in entries] != list(range(1, len(entries) + 1)):
        raise ValueError('Invalid appeal source order')
    return data


def selected_claim(key):
    return next((r for r in appeal_data()['entries'] if r['id'] == key), None)


def presented(row, state=None):
    result = dict(row)
    registry = {r['key']: r for r in preparation_data()['entries']}
    result['related'] = [registry[key] for key in row['related_keys']]
    result['state'] = state
    result['status'] = state.status if state else 'unreviewed'
    result['status_label'] = dict(PreparationReview.STATUS)[result['status']]
    # This is the redacted excerpt's page, NOT the original PDF or printed page.
    result['source_links'] = [(p, reverse('prepare_document', args=['appeal-body']) + f'#page={p-3}') for p in row['pdf_pages']]
    result['judgment_links'] = [(p, reverse('prepare_document', args=['judgment']) + f'#page={p}') for p in row['judgment_pages']]
    return result


@require_http_methods(['GET', 'HEAD'])
@preparation_required
def index(request):
    states = {s.claim_id: s for s in AppealReview.objects.all()}
    counts = dict(AppealComment.objects.filter(hidden=False).values('claim_id').annotate(n=Count('pk')).values_list('claim_id', 'n'))
    q = request.GET.get('q', '').strip()[:200]
    selected_status = request.GET.get('status', '')
    rows = []
    for row in appeal_data()['entries']:
        item = presented(row, states.get(row['id']))
        haystack = json.dumps(row, ensure_ascii=False) + ' '.join(f"{r['number']:02} {r['key']} {r['title']}" for r in item['related'])
        if item['state']:
            haystack += item['state'].revised_draft + item['state'].evidence_notes
        if q and q.casefold() not in haystack.casefold():
            continue
        if selected_status and selected_status != item['status']:
            continue
        item['comment_count'] = counts.get(row['id'], 0)
        rows.append(item)
    return render(request, 'portal/prepare_appeal_index.html', dict(rows=rows, data=appeal_data(), q=q, selected_status=selected_status, statuses=PreparationReview.STATUS, prepare_logged_in=True))


class CommentForm(forms.Form):
    author_name = forms.CharField(label='작성자 이름 (직접 기재·개별 인증 아님)', max_length=80)
    kind = forms.ChoiceField(label='의견 유형', choices=PreparationComment.KINDS)
    source_reference = forms.CharField(label='자료명·쪽수 (선택)', max_length=500, required=False)
    body = forms.CharField(label='의견 내용', max_length=10000, widget=forms.Textarea(attrs={'rows': 6}))


def detail_context(key, form=None):
    claim = selected_claim(key)
    if claim is None:
        raise Http404
    entries = appeal_data()['entries']
    pos = claim['order'] - 1
    return dict(entry=presented(claim, AppealReview.objects.filter(claim_id=key).first()), data=appeal_data(),
                comments=AppealComment.objects.filter(claim_id=key, hidden=False), form=form or CommentForm(),
                previous=entries[pos-1] if pos else None, following=entries[pos+1] if pos+1<len(entries) else None, prepare_logged_in=True)


@require_http_methods(['GET', 'HEAD'])
@preparation_required
def detail(request, key):
    return render(request, 'portal/prepare_appeal_detail.html', detail_context(key))


@require_POST
@preparation_required
def comment(request, key):
    if selected_claim(key) is None:
        raise Http404
    form = CommentForm(request.POST)
    valid = form.is_valid()
    if not limit('prepare-comment:' + request.META.get('REMOTE_ADDR', ''), 60, 3600):
        form.add_error(None, '작성 요청이 많습니다. 잠시 후 다시 시도하세요.')
        return render(request, 'portal/prepare_appeal_detail.html', detail_context(key, form), status=429)
    if valid:
        item = AppealComment(claim_id=key, **form.cleaned_data)
        item.full_clean()
        item.save()
        return redirect(reverse('prepare_appeal_detail', args=[key]) + f'#appeal-comment-{item.pk}')
    return render(request, 'portal/prepare_appeal_detail.html', detail_context(key, form), status=400)


@require_http_methods(['GET', 'HEAD'])
@preparation_required
def document(request, code):
    # No client-supplied file paths, no static URL, no unredacted fallback.
    if code == 'appeal-body':
        path = ROOT / 'private_documents/appeal-body.redacted.pdf'
        expected = appeal_data()['reading_copy']['sha256']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise Http404('열람본을 확인할 수 없습니다.')
    elif code == 'judgment':
        path = ROOT.parent / 'static/case-documents/A12.pdf'
        # This existing explicitly redacted source is unchanged.
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != appeal_data()['judgment_copy_sha256']:
            raise Http404
    else:
        raise Http404
    response = FileResponse(path.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="preparation-' + code + '.pdf"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
