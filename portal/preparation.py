"""An unlisted workspace with a deliberately temporary, shared login."""
import hmac
import json
from functools import lru_cache, wraps
from pathlib import Path

from django import forms
from django.db.models import Count
from django.http import Http404
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .models import PreparationComment, PreparationReview
from .reading_registry import TIMELINE_KEYS
from .security import limit, phone

SESSION_KEY = 'preparation_until'


@lru_cache(maxsize=1)
def preparation_data():
    data = json.loads((Path(__file__).parent / 'preparation_data.json').read_text(encoding='utf-8'))
    rows = data['entries']
    if tuple(row['key'] for row in rows) != TIMELINE_KEYS or [row['number'] for row in rows] != list(range(1, 73)):
        raise ValueError('Preparation snapshot keys and numbers must match the 72-event timeline.')
    return data


def authenticated(request):
    until = request.session.get(SESSION_KEY)
    return isinstance(until, (int, float)) and until > timezone.now().timestamp()


def preparation_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not authenticated(request):
            request.session.pop(SESSION_KEY, None)
            return redirect('prepare')
        return view(request, *args, **kwargs)
    return wrapped


class LoginForm(forms.Form):
    name = forms.CharField(label='이름', max_length=80)
    phone = forms.CharField(label='전화번호', max_length=20,
                            widget=forms.TextInput(attrs={'inputmode': 'tel', 'autocomplete': 'off'}))


class CommentForm(forms.Form):
    author_name = forms.CharField(label='작성자 이름', max_length=80)
    kind = forms.ChoiceField(label='의견 유형', choices=PreparationComment.KINDS)
    source_reference = forms.CharField(label='자료명·쪽수·날짜 (선택)', max_length=500, required=False)
    body = forms.CharField(label='의견 내용', max_length=10000, widget=forms.Textarea(attrs={'rows': 6}))


@require_http_methods(['GET', 'HEAD'])
def prepare_redirect(request):
    return redirect('prepare')


@require_http_methods(['GET', 'HEAD', 'POST'])
def index(request):
    if not authenticated(request):
        request.session.pop(SESSION_KEY, None)
        form = LoginForm(request.POST if request.method == 'POST' else None)
        status = 200
        if request.method == 'POST':
            allowed = limit('prepare-login:' + request.META.get('REMOTE_ADDR', ''), 20, 3600)
            if not allowed:
                form.is_valid()
                form.add_error(None, '잠시 후 다시 시도하세요.')
                status = 429
            elif form.is_valid():
                if (hmac.compare_digest(form.cleaned_data['name'].encode(), '준비위원'.encode())
                        and hmac.compare_digest(phone(form.cleaned_data['phone']).encode(), b'01011111111')):
                    request.session.cycle_key()
                    rotate_token(request)
                    request.session[SESSION_KEY] = timezone.now().timestamp() + 3600
                    request.session.set_expiry(3600)
                    return redirect('prepare')
                form.add_error(None, '이름과 전화번호를 확인해 주세요.')
        return render(request, 'portal/prepare_login.html', {'form': form}, status=status)

    from .appeals import index as appeal_index
    return appeal_index(request)


@require_http_methods(['GET', 'HEAD'])
@preparation_required
def events(request):
    data = preparation_data()
    states = {state.reading_key: state for state in PreparationReview.objects.all()}
    counts = dict(PreparationComment.objects.filter(hidden=False).values('reading_key').annotate(n=Count('pk')).values_list('reading_key', 'n'))
    q = request.GET.get('q', '').strip()[:200]
    selected_status = request.GET.get('status', '')
    rows = []
    for original in data['entries']:
        row = dict(original)
        state = states.get(row['key'])
        row['state'] = state
        row['status'] = state.status if state else 'unreviewed'
        row['status_label'] = dict(PreparationReview.STATUS).get(row['status'], '미검토')
        row['comment_count'] = counts.get(row['key'], 0)
        haystack = f"{row['number']:02} " + ' '.join(str(value) for value in original.values())
        if state:
            haystack += ' ' + state.evidence_notes + ' ' + state.revised_draft
        if q and q.casefold() not in haystack.casefold():
            continue
        if selected_status and row['status'] != selected_status:
            continue
        rows.append(row)
    return render(request, 'portal/prepare_index.html', {
        'rows': rows, 'q': q, 'selected_status': selected_status, 'statuses': PreparationReview.STATUS,
        'confirmed_count': sum(state.status == 'confirmed' for state in states.values()),
        'data': data, 'prepare_logged_in': True,
    })


def selected_entry(key):
    return next((entry for entry in preparation_data()['entries'] if entry['key'] == key), None)


def detail_context(key, form=None):
    entry = selected_entry(key)
    if entry is None:
        raise Http404
    entries = preparation_data()['entries']
    position = entry['number'] - 1
    state = PreparationReview.objects.filter(reading_key=key).first()
    return {
        'entry': entry, 'state': state,
        'status_label': state.get_status_display() if state else '미검토',
        'comments': PreparationComment.objects.filter(reading_key=key, hidden=False),
        'form': form if form is not None else CommentForm(),
        'previous': entries[position-1] if position else None,
        'following': entries[position+1] if position+1 < len(entries) else None,
        'prepare_logged_in': True,
    }


@require_http_methods(['GET', 'HEAD'])
@preparation_required
def detail(request, key):
    return render(request, 'portal/prepare_detail.html', detail_context(key))


@require_POST
@preparation_required
def comment(request, key):
    if selected_entry(key) is None:
        raise Http404
    form = CommentForm(request.POST)
    valid = form.is_valid()
    if not limit('prepare-comment:' + request.META.get('REMOTE_ADDR', ''), 60, 3600):
        form.add_error(None, '작성 요청이 많습니다. 잠시 후 다시 시도하세요.')
        return render(request, 'portal/prepare_detail.html', detail_context(key, form), status=429)
    if valid:
        item = PreparationComment(reading_key=key, **form.cleaned_data)
        item.full_clean()
        item.save()
        return redirect(f'/prepare/events/{key}/#prepare-comment-{item.pk}')
    return render(request, 'portal/prepare_detail.html', detail_context(key, form), status=400)


@require_POST
def logout(request):
    request.session.pop(SESSION_KEY, None)
    rotate_token(request)
    return redirect('prepare')
