import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class Member(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('이름', max_length=80)
    phone = models.CharField('전화번호', max_length=20)
    active = models.BooleanField('활성', default=True)
    synthetic = models.BooleanField(default=False)
    session_version = models.PositiveIntegerField(default=1)
    label = models.CharField('비민감 구분 표기', max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def save(self,*args,**kwargs):
        if self.pk:
            old = Member.objects.filter(pk=self.pk).first()
            if old and (old.phone != self.phone or old.active != self.active):
                self.session_version = old.session_version + 1
        super().save(*args,**kwargs)
    @property
    def display_label(self):
        if self.label: return self.label
        if Member.objects.filter(name=self.name).exclude(pk=self.pk).exists(): return '교인 '+str(self.pk)[:6]
        return ''
    def __str__(self): return str(self.id)

class Challenge(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    member = models.ForeignKey(Member,on_delete=models.CASCADE,null=True)
    digest = models.CharField(max_length=128)
    version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    used = models.BooleanField(default=False)
    exception = models.BooleanField(default=False)

class RateBucket(models.Model):
    key = models.CharField(max_length=64,unique=True)
    count = models.PositiveIntegerField(default=0)
    start = models.DateTimeField(default=timezone.now)

class Audit(models.Model):
    actor = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=100)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

STATES = [('draft','초안'),('review','검토 중'),('published','게시')]
class Case(models.Model):
    title = models.CharField('제목',max_length=200)
    occurred_on = models.DateField('사건 발생일')
    topic = models.CharField('주제',max_length=100)
    timeline = models.TextField('경과',blank=True)
    facts = models.TextField('확인된 사실',blank=True)
    claims = models.TextField('당사자별 주장',blank=True)
    unknown = models.TextField('미확인 사항',blank=True)
    status = models.TextField('현재 처리 상태',blank=True)
    decisions = models.TextField('결정: 기관·사건번호·결정일·판단 범위·확정 여부',blank=True)
    responses = models.TextField('양측 설명과 반론',blank=True)
    issues = models.TextField('검토 쟁점·추가 확인 자료',blank=True)
    opinion = models.TextField('운영진 의견과 근거',blank=True)
    review_summary = models.TextField('교인 공개 정정·변경 요약 (개인정보 제외)',blank=True)
    state = models.CharField('상태',max_length=20,choices=STATES,default='draft')
    author = models.ForeignKey('auth.User',on_delete=models.PROTECT,related_name='authored_cases')
    reviewer = models.ForeignKey('auth.User',on_delete=models.PROTECT,null=True,blank=True,related_name='reviewed_cases')
    last_editor = models.ForeignKey('auth.User',on_delete=models.PROTECT,null=True,blank=True,related_name='last_edited_cases')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def clean(self):
        if self.state == 'published' and (not self.reviewer_id or self.reviewer_id == self.author_id or self.reviewer_id == self.last_editor_id):
            raise ValidationError('작성자와 다른 게시 승인자가 필요합니다.')
    class Meta:
        permissions = [('publish_case', '사건·자료 게시 승인')]
    def __str__(self): return self.title

class Article(models.Model):
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='articles')
    citation = models.CharField('통합 헌법 편·장·조·항 / 시행규정 구분',max_length=200)
    text = models.TextField('정확한 조문')
    source = models.URLField('총회 공식 원문 URL')
    amendment_source = models.URLField('총회 공식 개정 공고 URL',blank=True)
    effective_on = models.DateField('시행일')
    amended_on = models.DateField('개정일')
    checked_on = models.DateField('확인일')
    applicable = models.BooleanField('사건 당시 적용 확인',default=False)
    verified = models.BooleanField('공식 원문·개정 공고 확인',default=False)
    current_difference = models.TextField('현재 조문과 차이',blank=True)
    relevance = models.TextField('사건 관련 이유')
    def clean(self):
        from urllib.parse import urlparse
        if self.verified:
            for url in (self.source,self.amendment_source):
                parsed=urlparse(url)
                if parsed.scheme!='https' or not (parsed.hostname=='pck.or.kr' or (parsed.hostname or '').endswith('.pck.or.kr')):
                    raise ValidationError('공식 원문과 개정 공고의 총회 HTTPS 출처가 필요합니다.')
            if self.checked_on > timezone.localdate(): raise ValidationError('확인일은 미래일 수 없습니다.')
        if self.applicable and self.effective_on > Case._meta.get_field('occurred_on').to_python(self.case.occurred_on): raise ValidationError('사건일 이후 시행 조문을 소급 적용할 수 없습니다.')
    def __str__(self): return self.citation

class Document(models.Model):
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='documents')
    title = models.CharField('제목',max_length=200)
    original = models.FileField('원본 (관리자 전용)',upload_to='originals/%Y/%m')
    reading = models.FileField('가림 처리 열람본',upload_to='reading/%Y/%m',blank=True)
    source = models.CharField('출처',max_length=300)
    acquired_on = models.DateField('확보일')
    written_on = models.DateField('문서 작성일',null=True,blank=True)
    excerpt = models.TextField('원문/발췌 여부와 범위')
    redaction_reason = models.TextField('가림 이유',blank=True)
    redaction_checked = models.BooleanField('복구 불가능한 가림을 수동 검증함',default=False)
    state = models.CharField('상태',max_length=20,choices=STATES,default='draft')
    def clean(self):
        for f in (self.original,self.reading):
            if f and (not f.name.lower().endswith('.pdf') or f.size > 10*1024*1024):
                raise ValidationError('10MB 이하 PDF만 허용합니다.')
            if f and hasattr(f,'read'):
                f.open(); prefix=f.read(5); f.seek(0)
                if prefix != b'%PDF-': raise ValidationError('PDF 형식이 아닙니다.')
        if self.state == 'published' and (not self.reading or not self.redaction_checked):
            raise ValidationError('열람본과 가림 검증이 필요합니다.')
    def __str__(self): return self.title

class Post(models.Model):
    member = models.ForeignKey(Member,on_delete=models.PROTECT)
    author_name = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    body = models.TextField()
    case = models.ForeignKey(Case,on_delete=models.SET_NULL,null=True,blank=True)
    hidden = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True)
    moderation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited = models.BooleanField(default=False)
    def __str__(self): return self.title

class Revision(models.Model):
    target = models.CharField(max_length=100)
    actor = models.CharField(max_length=100)
    body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class Request(models.Model):
    KINDS = [('report','신고'),('correction','정정'),('response','반론·자료 제출'),('appeal','이의 제기')]
    member = models.ForeignKey(Member,on_delete=models.PROTECT)
    kind = models.CharField(max_length=20,choices=KINDS)
    case = models.ForeignKey(Case,on_delete=models.SET_NULL,null=True,blank=True)
    post = models.ForeignKey(Post,on_delete=models.SET_NULL,null=True,blank=True)
    body = models.TextField('요청 내용')
    response = models.TextField('관리자 답변·처리 사유',blank=True)
    resolved = models.BooleanField('처리 완료',default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class RosterBatch(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    actor = models.ForeignKey('auth.User',on_delete=models.CASCADE)
    rows = models.JSONField()
    summary = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    applied = models.BooleanField(default=False)

class ChangeNote(models.Model):
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='changes')
    summary = models.TextField('공개 정정·변경 요약')
    published_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-published_at']
