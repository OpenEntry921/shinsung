from django.core.exceptions import PermissionDenied,ValidationError
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Document,ImportCandidate,Audit
from .memo_import import require_private_environment,extract_candidates,convert_candidate

def allowed(request):
    if not request.user.is_staff or not request.user.has_perms(['portal.change_importcandidate','portal.add_case','portal.view_document','portal.view_importcandidate']) or request.session.get('admin_mfa_until',0)<=timezone.now().timestamp(): raise PermissionDenied()

def memo_import(request):
    allowed(request); error='';batch=None
    try: require_private_environment()
    except ValidationError as e: return render(request,'portal/memo_import.html',{'error':e.messages[0],'disabled':True},status=403)
    if request.method=='POST':
        try:
            document=get_object_or_404(Document,pk=request.POST.get('document'),internal_memo=True)
            batch,_=extract_candidates(document,request.user)
            Audit.objects.create(actor=str(request.user.pk),action='memo_extract',target=str(batch.pk),reason='관리자 전용 후보 추출; 원자료 확인·개인정보 검토 전에는 공개 금지')
        except (ValidationError,ValueError) as e: error='문서 ID와 비공개 DOCX 구조를 확인하세요.'
    return render(request,'portal/memo_import.html',{'error':error,'batch':batch,'documents':Document.objects.filter(internal_memo=True),'candidates':ImportCandidate.objects.select_related('batch','case').all()})

@require_POST
def candidate_convert(request,pk):
    allowed(request)
    candidate=get_object_or_404(ImportCandidate,pk=pk)
    try: case,created=convert_candidate(candidate,request.user)
    except ValidationError as e: return render(request,'portal/memo_import.html',{'error':' / '.join(e.messages)},status=400)
    Audit.objects.create(actor=str(request.user.pk),action='candidate_to_draft',target=str(case.pk),reason='중립 요약 검토 후 사건 초안 등록; 원자료 확인 필요')
    return redirect(f'/admin/portal/case/{case.pk}/change/')
