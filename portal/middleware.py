from django.shortcuts import redirect, render
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import resolve, Resolver404
from .models import Member

# Clear only member authentication: preparation and administrator sessions are separate.
MEMBER_SESSION_KEYS = (
    'member_id', 'member_auth', 'member_version', 'identity_member',
    'identity_version', 'identity_until', 'challenge_id',
)


def clear_member_session(request):
    for key in MEMBER_SESSION_KEYS:
        request.session.pop(key, None)


def public_read(request):
    if request.method not in ('GET', 'HEAD'):
        return False
    try:
        match = resolve(request.path_info)
    except Resolver404:
        return False
    return match.url_name in ('cases', 'legacy_cases', 'case', 'fixed_case', 'policy', 'health', 'business_number_evidence',
        'devotion_hymn', 'devotion_acts') or (
        match.url_name == 'document' and match.kwargs['kind'] == 'reading'
    )


class RetiredEvidenceStaticMiddleware:
    """Block legacy evidence URLs even if old collected copies still exist."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(f"{settings.STATIC_URL}portal/business-number/"):
            response = HttpResponseNotFound()
            response['Cache-Control'] = 'no-store'
            return response
        return self.get_response(request)


class AccessMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        from django.utils.cache import patch_vary_headers
        response=self.authorize(request)
        response['Cache-Control']='no-store, private'
        response['X-Robots-Tag']='noindex, nofollow'
        response['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        patch_vary_headers(response, ('Cookie',))
        return response
    def authorize(self,request):
        request.member = None
        request.member_board_enabled = settings.MEMBER_BOARD_ENABLED
        path = request.path_info
        board_auth_path = path in ('/board/auth/', '/board/verify/')
        board_posts_path = path == '/posts' or path.startswith('/posts/')
        if not request.member_board_enabled and (board_auth_path or board_posts_path):
            return render(request, 'portal/board_unavailable.html', status=503)
        # The temporary preparation login is isolated from member authentication.
        # Every preparation view performs its own session check, including writes.
        if request.path == '/prepare' or request.path.startswith('/prepare/'):
            return self.get_response(request)
        mid=request.session.get('member_id')
        if mid:
            try:
                member=Member.objects.filter(pk=mid,active=True).first()
            except (ValidationError, ValueError, TypeError):
                member=None
            if member and request.session.get('member_auth') in ('roster','exception') and member.session_version == request.session.get('member_version') and (request.session.get('member_auth')=='exception' or Member.objects.filter(phone=member.phone,active=True).count()==1):
                request.member=member
            else: clear_member_session(request)
        from .access import access_valid
        try:
            valid_member = request.member and access_valid(request)
        except (TypeError, ValueError):
            valid_member = False
        if request.member and not valid_member:
            clear_member_session(request)
            request.member = None
        if request.user.is_authenticated and request.user.is_staff:
            request.member = None
        path=request.path
        public=public_read(request) or path in ('/login/','/otp/','/exception/','/apply/','/logout/') or (request.method in ('GET','HEAD') and path.startswith('/static/'))
        if board_auth_path:
            return self.get_response(request)
        if board_posts_path and not request.member and not request.user.is_staff:
            from .board_auth import board_member
            request.member = board_member(request)
            request.board_only = request.member is not None
        admin_public=path in ('/admin/login/','/admin/logout/','/admin-mfa/')
        if path.startswith('/admin') or path.startswith('/roster/') or path.startswith('/exception-issue/') or path.startswith('/materials/'):
            if not admin_public:
                if not request.user.is_authenticated or not request.user.is_staff: return redirect('/admin/login/')
                if request.session.get('admin_mfa_until',0) < timezone.now().timestamp(): return redirect('/admin-mfa/')
        elif not public and not request.member and not (path.startswith('/documents/') and path.endswith('/original/') and request.user.is_authenticated and request.user.is_staff and request.session.get('admin_mfa_until',0)>timezone.now().timestamp()):
            return HttpResponseForbidden('공개 열람 범위에 포함되지 않는 요청입니다.')
        response=self.get_response(request)
        response['Cache-Control']='no-store, private'
        response['X-Robots-Tag']='noindex, nofollow'
        response['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

