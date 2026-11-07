"""Build a private, immutable comparison snapshot; never rewrites the timeline.

Usage: python scripts/build_preparation_snapshot.py --review /path/to/review.md
       --source-commit <reviewed-main-commit>
The review report is a secondary source. It does not replace appeal originals.
"""
import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ''.join(child.text() if isinstance(child, Node) else child for child in self.children).strip()

    def find(self, predicate):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if predicate(child):
                    result.append(child)
                result.extend(child.find(predicate))
        return result


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'br', 'hr', 'img', 'input', 'meta', 'link'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, value):
        self.stack[-1].children.append(value)


# Concrete preparation tasks and conditional argument proposals, by DISPLAY
# number, never by stable key. These are new working suggestions, not evidence.
PLANS = {
1: ('도입·예산 결의 원문, 승인 당시 도면·설명자료, 위험 경고 전체와 답변, 운영·시정 사진. 각 주체의 승인 범위와 위험 인식 후 조치를 입증한다.', '공동 승인과 개별 집행·감독 책임을 함께 살펴야 한다는 논리를 유지한다. 당시 경고를 포함한 전체 기록으로 누가 무엇을 승인·집행·시정했는지 제시한다.'),
2: ('해당 날짜 주보, 예배 순서·직무 배정, 출석과 불참 사유를 확인할 기록. 불기소 이유 통지서를 함께 확보한다.', '불기소 결과를 정확히 전제하고, 예배 직무의 실제 이행과 설명 책임을 같은 기준으로 묻는다.'),
3: ('변경 전후 작업지시서·견적, 건축위원회 결의, 감독관 확인서와 동시기 연락, 고소인별 수신·인지 기록. 승인·지시·금액·인지 시점을 분리한다.', '협의·승인 자료와 주장 금액의 변화에 대한 설명을 요구한다. 기간 문제와 실제 승인 여부의 주장은 각각의 자료로 뒷받침한다.'),
4: ('헌금자 각각의 진술, 봉투·당시 메시지, 두 차례 입금과 지정 목적 기록, 목적 변경 동의 자료. 헌금일과 지정 목적을 구분한다.', '헌금 목적과 실제 사용을 중심에 두되, 가족 전체의 의사가 같았다는 추정 대신 헌금자별 기록을 제시한다.'),
5: ('9.23 통화·메시지, 9.24 은행 이체 내역, 기존 11.7 표기의 출처, 업체별 지급·영수증, 집행 승인, 인사 통보·소명 자료.', '사용처 확인과 집행 권한을 함께 설명한다. 이체일은 원자료로 확정하고, 목적헌금과 인사 조치의 인과는 별도 기록으로 제시한다.'),
6: ('법률자문 원본과 작성일·질의 내용, 영업신고, 실제 운영 면적과 공간 구획, 지방세 결정 이유. 자문 시점과 검토 범위를 입증한다.', '검토·신고를 거친 경위는 유지하되, 도입 전 검토와 이후 자문, 식품위생과 지방세 판단을 구분해 설명한다.'),
7: ('4층 공사 안건의 회의록·전체 녹취, 견적 송부, 후속 결의·발주 기록. 조건부 논의와 최종 승인을 대조한다.', '공사 승인 범위와 재결의 조건을 원문으로 확인한 뒤, 실제 집행이 그 조건을 충족했는지 묻는다.'),
8: ('S01이 인용한 총회 제출 요약서, 단체대화방 전체, 견적·건축위원회·당회 기록, 결의 권한의 근거.', '공사와 담당자 교체의 권한 차이를 확인하면서, 논의·인지·동의·정식 의결을 구분하는 동일 기준을 요구한다.'),
9: ('공사 전 예산·위임·승인 기록, 계약·발주일, 공사 완료일과 제직회 보고 원문.', '사후 보고와 사전 승인 여부를 구분하고, 기존 위임이 있었다면 그 범위와 한도까지 검증한다.'),
10: ('과세결정 이유·산출표, 실제 공간 사용, 위험 경고 이후 조치, 행위자별 지시·보고 기록.', '추징과 사적 착복을 구별하는 논리를 유지하고, 추징 원인에 대한 개인별 관여와 감독 대응을 따로 제시한다.'),
11: ('회의록 판본별 원본, 녹취, 작성·확인·배포 경위, 변조 불인정 판단의 해당 부분.', '문언 차이와 고의 변조를 구분하고, 해당 판단이 인정한 범위 안에서 기록의 신뢰성을 논한다.'),
12: ('월별 보고서, 통장·원증빙 요청 목록, 제출·수령 기록, 미제출 사유와 대체자료.', '월별 보고가 있었다는 사실과 요구된 원자료를 충분히 제출했는지를 각각 설명한다.'),
13: ('기존 불복 결의 원문, 후속 이의신청 위임·의결, 대표 권한, 명의·비용, 원심 판단 이유.', '세금 감소 목적과 절차상 권한을 모두 제시해, 어떤 행위가 실제 승인 범위를 벗어났다는 것인지 구체적으로 다툰다.'),
14: ('감사 보고서·발언 원문, 당시 확인한 증빙, 공개·전달 범위와 정정 요청·답변.', '적정한 감사 지적과 근거를 넘는 비난을 구별하고, 실제 표현과 확인 시점을 근거로 설명을 요구한다.'),
15: ('3.29 전체 안건·표결·녹취, 기존 부담 의무, 이후 결의·집행과 비용 내역.', '교회 부담안 부결과 카페 부담 결의의 문언 차이를 유지하면서, 전체 의결과 기존 의무까지 연결해 설명한다.'),
16: ('개별 소집 요구·요구자 수·도달일·안건, 회신·대안 일정, 실제 개최와 안건 처리 기록.', '개최 횟수와 특정 소집 요구에 대한 응답을 구분해, 요구자와 의장의 실제 조치를 비교한다.'),
17: ('세무 담당 최초 선임 결의·계약, 해지·교체 권한과 위임, 통보·인수인계 기록.', '다른 사건과의 형평성 지적에 더해, 담당자 교체 자체의 권한과 절차를 독립적으로 설명한다.'),
18: ('발언 전체 녹음, 10.25 정책당회·12.1 속회 원문, 인사 사유별 증거·소명, 실제 통보, 원심 해당 판단.', '연임 반대 사실과 동기 평가는 구분한다. 목적헌금의 영향은 인사 결정 경위와 당사자 소명으로 검증한다.'),
19: ('4.27 회의록 이후 협의·위임·당회 결정, 1,200만 원 예산, 계약서·미입금·취소 기록, 5.18 표결 원문.', '예산·계약 권한·효력·지급을 나눠 제시하고, 재협의 요구 이후 어떤 절차가 이행됐는지 설명한다.'),
20: ('비상재정조치권 발언 전체 녹취, 근거 규정·위임·예비비 결의, 제직회 공지·안건·표결.', '발언의 정확한 뜻과 권한 근거를 밝히고, 제직회 재정 권한과 인사·감독 사안의 범위를 나눠 설명한다.'),
21: ('공개당회 전환 제안·표결·녹취, 적용 절차, 원심의 해당 판단 이유.', '알 권리의 필요성과 전환 절차의 적정성을 각각 설명하며, 원심 판단과 다투는 부분을 특정한다.'),
22: ('지급 요청·거절 사유·예산·결재선, 실제 사비 지출 영수증과 정산 여부.', '해당 지급 사례의 결정 구조를 구체적으로 제시하고, 이를 전체 재정 통제 구조로 일반화하지 않는다.'),
23: ('대표기도 원영상·전체 발언과 전후 맥락, 특정 대상·내용을 확인할 기록.', '정확한 발언과 지칭 대상을 먼저 제시하고, 평가와 확인된 행위를 구분해 문제를 제기한다.'),
24: ('고소장 원본·접수, 혐의별 기소·불기소·원심 결과·상고 범위 대응표.', '고소 사실과 인정된 사실을 구분하면서, 판단 결과가 최초 의혹과 어떻게 다른지 항목별로 비교한다.'),
25: ('당회·제직회 결의 순서와 원문, 불복 명의·권한·비용·기간, 관련 위임 기록.', '불복의 목적과 각 기관의 결의·대표 권한을 연결해 실제 승인 범위를 제시한다.'),
26: ('안건 상정 요청·도달·회신, 당회 전체 녹취, 의장 진행과 요구자 조치.', '안건 미처리가 누구의 어떤 행위에서 발생했는지 기록으로 나눠 책임을 묻는다.'),
27: ('서명 원본과 집계일·중복 제거 기준, 출석 수 근거. 공유본은 직접 개인정보를 가린다.', '성도들의 문제의식과 공동체 영향을 제시하되, 인원수와 개별 혐의의 입증은 구분한다.'),
28: ('발언 원영상·전후 맥락, 특정 상대와 청취 경위, 기소·변경·판단 상태.', '발언을 정확히 제시하고, 부적절성에 대한 의견과 확정된 판단을 구분한다.'),
29: ('1·2차 기소장, 재판국 제출·접수·사건 계속·변경 허가·송달 기록.', '작성·카톡 통보와 재판국 접수·계속을 구분하고, 실제 중복 심리인지 기록으로 다툰다.'),
30: ('성도 측 고소장과 접수, 고소인 명단의 집계 근거, 탄원·서명과 별도 구분표.', '고소의 구체적 사실과 근거를 중심으로 독립 심사를 요구하고, 고소인 수를 다른 참여 인원과 섞지 않는다.'),
31: ('사역실행위원회 안건별 회의록, 제안→적법 기관 승인→실제 집행 대응표.', '위원회의 필요성과 실제 권한 행사를 구분하고, 안건별 승인·집행 경로를 제시한다.'),
32: ('재정 공개 요청과 회신, 공개·미공개 범위, 양측에 적용한 증빙·열람 기준.', '양측 재정에 같은 검증 기준을 적용하고, 미공개 자체를 자금 유용의 증명으로 삼지 않는다.'),
33: ('제직 임명·보류 사유, 회계 선출 전체 표결·녹취, 의장의 무효 선언과 근거.', '임명·회계 선출·표결 효력을 구분해 각각의 권한과 결정 과정을 검증한다.'),
34: ('대상자별 자격·임명 권한·보류 사유, 요구서 도달·회신, 관련 결의.', '보류의 사유와 절차를 개별 대상별로 확인하고, 임명 권한에 상응하는 설명을 요구한다.'),
35: ('출석요구·출석·조사조서·서면 소명, 새 사실의 고지와 답변 기회 기록.', '실제로 있었던 조사를 인정한 상태에서, 새 기소 사실에 대한 소명 기회의 공백을 구체적으로 지적한다.'),
36: ('고소 접수·위원회 송부·연장·중지·요청서 수령 기록과 당시 시행 규정.', '기간을 단계별로 계산하고, 실제 위반한 기한과 방어에 미친 영향을 특정한다.'),
37: ('2.11 작성 문서·3.10 실제 제출·접수, 변경 허가·고지·답변 기록.', '작성일과 제출일을 구분하고, 양측 기소장 변경에 같은 기준을 적용한다.'),
38: ('최초 조사조서·출석요구서·출석과 송달 기록, 후속 고소장 기재.', '후속 문서의 설명을 원기록과 대조해 실제 조사 시점·범위를 특정한다.'),
39: ('회계 선정 표결 전체·기존 표결 효력, 업무 배분·결재체계 변경 결의.', '선정권과 업무·결재체계 변경 권한을 각각의 근거로 설명한다.'),
40: ('헌법해석 원문·질의 내용·적용 시점, 회계 선출·표결 무효화 관련 전체 문구.', '유리한 선정권 해석과 의장 단독 무효화에 관한 제한을 함께 적용해 일관된 기준을 제시한다.'),
41: ('기사 원문·게시일·정정 이력, 확인 가능한 작성·제보 경위. 작성자 추정과 확인 사실을 구별한다.', '기사의 확인된 문구와 사실관계를 검증하고, 작성·제보 주체에 관한 추정을 사실로 기재하지 않는다.'),
42: ('네 차례 내용증명 원본·도달증명·요구 범위·회신·실제 이행·대안.', '실제 인계 거부와 그 범위를 입증하고, 그 사실과 이후 조치의 권한 근거를 구분한다.'),
43: ('소집 공지·안건, 실제 제직회 녹취·결의, 추가 안건 처리 권한·집행 기록.', '공지와 실제 결정의 차이를 밝히고, 추가 안건 처리와 집행 권한을 각각 검증한다.'),
44: ('같은 날 처분된 각 사건의 혐의·증거·절차·판단 이유 비교표.', '처분 시점의 대비에 더해 실질적으로 같은 사안에 다른 기준이 적용됐는지 구체적으로 입증한다.'),
45: ('기도 시정 요구, 예배직무 제한 통지·결의·근거 규정·이행 기록.', '기도 내용에 대한 시정 요구와 직무 제한의 권한·절차를 따로 검증한다.'),
46: ('최초 통지·첨부 목록, 보완 요청·발송·수령 기록. 누락 문서와 지연 기간을 특정한다.', '어떤 이유·증거가 언제까지 제공되지 않았고 대응에 어떤 영향을 주었는지 구체화한다.'),
47: ('재항고장 판본·실제 접수증, 이유서 수령·보완 제출 기록.', '작성·접수·수령·보완 날짜를 나눠 실제 대응 경과를 정확히 설명한다.'),
48: ('장로 사건 혐의별 불기소 이유·예외 기소·처분 상태와 목사 사건 판단 대응표.', '양측의 유리·불리한 결과와 판단 이유를 같은 기준으로 소개하고 개별 쟁점을 다툰다.'),
49: ('인계 요구·회신, 은행 OTP·인증서 변경 신청·권한·결의, 자금 사용과 결재 변화.', '인계 거부와 변경 필요성을 설명하면서, 변경의 권한 근거·범위·견제 구조도 제시한다.'),
50: ('직무 제한 통지·권한 근거, 현장 원영상·당사자 진술·발언 맥락.', '제한 통보와 현장 충돌을 행위자별로 나눠 검토하고 서로의 책임을 상쇄하는 근거로 쓰지 않는다.'),
51: ('목사 측 답변서의 주장별 증빙, 원심이 채택·배척한 이유, 후속 반박 자료.', '답변서의 주장을 원자료로 뒷받침하고, 원심이 배척한 부분에는 별도의 근거로 답한다.'),
52: ('기소위원별 업무분장·조사·심의·의결·서명 참여 기록, 고소장·실제 처리 상태.', '위원별 구체적 관여와 이해충돌을 입증하고, 고소된 사실만으로 위법을 확정하지 않는다.'),
53: ('7.13 문서의 원본·개정본·접수·배포 이력, 10월 사실 추가 경위, 죄과별 행위 대응표.', '판본 변화와 실제 추가 사실을 확인하고, 중복 사실과 복수 죄과 평가의 쟁점을 구분한다.'),
54: ('경찰용 고발장 판본·접수증·처분, 업체 등록·계약·실제 업무 자료.', '작성·접수·수사·판단 상태를 나눠 표시하고 업체 관련 의혹은 확보한 자료 범위에서 제기한다.'),
55: ('최초·보완·정정·상고 문서의 날짜별 주장·금액·근거 비교표.', '과거 주장의 문제를 기록으로 남기면서 현재 보완된 주장의 가장 강한 형태에도 구체적으로 답한다.'),
56: ('출석 요구, 공정성 이의·회신·불출석 사유, 대체 소명 제안·제출 기록.', '공정성 문제와 조사 대응 경위를 함께 제시하고, 실제 방어 기회를 확보하려 한 조치를 설명한다.'),
57: ('제척·기피 신청서·개별 사유, 해당 규정·준용 관계·판단 주체·회신.', '자동 제척이라는 단정 대신 위원별 사유와 실제 심리·참여 기록으로 문제를 제기한다.'),
58: ('통지 명의·서명, 안건별 실제 심의·의결 참여자와 회피 여부 기록.', '문서 서명과 실질 판단 참여를 구분해 자기 사건 관여 여부를 구체적으로 확인한다.'),
59: ('제척 신청과 기피 제한을 적용한 실제 회신, 해당 조문·해석·이유.', '서로 다른 제도를 어떻게 적용했는지 원문으로 대조하고 적용 오류를 특정한다.'),
60: ('기소장 변경 전후, 허가·고지·송달, 추가 사실별 조사·답변 기회와 기간.', '사실 동일성과 실질 방어 기회를 기준으로 변경 절차의 문제를 구체적으로 주장한다.'),
61: ('교회 존립 우려 문구가 포함된 결정 전문·주문·증거 판단, 심의 근거.', '공동체 우려가 판단에서 수행한 역할을 확인하고 구체적인 사실·이유의 공백을 지적한다.'),
62: ('이전 목회자별 재임·퇴임 시점과 사유, 당사자 진술·당시 결의, 동일 행위자 여부.', '네 번째 갈등이라는 경과와 앞선 퇴임의 부당성 주장을 구별하고 반복 구조를 기록으로 입증한다.'),
63: ('원심 유죄 항목·양형 이유, 시정·회복·감독 협조 자료와 실제 목회 공백 영향.', '유죄 판단을 다투는 근거와 별개로 공동체 영향·시정·개인 이익 여부 등 처분의 적정성을 설명한다.'),
64: ('원심 항목별 주문·이유, 기간도과·실체 판단, 양측 상고 범위·반대 증거 대응표.', '일부 무죄의 의미를 정확히 유지하고 상고가 실제로 다투는 사실·권한·절차에 항목별로 답한다.'),
65: ('기소위원장 측·목사 측 상고장·접수증·이유서·실제 송달 기록과 사건번호.', '당사자별 상고와 송달 상태를 각각 확인하고 준비·제출·접수를 구분한다.'),
66: ('각하·혐의 없음 등의 이유 통지 전문, 실제 의결자·심의 참여 기록.', '처분 명칭과 판단 범위를 정확히 구분하고 이유와 심의 절차에 대한 설명을 요구한다.'),
67: ('장로 사건 변경 전후 기소장, 허가·송달·답변 기회 기록.', '양측 사건의 변경에 동일성·고지·방어 기회라는 같은 기준을 적용한다.'),
68: ('접수·송부·연장·결정·작성·발송·수령 자료와 당시 적용 기한.', '기간을 단계별로 검증하고 실제 지연과 그 영향을 근거로 문제를 제기한다.'),
69: ('호소문 문장별 근거, 1·2차 기소 접수·조사 기록, 원심의 반대 판단·이유.', '호소의 핵심 문제의식은 보존하고, 조사·중복·기간 관련 표현은 실제 기록으로 정밀하게 뒷받침한다.'),
70: ('이유·참여자·기록 공개 요구서와 접수·회신, 제공 범위와 제한 근거.', '무엇을 요청했고 어떤 답을 받았는지 공개해 미해결 설명 요구를 구체적으로 제시한다.'),
71: ('예납금 영수증·적용 비용 규정·실제 집행·정산·반환 요구와 회신.', '반환 여부와 금액은 적용 규정과 실제 비용·정산 자료로 다툰다.'),
72: ('탄원 초안·서명 집계·제출 여부·접수증. 앞선 호소문·탄원과 별도로 구분한다.', '현재 확인된 준비·제출·접수 상태를 정확히 표시하고 요구 사항과 근거를 구체화한다.'),
}


GROUPS = {
    'A': [1, 6, 10, 12, 13, 25, 55, 64], 'B': [1, 6, 10, 19],
    'C': [12, 55, 64], 'D': [3], 'E': [4, 5, 14, 18, 64],
    'F': [5, 18], 'G': [19], 'H': [15, 20],
    'I': [33, 39, 40, 42, 49], 'J': [31, 60, 64],
    'K': [16, 26, 63], 'L': [18], 'M': [11, 13, 25],
}


def build(review_text, source, commit, review_name):
    parser = TreeParser()
    parser.feed(re.sub(r'{%.*?%}|{{.*?}}|{#.*?#}', '', source, flags=re.S))
    articles = parser.root.find(lambda node: node.tag == 'article' and node.attrs.get('data-key'))
    checks = {int(number): (label.strip(), note.strip()) for number, label, note in
              re.findall(r'^\| (\d{2}) \| ([^|]+) \| ([^|]+) \|$', review_text, re.M)}
    groups = {}
    for letter, content in re.findall(r'^### ([A-M])\. (.*?)(?=^### |^## |\Z)', review_text, re.M | re.S):
        title, _, body = content.partition('\n')
        pages = re.search(r'상고 PDF ([^\n]+)', body)
        paragraphs = [paragraph.strip() for paragraph in body.strip().split('\n\n')]
        # Report text is explicitly marked secondary. Keep the full relevant
        # analysis available, including qualifications and competing evidence.
        groups[letter] = {'title': title, 'body': '\n\n'.join(paragraphs),
                          'pages': pages.group(1).strip() if pages else '쪽수 원문 대조 필요'}
    entries = []
    for article in articles:
        number = int(article.attrs['data-number'])
        key = article.attrs['data-key']
        background = next(node.text() for node in article.find(lambda node: node.attrs.get('data-content') == '경과'))
        sources = article.find(lambda node: node.tag == 'p' and node.attrs.get('class') == 'source-original')
        opinions = article.find(lambda node: 'opinion-draft' in node.attrs.get('class', '').split() and node.attrs.get('data-opinion'))
        if len(opinions) != 1:
            raise ValueError(f'Expected exactly one original opinion: {key}')
        paragraphs = [node.text() for node in opinions[0].find(lambda node: node.tag == 'p')]
        opinion = '\n\n'.join(paragraphs)
        title = re.sub(r'^제목\s*:\s*', '', paragraphs[0])
        selected = [groups[letter] for letter, numbers in GROUPS.items() if number in numbers]
        appeal = '\n\n'.join(group['title'] + '\n' + group['body'] for group in selected)
        claim = '\n'.join(part.strip() for part in re.split(r'(?<=다)\.\s+', background)
                          if any(term in part for term in ('장로 측', '장로측', '고소인', '장로는', '장로들은')))
        if claim:
            # Preserve terminal punctuation removed only at sentence boundaries.
            claim = '\n'.join(line if line.endswith(('.', '다.', '됨.')) else line + '.' for line in claim.splitlines())
        label, note = checks[number]
        evidence, draft = PLANS[number]
        entries.append({
            'key': key, 'number': number, 'title': article.attrs['data-title'], 'date': article.attrs['data-date'],
            'background': background, 'original_sources': '\n'.join(node.text() for node in sources),
            'initial_claim_basis': '기존 웹 경과에서 발췌한 주장 요약 · 최초 고소 원문 직접 대조 전',
            'initial_claim': claim or '기존 경과에서 장로 측 최초 주장이 별도로 특정되지 않았습니다. 해당 원문과 제출 주체를 추가 확인해야 합니다.',
            'opinion_title': title, 'original_opinion': opinion,
            'original_opinion_sha256': hashlib.sha256(opinion.encode()).hexdigest(),
            'appeal_basis': '2026.11.07 재검토 문서 §2의 요약·분석을 재인용 · 상고 원문 직접 대조 전',
            'appeal_summary': appeal or '이 사건과 상고 주장의 직접 대응 관계는 아직 확인하지 않았습니다. 최초·변경 기소장, 추가의견, 상고이유서를 사건별로 연결하고 제출 주체·작성일·쪽수를 확인해야 합니다.',
            'check_label': label, 'check_notes': note,
            'evidence_plan': evidence,
            'draft_basis': '새 검토 제안 · 증거 확보와 준비위원 검토 후 확정',
            'draft_suggestion': draft,
        })
    if len(entries) != 72 or set(checks) != set(range(1, 73)):
        raise ValueError('Expected all 72 event opinions and review checklist rows.')
    return {'version': 1, 'snapshot_date': '2026-11-07', 'source_commit': commit,
            'timeline_source': 'portal/templates/portal/integrated_case_reading.html',
            'timeline_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'review_source': review_name, 'review_sha256': hashlib.sha256(review_text.encode()).hexdigest(),
            'entries': entries}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    source = (root / 'portal/templates/portal/integrated_case_reading.html').read_text(encoding='utf-8')
    output = build(args.review.read_text(encoding='utf-8'), source, args.source_commit, args.review.name)
    (root / 'portal/preparation_data.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Built private snapshot: 72 original opinions and 72 preparation plans.')
