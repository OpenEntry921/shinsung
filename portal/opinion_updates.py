"""Reviewed display-only opinion updates. No database records or reader comments are created."""
from copy import deepcopy

PROCEDURE_OPINIONS = {
    'T08': {
        'id': 'OP09', 'number': 8, 'related': (17, 54),
        'title': '자신의 공사에는 대화방 동의, 목사에게는 정식 결의인가',
        'body': (
            '장로 측은 4층 공사에 관하여 당회에서 논의했고 단체대화방과 건축위원회에서 견적 공개·동의가 있었다고 설명한 것으로 정리돼 있습니다. 그러나 같은 정리에는 최종 안건 부의가 미완료였다는 설명도 있습니다. 그렇다면 공사 내용을 논의하고 견적을 공유했다는 사실만으로 정식 결의까지 있었다고 볼 수 있는지 분명히 밝혀야 합니다.',
            '이 문제는 17번 세무기장 담당자 교체와 함께 살펴야 합니다. 장로 측은 목사가 당회 결의 없이 담당자를 교체했다는 점을 문제 삼았습니다. 자신의 공사 추진에서는 대화방 동의를 근거로 제시하면서 목사의 행정행위에는 정식 당회 결의를 요구했다면, 두 사건에 적용한 기준이 어떻게 다른지 설명해야 합니다.',
            '목사가 논의에 참여했거나 공사 내용을 알고 있었다는 사정도, 그 자체로 특정 계약과 지출에 대한 정식 결의가 있었다는 증거가 되지는 않습니다. 무엇을 안건으로 올렸고, 누가 어떤 내용에 동의했으며, 어떤 절차로 의결했는지 확인할 수 있는 기록을 제시해야 합니다.',
            '공사와 담당자 교체는 권한과 승인 절차가 다를 수 있습니다. 그러나 그 차이는 해당 규정과 실제 결의 기록으로 설명해야 합니다. 장로 측 행위의 절차상 공백은 대화방 동의로 설명하면서 목사에게만 결의 부재의 책임을 엄격하게 묻는 방식이라면, 우리는 이를 공정한 기준이라고 받아들일 수 없습니다. 목사에게 요구한 절차적 엄격함을 장로들의 공사 추진에도 동일하게 적용할 것을 요구합니다.',
            '자료 확인 범위: 장로 측 반론은 S01 정리본에 소개된 내용입니다. 해당 총회 제출 요약서·회의록·카카오톡 원문을 직접 대조하기 전까지 정식 결의의 존재 또는 부재를 확정하지 않습니다.',
        ),
    },
    'T17': {
        'id': 'OP16', 'number': 17, 'related': (8,),
        'title': '목사에게 요구한 결의 기준을 장로들에게도 적용하라',
        'body': (
            '이 사건에서 장로 측이 문제 삼은 핵심은 카카오톡이라는 전달 수단보다 당회 결의 없이 세무기장 담당자를 교체했다는 점입니다. 타임라인에 정리된 안양노회 재판국 판단도 결의 없는 교체를 직권남용으로 보았다고 기록돼 있습니다.',
            '그렇다면 08번 4층 공사에서도 정식 결의가 있었는지를 같은 엄격함으로 확인해야 합니다. 장로 측이 제시한 당회 논의와 단체대화방 동의가 정식 결의를 입증하는지, 최종 안건 부의가 미완료였다는 설명과 어떻게 양립하는지 밝혀야 합니다.',
            '우리는 목사의 행정행위라는 이유만으로 절차 문제를 면제하자는 것이 아닙니다. 목사에게 책임을 묻는 기준이라면 장로들에게도 적용하라는 것입니다. 두 사건의 권한과 승인 요건이 다르다면, 장로 측과 이를 판단하는 기관은 그 차이를 규정과 기록으로 설명해야 합니다.',
            '그 설명 없이 자신의 행위에는 비공식 동의를 방어 근거로 삼고 상대방에게는 정식 결의의 부재를 책임 근거로 삼는다면, 선택적으로 절차를 적용한다는 비판을 피하기 어렵습니다. 각 사건의 승인 권한, 안건, 의결 내용과 회의록을 제시하고 같은 기준으로 설명할 것을 요구합니다.',
        ),
    },
}


def apply_opinion_updates(entries, updates=None):
    """Idempotent offline edits, with IDs checked across the entire input."""
    updates=PROCEDURE_OPINIONS if updates is None else updates
    result=deepcopy(entries)
    by_key={entry['key']:entry for entry in result}
    for key,update in updates.items():
        if key not in by_key:raise ValueError('Opinion update target is missing')
        heading='우리의 의견 초안 '+update['id']
        for entry in result:
            if entry['key']!=key and any(p['heading']==heading for p in entry.get('supplements',[])):
                raise ValueError('Opinion ID belongs to another event')
        entry=by_key[key];parts=entry.setdefault('supplements',[])
        matches=[i for i,part in enumerate(parts) if part['heading']==heading]
        if len(matches)>1:raise ValueError('Duplicate opinion ID')
        # A new ID must not overwrite a different opinion already on the target.
        if not matches and any(p['heading'].startswith('우리의 의견 초안 ') for p in parts):
            raise ValueError('Target already has a different opinion')
        part={'heading':heading,'related_numbers':tuple(update['related']),
              'paragraphs':['**제목**: '+update['title'],
                            '**작성 주체·상태**: 사용자 명의 검토 초안 · 항목별 검토 전 · 미등록',
                            f"**주 연결 사건**: {update['number']:02}번 / **함께 읽을 사건**: "+' · '.join(f'{n:02}번' for n in update['related']),
                            *update['body']]}
        if matches:parts[matches[0]]=part
        else:parts.append(part)
    return result
