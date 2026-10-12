import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

def private_original_path(instance,filename):
    return f'originals/{uuid.uuid4().hex}{__import__("pathlib").Path(filename).suffix.lower()}'

def private_reading_path(instance,filename):
    return f'reading/{uuid.uuid4().hex}.pdf'

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
    occurred_on = models.DateField('정확한 발생일',null=True,blank=True)
    occurred_precision = models.CharField('날짜 정확도',max_length=12,choices=[('day','일'),('month','월'),('year','연도'),('period','기간'),('unknown','확인 중')],default='day')
    occurred_year = models.PositiveSmallIntegerField('발생 연도',null=True,blank=True)
    occurred_month = models.PositiveSmallIntegerField('발생 월',null=True,blank=True)
    occurred_until = models.DateField('발생 기간 종료일',null=True,blank=True)
    period_description = models.CharField('불확실한 발생 기간 설명',max_length=120,blank=True)
    overview = models.TextField('사건 개요',blank=True)
    status_as_of = models.DateField('상태 확인 기준일',null=True,blank=True)
    materials_as_of = models.DateField('자료 기준일',null=True,blank=True)
    additional_materials = models.TextField('추가로 필요한 자료',blank=True)
    related_cases = models.ManyToManyField('self',blank=True,symmetrical=False,verbose_name='관련 사건')
    publication_reason = models.TextField('검토·승인 사유',blank=True)
    sources_reviewed = models.BooleanField('출처와 표현의 확정 수준을 확인함',default=False)
    privacy_reviewed = models.BooleanField('본문과 열람 자료의 개인정보 가림을 확인함',default=False)
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
    @property
    def date_label(self):
        if self.occurred_precision=='day' and self.occurred_on: return str(self.occurred_on)
        if self.occurred_precision=='month' and self.occurred_year and self.occurred_month: return f'{self.occurred_year}년 {self.occurred_month}월 (월 단위)'
        if self.occurred_precision=='year' and self.occurred_year: return f'{self.occurred_year}년 (연도 단위)'
        if self.occurred_precision=='period': return self.period_description or f'{self.occurred_on or "확인 중"} ~ {self.occurred_until or "확인 중"}'
        return '발생일 확인 중'
    def date_bounds(self):
        import calendar,datetime
        if self.occurred_precision in ('day','period') and self.occurred_on:
            start=Case._meta.get_field('occurred_on').to_python(self.occurred_on)
            return start,Case._meta.get_field('occurred_until').to_python(self.occurred_until) or start
        if self.occurred_year:
            if self.occurred_month:
                return datetime.date(self.occurred_year,self.occurred_month,1),datetime.date(self.occurred_year,self.occurred_month,calendar.monthrange(self.occurred_year,self.occurred_month)[1])
            return datetime.date(self.occurred_year,1,1),datetime.date(self.occurred_year,12,31)
        return None,None
    def clean(self):
        if self.occurred_precision=='day' and not self.occurred_on: raise ValidationError('정확한 날짜가 없으면 월·연도·기간·확인 중을 선택하세요.')
        if self.occurred_precision=='unknown' and any((self.occurred_on,self.occurred_year,self.occurred_month,self.occurred_until)): raise ValidationError('날짜 정확도와 입력한 날짜를 맞추세요.')
        if self.occurred_precision=='period' and not (self.occurred_on or self.period_description): raise ValidationError('발생 기간 또는 불확실한 기간 설명을 입력하세요.')
        if self.occurred_month and not 1<=self.occurred_month<=12: raise ValidationError('월은 1~12입니다.')
        if self.occurred_year and not 1<=self.occurred_year<=9999: raise ValidationError('연도를 확인하세요.')
        if self.occurred_precision=='month' and (not self.occurred_year or not self.occurred_month or self.occurred_on): raise ValidationError('월 단위 날짜에는 연도·월만 입력하고 임의 발생일을 넣지 마세요.')
        if self.occurred_precision=='year' and (not self.occurred_year or self.occurred_on or self.occurred_month): raise ValidationError('연도만 입력하세요.')
        if self.occurred_until and self.occurred_on and self.occurred_until<self.occurred_on: raise ValidationError('종료일을 확인하세요.')
        if self.state == 'published' and (not self.reviewer_id or self.reviewer_id == self.author_id or self.reviewer_id == self.last_editor_id):
            raise ValidationError('작성자와 다른 게시 승인자가 필요합니다.')
    class Meta:
        permissions = [('publish_case', '사건·자료 게시 승인')]
    def __str__(self): return self.title

class Article(models.Model):
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='articles')
    citation = models.CharField('통합 헌법 편·장·조·항 / 시행규정 구분',max_length=200)
    document_kind = models.CharField('문서 종류',max_length=20,choices=[('constitution','통합 헌법'),('regulation','통합 헌법시행규정')],default='constitution')
    heading = models.CharField('조문 제목',max_length=200,blank=True)
    official_page = models.CharField('공식 원문 페이지',max_length=80,blank=True)
    applicability_status = models.CharField('사건 당시 적용 상태',max_length=12,choices=[('pending','확인 중'),('applicable','적용 확인'),('inapplicable','적용 아님')],default='pending')
    applicability_reason = models.TextField('사건 당시 적용 검증 근거',blank=True)
    related_cases = models.ManyToManyField(Case,blank=True,related_name='linked_articles',through='ArticleCaseLink',verbose_name='추가 관련 사건')
    text = models.TextField('정확한 조문',blank=True)
    source = models.URLField('총회 공식 원문 URL',blank=True)
    amendment_source = models.URLField('총회 공식 개정 공고 URL',blank=True)
    effective_on = models.DateField('시행일',null=True,blank=True)
    amended_on = models.DateField('개정일',null=True,blank=True)
    checked_on = models.DateField('확인일',null=True,blank=True)
    applicable = models.BooleanField('사건 당시 적용 확인',default=False)
    verified = models.BooleanField('공식 원문·개정 공고 확인',default=False)
    current_difference = models.TextField('현재 조문과 차이',blank=True)
    relevance = models.TextField('사건 관련 이유')
    @property
    def source_confirmed(self):
        from urllib.parse import urlparse
        if not self.verified or not all((self.text,self.source,self.amendment_source,self.effective_on,self.amended_on,self.checked_on,self.official_page)): return False
        return all(urlparse(url).scheme=='https' and (urlparse(url).hostname=='pck.or.kr' or (urlparse(url).hostname or '').endswith('.pck.or.kr')) for url in (self.source,self.amendment_source)) and self.checked_on<=timezone.localdate()
    def clean(self):
        from urllib.parse import urlparse
        if self.verified:
            if not all((self.text,self.effective_on,self.amended_on,self.checked_on,self.official_page)): raise ValidationError('검증된 조문에는 본문·페이지·개정·시행·확인일이 필요합니다.')
            for url in (self.source,self.amendment_source):
                parsed=urlparse(url)
                if parsed.scheme!='https' or not (parsed.hostname=='pck.or.kr' or (parsed.hostname or '').endswith('.pck.or.kr')):
                    raise ValidationError('공식 원문과 개정 공고의 총회 HTTPS 출처가 필요합니다.')
            if self.checked_on > timezone.localdate(): raise ValidationError('확인일은 미래일 수 없습니다.')
        if self.applicability_status=='applicable':
            start,_=self.case.date_bounds()
            if not self.verified or not self.applicability_reason or not start or not self.effective_on or self.effective_on>start: raise ValidationError('공식 조문·사건 시점·당시 적용 근거를 먼저 확인하세요.')
    def __str__(self): return self.citation

class Document(models.Model):
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='documents',null=True,blank=True)
    title = models.CharField('제목',max_length=200)
    internal_memo = models.BooleanField('내부 검토 메모 (교인 공개 금지)',default=False)
    original_checked = models.BooleanField('원자료 직접 확인',default=False)
    served_on = models.DateField('송달일',null=True,blank=True)
    decided_on = models.DateField('결정일',null=True,blank=True)
    original = models.FileField('원본 (관리자 전용)',upload_to=private_original_path)
    reading = models.FileField('가림 처리 열람본',upload_to=private_reading_path,blank=True)
    source = models.CharField('출처',max_length=300)
    acquired_on = models.DateField('확보일')
    written_on = models.DateField('문서 작성일',null=True,blank=True)
    excerpt = models.TextField('원문/발췌 여부와 범위')
    redaction_reason = models.TextField('가림 이유',blank=True)
    redaction_checked = models.BooleanField('복구 불가능한 가림을 수동 검증함',default=False)
    state = models.CharField('상태',max_length=20,choices=STATES,default='draft')
    def clean(self):
        from .memo_import import validate_docx
        if self.internal_memo and (self.reading or self.state=='published' or self.original_checked): raise ValidationError('내부 메모는 원자료 확인·열람본·교인 공개가 금지됩니다.')
        for f in (self.original,self.reading):
            if not f: continue
            if f.size>10*1024*1024: raise ValidationError('10MB 이하 자료만 허용합니다.')
            f.open(); prefix=f.read(5); f.seek(0)
            if f==self.original and self.internal_memo:
                if not f.name.lower().endswith('.docx'): raise ValidationError('내부 메모는 DOCX만 허용합니다.')
                validate_docx(f); f.seek(0)
            elif not f.name.lower().endswith('.pdf') or prefix!=b'%PDF-': raise ValidationError('일반 자료는 PDF만 허용합니다.')
        if self.state=='published' and (not self.reading or not self.redaction_checked or not self.source): raise ValidationError('출처·열람본·가림 검증이 필요합니다.')
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

class CaseEvidence(models.Model):
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='evidence_links')
    document = models.ForeignKey(Document,on_delete=models.PROTECT,related_name='case_links')
    locator = models.CharField('페이지·문단·증거번호',max_length=200)
    checked = models.BooleanField('해당 부분을 직접 확인',default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','document','locator'],name='unique_case_evidence')]
    def clean(self):
        if self.checked and (self.document.internal_memo or not self.document.original_checked): raise ValidationError('내부 메모를 검증된 근거로 승격할 수 없습니다. 원자료부터 확인하세요.')
    def __str__(self): return f'{self.document.title} · {self.locator}'

class Decision(models.Model):
    cases = models.ManyToManyField(Case,related_name='official_decisions',verbose_name='관련 사건')
    institution = models.CharField('기관',max_length=200,blank=True)
    case_number = models.CharField('사건번호',max_length=100,blank=True)
    decided_on = models.DateField('결정일',null=True,blank=True)
    served_on = models.DateField('송달일',null=True,blank=True)
    order = models.TextField('주문',blank=True)
    scope = models.TextField('판단 범위',blank=True)
    outcome = models.CharField('결과 유형',max_length=20,choices=[('unknown','확인 중'),('acquitted','무죄'),('not_prosecuted','불기소'),('dismissed','기각'),('excluded','판단 제외'),('other','원문에 따른 기타 판단')],default='unknown')
    appeal_status = models.CharField('상소 여부 (모르면 확인 중)',max_length=200,blank=True)
    finality = models.CharField('확정 여부',max_length=12,choices=[('unknown','확인 중'),('pending','미확정'),('final','확정')],default='unknown')
    document = models.ForeignKey(Document,on_delete=models.PROTECT,null=True,blank=True)
    locator = models.CharField('원문 페이지·문단',max_length=200,blank=True)
    verified = models.BooleanField('원문과 판단 범위 직접 확인',default=False)
    @property
    def source_confirmed(self):
        return bool(self.verified and all((self.institution,self.case_number,self.decided_on,self.order,self.scope,self.locator,self.document_id)) and self.document.original_checked and not self.document.internal_memo)
    def clean(self):
        if self.verified and self.decided_on and self.decided_on>timezone.localdate(): raise ValidationError('결정일이 미래라면 검증된 결정으로 표시할 수 없습니다.')
        if self.verified and (not all((self.institution,self.case_number,self.decided_on,self.order,self.scope,self.locator,self.document_id)) or not self.document.original_checked or self.document.internal_memo): raise ValidationError('공식 판단으로 표시하려면 원자료·기관·번호·결정일·주문·판단 범위·위치를 확인해야 합니다.')
    def __str__(self): return f'{self.institution or "기관 확인 중"} · {self.case_number or "사건번호 확인 중"}'

class CaseStatement(models.Model):
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='statements')
    kind = models.CharField('설명 분류',max_length=20,choices=[('fact','원자료로 확인된 사실'),('decision_fact','해당 결정에서 인정한 사실'),('claim','당사자 주장·반론'),('unknown','미확인 사항'),('opinion','운영진 검토 의견')],default='unknown')
    text = models.TextField('중립적인 설명')
    source_note = models.CharField('출처 설명',max_length=300)
    evidence = models.ForeignKey(CaseEvidence,on_delete=models.PROTECT,null=True,blank=True)
    supporting_evidence = models.ManyToManyField(CaseEvidence,blank=True,related_name='supported_statements')
    decision = models.ForeignKey(Decision,on_delete=models.PROTECT,null=True,blank=True)
    occurred_on = models.DateField('정확한 경과일',null=True,blank=True)
    date_description = models.CharField('월 단위·불확실한 경과일 표기',max_length=100,blank=True)
    position = models.PositiveIntegerField('경과 순서',default=0)
    class Meta: ordering=['position','id']
    def clean(self):
        if self.pk and self.supporting_evidence.exclude(case_id=self.case_id).exists(): raise ValidationError('추가 근거도 같은 사건에 연결된 자료를 선택하세요.')
        if self.evidence_id and self.evidence.case_id!=self.case_id: raise ValidationError('같은 사건의 근거를 연결하세요.')
        if self.kind in ('fact','decision_fact') and (not self.evidence_id or not self.evidence.checked or not self.evidence.document.original_checked or self.evidence.document.internal_memo): raise ValidationError('확인된 사실에는 직접 확인한 원자료와 해당 위치가 필요합니다.')
        if self.kind=='decision_fact' and (not self.decision_id or not self.decision.source_confirmed or not self.decision.cases.filter(pk=self.case_id).exists()): raise ValidationError('결정에서 인정한 사실은 검증된 해당 결정을 연결하세요.')

class MemoImport(models.Model):
    document = models.ForeignKey(Document,on_delete=models.PROTECT,related_name='imports')
    digest = models.CharField(max_length=64,unique=True,editable=False)
    excluded_blocks = models.PositiveIntegerField('전략·목표 등 제외 블록 수',default=0)
    unclassified_blocks = models.PositiveIntegerField('분류되지 않아 수동 검토할 블록 수',default=0)
    basis_on = models.DateField('메모 기준일',default=__import__('datetime').date(2026,9,19))
    author = models.ForeignKey('auth.User',on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class ImportCandidate(models.Model):
    batch = models.ForeignKey(MemoImport,on_delete=models.CASCADE,related_name='candidates')
    key = models.CharField(max_length=64,editable=False)
    topic = models.CharField('쟁점 분류',max_length=100)
    title = models.CharField('검토한 중립 제목',max_length=200)
    internal_excerpt = models.TextField('내부 메모 발췌 (관리자 전용)')
    source_locator = models.TextField('메모 위치')
    neutral_summary = models.TextField('중립 요약 (관리자 작성)',blank=True)
    required_originals = models.TextField('필요한 원자료')
    article_hints = models.TextField('조문 확인 후보 (본문 아님)',blank=True)
    date_candidates = models.JSONField('메모의 날짜 후보 (원자료 검증 전)',default=list,blank=True)
    occurred_precision = models.CharField('검토한 날짜 정확도',max_length=12,choices=Case._meta.get_field('occurred_precision').choices,default='unknown')
    occurred_on = models.DateField('검토한 정확한 발생일',null=True,blank=True)
    occurred_year = models.PositiveSmallIntegerField('검토한 발생 연도',null=True,blank=True)
    occurred_month = models.PositiveSmallIntegerField('검토한 발생 월',null=True,blank=True)
    occurred_until = models.DateField('검토한 기간 종료일',null=True,blank=True)
    period_description = models.CharField('검토한 발생 기간',max_length=120,blank=True)
    reviewed = models.BooleanField('전략·개인정보 제외 및 사실/의견 분리 확인',default=False)
    case = models.OneToOneField(Case,on_delete=models.PROTECT,null=True,blank=True)
    state = models.CharField(max_length=20,choices=[('draft','초안'),('excluded','제외'),('converted','사건 초안 등록')],default='draft')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['batch','key'],name='unique_import_candidate')]


class ArticleCaseLink(models.Model):
    article = models.ForeignKey(Article,on_delete=models.CASCADE,related_name='case_applications')
    case = models.ForeignKey(Case,on_delete=models.CASCADE,related_name='article_links')
    relevance = models.TextField('이 사건과 관련되는 이유',blank=True)
    applicability_status = models.CharField('이 사건 당시 적용 상태',max_length=12,choices=Article._meta.get_field('applicability_status').choices,default='pending')
    applicability_reason = models.TextField('이 사건 당시 적용 검증 근거',blank=True)
    current_difference = models.TextField('당시 조문과 현재 조문 차이',blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['article','case'],name='unique_article_case_application')]
    def clean(self):
        if self.case_id==self.article.case_id: raise ValidationError('기본 사건의 적용 정보는 조문 본체에서 관리하세요.')
        if self.applicability_status=='applicable':
            start,_=self.case.date_bounds()
            if not self.article.verified or not start or not self.article.effective_on or self.article.effective_on>start or not self.applicability_reason: raise ValidationError('공유 조문도 이 사건의 시점과 적용 근거를 별도로 검증하세요.')
