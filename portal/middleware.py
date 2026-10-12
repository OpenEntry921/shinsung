from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.utils import timezone
from .models import Member, ReviewedMaterialImport

class AccessMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        request.member = None
        mid=request.session.get('member_id')
        if mid:
            member=Member.objects.filter(pk=mid,active=True).first()
            if member and (not settings.DEV or member.synthetic) and member.session_version == request.session.get('member_version') and (request.session.get('member_auth')=='exception' or Member.objects.filter(phone=member.phone,active=True).count()==1):
                request.member=member
            else: request.session.flush()
        path=request.path
        public=path in ('/login/','/otp/','/exception/','/policy/','/health/') or path.startswith('/static/')
        admin_public=path in ('/admin/login/','/admin/logout/','/admin-mfa/')
        # Public demo OTPs must never unlock an accidentally reused real-material database.
        admin_path=path.startswith(('/admin','/roster/','/exception-issue/','/materials/'))
        if request.member and settings.DEV and not public and not admin_path and ReviewedMaterialImport.objects.exists():
            response=HttpResponseForbidden('시연 저장소와 실제 자료 저장소를 분리하고 운영 모드에서 열람하세요.')
            response['Cache-Control']='no-store, private'
            return response
        if path.startswith('/admin') or path.startswith('/roster/') or path.startswith('/exception-issue/') or path.startswith('/materials/'):
            if not admin_public:
                if not request.user.is_authenticated or not request.user.is_staff: return redirect('/admin/login/')
                if request.session.get('admin_mfa_until',0) < timezone.now().timestamp(): return redirect('/admin-mfa/')
        elif not public and not request.member and not (path.startswith('/documents/') and path.endswith('/original/') and request.user.is_authenticated and request.user.is_staff and request.session.get('admin_mfa_until',0)>timezone.now().timestamp()):
            if path.startswith('/api/') or path.startswith('/documents/'): return HttpResponseForbidden('로그인이 필요합니다.')
            return redirect('/login/')
        response=self.get_response(request)
        response['Cache-Control']='no-store, private'
        response['X-Robots-Tag']='noindex, nofollow'
        response['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
