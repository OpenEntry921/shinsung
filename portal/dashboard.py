"""Versioned editorial defaults supplement, never write or replace published operator records."""
from datetime import date
from .models import ProgressRecord
from .reading_registry import reading_entries, legacy_reading_entries
from .timeline_revision import KEY_BY_NUMBER

EDITED_ON=date(2026,11,6)
BASIS=date(2026,11,4)
# Category, stable editorial ID, title, explanation, classification, status, display numbers, sources, basis.
DEFAULTS=(
 ('update','reasons','기소위원 사건 각하 이유·처리 기록 통지 청구','성도 측은 2026.10.28 각하 이유, 인정사실과 적용조항, 참석위원·의결결과, 기간 연장과 발송 경위 등을 요청했습니다. 자료에서 청구는 확인되지만 이후의 구체적인 회신은 별도로 확인해야 합니다.','자료에 기재된 기록','청구 기록 확인 / 회신 자료 확인 필요',(70,66,68),('C04','C05'),date(2026,10,28)),
 ('update','costs','예납 재판비용 200만 원 반환 청구','성도 측은 2026.10.30 예납금 반환 또는 반환하지 않는 근거의 서면 설명을 요청했습니다. 청구와 실제 환급·거절은 구분합니다.','자료에 기재된 기록','청구 기록 확인 / 처리 결과 확인 필요',(71,),('C06',),date(2026,10,30)),
 ('update','petition','노회원 대상 호소와 총회 제출용 탄원 준비','10월 호소문과 총회 제출용 탄원 준비는 서로 다른 문서·절차입니다. 총회 탄원은 정리본에 준비 중으로 기재돼 있으며 제출·접수와 최종 서명 인원은 추가 자료로 확인해야 합니다.','자료에 기재된 기록','호소문 자료 확인 / 총회 탄원 접수 확인 필요',(69,27,72),('E01','S01'),BASIS),
 ('issue','judgment','정직 2년 판단의 근거와 상고 범위','노회 판결의 유죄 부분과 무죄·기간도과 부분을 구분해 확인합니다. 상고 여부·범위·현재 진행 상태는 정리본의 설명과 실제 접수 문서를 구분해야 합니다.','우리의 검토 쟁점','원자료·최신 진행 확인 필요',(63,60,64,65),('A12','S01'),BASIS),
 ('issue','finance','재정 인수인계와 실제 권한','회계 선정, 자료·금융업무 인수인계 요구, 계좌·인증수단 변경을 연결해 실제 결정권과 협의 경과를 확인합니다.','우리의 검토 쟁점','기록 대조 필요',(39,40,42,49),('A06','A11','C01'),BASIS),
 ('issue','minister','전도사 사임·해임 사유 공개와 소명 기회','공개된 사유, 당사자의 반박 기회, 목적헌금 실제 지출과 후속 판결 내용을 대조합니다. 목사 사건의 판단을 전도사 개인에 대한 판결로 확대하지 않습니다.','우리의 검토 쟁점','인사·소명 원자료 확인 필요',(18,4,5,64),('A01','B01','A12'),BASIS),
 ('request','approval','목사와 장로에게 같은 승인·결의 기준을 적용했는가','각 사건의 승인 권한·안건·의결 내용과 기록을 대조하는 질의안을 검토합니다. 실제 발송 기록은 확인되지 않았습니다.','앞으로 할 일 · 질의안','질의안·검토 중 (미전달)',(8,17,54),('B01','D01','S01'),BASIS),
 ('request','tax','당회 반대와 세금 이의신청의 직권남용 판단을 연결한 근거는 무엇인가','대표권·앞선 불복 추진 결의·별도 승인 필요성의 설명을 요청하는 질의안입니다. 실제 발송 기록은 확인되지 않았습니다.','앞으로 할 일 · 질의안','질의안·검토 중 (미전달)',(13,11,25,64),('A01','A12'),BASIS),
 ('request','disclosure','전도사 관련 공개 사유는 어떻게 검증했고 어떤 소명 기회를 제공했는가','공개 사유별 증거·확인 주체·당사자 소명 절차에 관한 질의안을 검토합니다. 실제 발송 기록은 확인되지 않았습니다.','앞으로 할 일 · 질의안','질의안·검토 중 (미전달)',(18,5),('B01','A12'),BASIS),
 ('request','recusal','기소위원 사건의 조사·판단 주체와 제척 처리 경과를 확인할 수 있는가','조사·판단 참여자와 제척 처리 근거를 확인하는 질의안을 검토합니다. 실제 발송 기록은 확인되지 않았습니다.','앞으로 할 일 · 질의안','질의안·검토 중 (미전달)',(58,57,59,66,70),('C02','C04','C05'),BASIS),
 ('response','reasons','각하 이유 통지 청구 후속 회신','제공 자료에서 이후 회신을 확인하지 못했습니다. 추가 문서 확인 후 갱신합니다. 답변이 없다는 사정만으로 잘못을 인정했다고 보지 않습니다.','확인되지 않은 진행','회신 자료 확인 필요',(70,66,68),('C05','C04'),date(2026,10,28)),
 ('response','costs','예납금 반환 청구 처리 결과','제공 자료에서 이후 회신을 확인하지 못했습니다. 추가 문서 확인 후 갱신합니다. 청구, 답변 수령과 실제 환급·이행 확인을 구분합니다.','확인되지 않은 진행','처리·환급 자료 확인 필요',(71,),('C06',),date(2026,10,30)),
 ('response','appeal','상고 진행 확인','제공 자료에서 이후 회신을 확인하지 못했습니다. 추가 문서 확인 후 갱신합니다. 정리본 기재와 실제 상고 접수·진행 문서를 구분합니다.','확인되지 않은 진행','접수·진행 원자료 확인 필요',(65,63,64),('S01','A12'),BASIS),
 ('week','agenda','다음 모임 검토 안건','72개 사건의 사실관계·의견·원문 링크 검토\n18번 전도사 관련 공개 발언과 소명 절차 확인\n정직 판결·기소장 변경·상고 관련 문서 확인\n공식 질의안의 우선순위와 실제 전달 방법 논의\n토요일 오후 7시 안내에 대응하는 최신 날짜·공지·장소를 확인하지 못해 모임 일정을 확정하지 않습니다.','앞으로 할 일 · 검토 안건','일정 미확인 / 다음 모임 검토 안건',(18,60,63,65),('A12','S01'),BASIS),
)


def dashboard_groups():
    entries={entry['key']:{**entry,'number':entry.get('number',entry['key'])} for entry in [*reading_entries(),*legacy_reading_entries()]}
    published=list(ProgressRecord.objects.filter(published=True).order_by('-basis_on','-updated_at','-pk'))
    result=[]
    for category,label in ProgressRecord.CATEGORIES:
        records=[r for r in published if r.category==category]
        items=[]
        for record in records:
            entry=entries.get(record.reading_key)
            items.append(dict(id='db-'+str(record.pk),title=record.title,public_text=record.public_text,
                classification='운영 게시 기록',status_text=record.get_status_display(),basis_on=record.basis_on,
                updated_at=record.updated_at,recipient=record.recipient,delivered_on=record.delivered_on,
                reply_requested_on=record.reply_requested_on,rule_deadline=record.rule_deadline,
                related=[entry] if entry else [],sources=[],is_default=False))
        for kind,key,title,body,classification,status,numbers,codes,basis in DEFAULTS:
            if kind!=category:continue
            related=[entries[KEY_BY_NUMBER[n]] for n in numbers]
            primary=related[0]['key']
            # An operator can supersede a default by its primary event or exact title.
            if any(r.title==title or r.reading_key==primary or (kind=='week' and not r.reading_key) for r in records):continue
            refs=[]
            for code in codes:
                reference=next((ref for entry in related for ref in entry.get('source_references',[]) if ref['code']==code),None)
                if reference:refs.append(reference)
                else:refs.append(dict(code=code,locator='추가 확인 필요'))
            items.append(dict(id='default-'+kind+'-'+key,title=title,public_text=body,classification=classification,
                status_text=status,basis_on=basis,edited_on=EDITED_ON,related=related,sources=refs,is_default=True))
        result.append((label,items))
    return result
