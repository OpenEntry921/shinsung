import secrets, datetime, hmac, json, uuid
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.middleware.csrf import rotate_token
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.forms import ModelForm
from .models import *
from .security import phone, digest, limit, send_sms, valid_totp, keyed
from .roster import parse

GENERIC='입력 내용이 명부와 일치하고 발송 가능한 경우 인증번호를 보냅니다. 인증이 어려우면 관리자에게 문의하세요.'
def health(request): return JsonResponse({'status':'ok'})
def policy(request): return render(request,'portal/policy.html',{'operator_name':settings.OPERATOR_NAME,'operator_contact':settings.OPERATOR_CONTACT})
def login(request):
    message=''; devcode=''
    if request.method=='POST':
        message=GENERIC
        name=request.POST.get('name','').strip()[:80]; number=phone(request.POST.get('phone',''))[:20]
        request.session['challenge_id']=str(uuid.uuid4())
        allowed=limit('ip:'+request.META.get('REMOTE_ADDR',''),20,3600)
        if allowed: allowed=limit('phone-hour:'+number,5,3600)
        if allowed: allowed=limit('phone-minute:'+number,1,60)
        members=Member.objects.filter(name=name,phone=number,active=True)
        member=members.first() if members.count()==1 and Member.objects.filter(phone=number,active=True).count()==1 else None
        code=f'{secrets.randbelow(1000000):06d}'
        sent=allowed and member and send_sms(member,code)
        if allowed:
            Challenge.objects.create(id=request.session['challenge_id'],member=member if sent else None,digest=digest(request.session['challenge_id'],code),expires_at=timezone.now()+datetime.timedelta(minutes=5),version=member.session_version if sent else 1)
        if sent and settings.DEV and member.synthetic: devcode=code
    return render(request,'portal/login.html',{'message':message,'devcode':devcode,'development':settings.DEV})

@require_POST
def otp(request):
    error='인증번호를 확인할 수 없습니다. 만료되었거나 사용된 번호일 수 있습니다.'
    with transaction.atomic():
        challenge=Challenge.objects.select_for_update().filter(pk=request.session.get('challenge_id')).first() if request.session.get('challenge_id') else None
        allowed=limit('verify:'+request.META.get('REMOTE_ADDR',''),30,3600)
        if challenge and allowed and not challenge.used and challenge.attempts<5 and challenge.expires_at>timezone.now():
            challenge.attempts+=1
            valid=hmac.compare_digest(challenge.digest,digest(str(challenge.id),request.POST.get('code','')))
            member=challenge.member
            if valid and member and member.active and member.session_version==challenge.version and Member.objects.filter(phone=member.phone,active=True).count()==1 and (not settings.DEV or member.synthetic):
                challenge.used=True; challenge.save(); request.session.flush(); rotate_token(request)
                request.session['member_id']=str(member.id); request.session['member_version']=member.session_version
                request.session['member_auth']='sms'
                request.session.set_expiry(3600)
                return redirect('/')
            challenge.save()
    return render(request,'portal/login.html',{'message':error,'development':settings.DEV},status=400)

@require_POST
def logout(request):
    request.session.flush(); return redirect('/login/')

def admin_mfa(request):
    if not request.user.is_authenticated or not request.user.is_staff: return redirect('/admin/login/')
    error=''
    if request.method=='POST':
        counter=valid_totp(request.POST.get('code',''),request.user.username) if limit('mfa:'+str(request.user.pk),5,300) else False
        if counter is not False and limit('totp:'+str(request.user.pk)+':'+str(counter),1,90):
            request.session['admin_mfa_until']=(timezone.now()+datetime.timedelta(minutes=15)).timestamp(); return redirect('/admin/')
        error='추가 인증을 확인할 수 없습니다. 관리자 TOTP 설정을 확인하세요.'
    return render(request,'portal/mfa.html',{'error':error})

def cases(request):
    return render(request, 'portal/cases.html')


def case_detail(request, pk=None, key=None):
    from django.http import Http404
    if pk is not None and 1 <= pk <= 30:
        key = f'E{pk:02}'
    if key not in {f'E{i:02}' for i in range(1, 31)}:
        raise Http404
    return redirect('/#material-' + key)


def documents(request,pk,kind):
    doc=get_object_or_404(Document,pk=pk)
    if kind=='original':
        if not (request.user.is_authenticated and request.user.has_perm('portal.view_document') and request.session.get('admin_mfa_until',0)>timezone.now().timestamp()): return HttpResponseForbidden()
        file=doc.original
    elif kind=='reading' and request.member and not doc.internal_memo and doc.state=='published' and doc.redaction_checked and Case.objects.filter(Q(documents=doc)|Q(evidence_links__document=doc),state='published').exists(): file=doc.reading
    else: return HttpResponseForbidden()
    if not file: return HttpResponse(status=404)
    extension='docx' if kind=='original' and doc.internal_memo else 'pdf'
    mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document' if extension=='docx' else 'application/pdf'
    return FileResponse(file.open('rb'),as_attachment=True,filename=f'document-{doc.pk}.{extension}',content_type=mime)

def posts(request):
    qs=Post.objects.filter(hidden=False,deleted_at=None).order_by('-created_at')
    q=request.GET.get('q','')[:200]
    if q: qs=qs.filter(Q(title__icontains=q)|Q(body__icontains=q))
    return render(request,'portal/posts.html',{'posts':qs,'q':q})
def post_detail(request,pk):
    post=get_object_or_404(Post,pk=pk,hidden=False,deleted_at=None)
    return render(request,'portal/post.html',{'post':post})
class PostForm(ModelForm):
    class Meta: model=Post; fields=['title','body','case']; labels={'title':'제목','body':'내용','case':'관련 사건'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.fields['case'].queryset=Case.objects.filter(state='published')
def post_edit(request,pk=None):
    post=get_object_or_404(Post,pk=pk,member=request.member,hidden=False,deleted_at=None) if pk else None
    form=PostForm(request.POST or None,instance=post)
    if request.method=='POST' and form.is_valid():
        if not limit('post:'+str(request.member.pk),20,3600): return HttpResponse('작성 요청이 너무 많습니다.',status=429)
        obj=form.save(commit=False)
        if post:
            old=Post.objects.get(pk=post.pk)
            Revision.objects.create(target=f'post:{post.pk}',actor=str(request.member.pk),body={'title':old.title,'body':old.body}); obj.edited=True
        else: obj.member=request.member; obj.author_name=request.member.name
        obj.save(); return redirect('post',pk=obj.pk)
    return render(request,'portal/form.html',{'form':form,'title':'실명 게시글 작성·수정','notice':'교인 전용 게시판에 등록된 실명으로 표시됩니다.'})
@require_POST
def post_delete(request,pk):
    post=get_object_or_404(Post,pk=pk,member=request.member,deleted_at=None)
    post.deleted_at=timezone.now(); post.save(); return redirect('posts')
class RequestForm(ModelForm):
    class Meta: model=Request; fields=['kind','case','post','body']; labels={'kind':'유형','case':'관련 사건','post':'관련 게시글','body':'내용'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.fields['case'].queryset=Case.objects.filter(state='published'); self.fields['post'].queryset=Post.objects.filter(hidden=False,deleted_at=None)
def requests_view(request):
    selected=Case.objects.filter(pk=request.GET.get('case'),state='published').first() if request.GET.get('case','').isdigit() else None
    form=RequestForm(request.POST or None,initial={'case':selected})
    if request.method=='POST' and form.is_valid():
        if not limit('request:'+str(request.member.pk),20,3600): return HttpResponse(status=429)
        obj=form.save(commit=False); obj.member=request.member; obj.save(); return redirect('requests')
    return render(request,'portal/requests.html',{'form':form,'requests':Request.objects.filter(member=request.member).order_by('-created_at')})

def roster(request):
    if not request.user.has_perm('portal.change_member'): return HttpResponseForbidden()
    error=''; batch=None
    if request.method=='POST':
        if 'file' in request.FILES:
            try:
                rows,summary=parse(request.FILES['file']); batch=RosterBatch.objects.create(actor=request.user,rows=rows,summary=summary)
            except Exception: error='명부를 읽을 수 없습니다. XLSX 형식·시트·헤더·파일 크기를 확인하세요.'
        elif request.POST.get('batch'):
            with transaction.atomic():
                batch=get_object_or_404(RosterBatch,pk=request.POST['batch'],actor=request.user,applied=False,created_at__gt=timezone.now()-datetime.timedelta(hours=1))
                assignments=[]; seen=set()
                for row in batch.rows:
                    action=request.POST.get(f'action_{row["row"]}','skip')
                    if action=='skip': continue
                    if row['issue'] or row['duplicate'] or row['ambiguous']: error='문제 행은 수정 후 다시 업로드해야 합니다.'; break
                    if action=='new':
                        if row['existing'] or row['change_candidates']: error='변경 후보는 기존 ID 연결 또는 건너뛰기를 선택하세요.'; break
                        if Member.objects.filter(Q(name=row['name'])|Q(phone=row['phone'])).exists():
                            error='검토 후 일치 후보가 추가되었습니다. 다시 업로드하세요.'; break
                        member=Member(name=row['name'],phone=row['phone'])
                    else:
                        allowed={r['id'] for r in row['change_candidates']}|{row['existing']}
                        if action not in allowed or action in seen: error='연결 대상 확인이 필요합니다.'; break
                        member=get_object_or_404(Member,pk=action)
                        if row.get('baseline',{}).get(action)!=keyed(str(member.id)+':'+str(member.updated_at)):
                            error='검토 후 명부가 변경되었습니다. 다시 업로드하세요.'; break
                        seen.add(action)
                    assignments.append((row,member))
                if not error and request.POST.get('confirmed')=='yes':
                    for row,member in assignments:
                        member.name=row['name']; member.phone=row['phone']; member.save()
                    batch.applied=True; batch.save(); batch.rows=[]; batch.save(update_fields=['rows'])
                    Audit.objects.create(actor=str(request.user.pk),action='roster_apply',target=str(batch.pk),reason='명부 검토 확인; 누락 교인 자동 삭제 없음')
                    return redirect('/admin/portal/member/')
                if not error: error='검토 확인이 필요합니다.'
    return render(request,'portal/roster.html',{'batch':batch,'error':error})

def exception_issue(request):
    if not request.user.has_perm('portal.change_member'): return HttpResponseForbidden()
    token=''; error=''
    if request.method=='POST':
        try: member=Member.objects.filter(pk=uuid.UUID(request.POST.get('member','')),active=True).first()
        except ValueError: member=None
        reason=request.POST.get('reason','').strip()
        if member and reason and request.POST.get('confirmed')=='yes' and (not settings.DEV or member.synthetic):
            code=secrets.token_urlsafe(32)
            challenge=Challenge(member=member,version=member.session_version,expires_at=timezone.now()+datetime.timedelta(minutes=15),exception=True)
            challenge.digest=digest(str(challenge.id),code); challenge.save(); token=f'{challenge.id}:{code}'
            Audit.objects.create(actor=str(request.user.pk),action='exception_issue',target=str(member.pk),reason=reason)
        else: error='활성 교인 ID·별도 신원 확인·사유가 필요합니다.'
    return render(request,'portal/exception_issue.html',{'token':token,'error':error})
def exception_login(request):
    error=''
    if request.method=='POST':
        value=request.POST.get('token','')
        if limit('exception:'+request.META.get('REMOTE_ADDR',''),10,3600):
            try:
                cid,code=value.split(':',1)
                with transaction.atomic():
                    ch=Challenge.objects.select_for_update().filter(pk=cid,exception=True,used=False,expires_at__gt=timezone.now()).first()
                    if ch and ch.attempts<5:
                        ch.attempts+=1; ch.save()
                        if hmac.compare_digest(ch.digest,digest(str(ch.id),code)) and ch.member.active and ch.member.session_version==ch.version and (not settings.DEV or ch.member.synthetic):
                            ch.used=True; ch.save(); request.session.flush(); rotate_token(request); request.session['member_id']=str(ch.member_id); request.session['member_version']=ch.version; request.session['member_auth']='exception'; request.session.set_expiry(3600); return redirect('/')
            except (ValueError,ValidationError): pass
        error='접속 수단을 확인할 수 없습니다.'
    return render(request,'portal/exception.html',{'error':error})
