# 공개 사업자등록번호 확인 섹션

최신 main `b5834a3`에서 별도 브랜치 `feat/business-number-check`로 작업합니다. 저장소 및 상위 작업 경로에서 AGENTS.md는 발견되지 않았습니다. 기존 운영 지침 `docs/OPERATIONS.md`, 공개 자료 안내 `docs/case-documents/README.md`, 랜딩 구성 `docs/LANDING.md`를 확인했습니다.

## 화면 구성

메인 소개문 직후에 안내 카드를 추가하고 `#business-number-check`로 연결합니다. 기존 사건 목록 다음, 모금 본문 앞에 독립 섹션을 추가합니다. 제목·도입·비교표·계산과 가중치·홈택스 전달 정보·성도 설명·확인 요청을 본문으로 표시합니다. 기존 영상·72개 사건·⑤ 우리의 의견·상황판·로드맵·모금 본문은 수정하지 않습니다.

신규 CSS는 이 섹션의 클래스에만 적용합니다. 모바일 비교표는 내부 가로 스크롤이 가능하고 본문은 화면 너비 안에서 줄바꿈합니다. 표 영역은 키보드로도 접근할 수 있습니다. 링크는 기본 앵커 동작이며 별도 JavaScript 없이 이동합니다. 이미지 확대는 새 탭의 실제 JPEG로 연결합니다.

## 증빙 확인과 누락

요청된 개별 사진 5장은 저장소의 이미지 목록과 현재 첨부에 없습니다. 공개 PDF의 텍스트 검색은 가림 처리된 스캔본이라 일치 항목을 반환하지 않았습니다. 견적서 관련 답변서·성도 자료·고발장 등 공개 PDF의 페이지 축소 이미지를 확인하여 **D01.pdf 40쪽**의 견적서를 찾았습니다.

- 실제 판독: 날짜 `2024년 02월 25일`, 등록번호 `128-03-18446`. 상호는 선목인테리어로 읽힙니다.
- 대표자명 일부·주소·전화·팩스·날인은 기존 공개 사본에서 이미 가려져 있습니다. 대표자명 전체를 복원·추정하지 않았습니다. `김득만`은 사용자 전달 정보로만 구분합니다.
- 사진 자체에는 공사명 `4층 개조공사`가 직접 표기되지 않아, 공사 구분은 사용자 전달 내용으로 표시합니다.
- 다른 두 견적서와의 동일 상호·대표자명·주소·연락처 비교는 완료하지 못했습니다. 해당 비교 문구도 사용자 제공 설명과 원문 대조 대기 상태로 표시합니다.
- 아래 4개 증빙은 확보하지 못했습니다. 가짜 이미지·대체 이미지·깨진 이미지 URL을 만들지 않습니다.

| 미확보 증빙 | 화면 처리 |
| --- | --- |
| 2021. 9. 25. 임시성전 인테리어 견적서 | 사용자 전달 표 + 원문 미확보 표시 |
| 2023. 10. 10. 임시성전 철거 견적서 | 사용자 전달 표 + 원문 미확보 표시 |
| 128-03-18446 홈택스 조회 캡처 (2026. 11. 17.) | 사용자 전달 날짜·결과 + 캡처 미확보 표시 |
| 128-03-18449 홈택스 조회 캡처 (2026. 11. 17.) | 끝자리 변경 가정 번호 + 사용자 전달 결과·캡처 미확보 표시 |

별도 카페 전기공사 영수증·4층 공사 영수증·자료 공개 요청/회신 경위·감사 관련 설명을 직접 확인했다고 표시하지 않습니다. 성도 설명은 직접 인용 형식을 쓰지 않고 `성도가 전달한 설명·요지`로 구분합니다.

홈택스 실시간 조회를 대신 실행하지 않았습니다. 두 조회 결과·조회일자·이용상 주의사항은 사용자 전달 내용이며 캡처 원문 미대조임을 명시합니다. 캡처가 제출되면 번호·날짜·결과·법적 효력 안내를 원문으로 대조해야 합니다. 제공되지 않은 자료의 내용을 확인된 사실로 승격하지 않습니다.

## 공개 이미지와 가림

`static/case-documents/D01.pdf`는 기존 승인된 공개 가림 사본입니다. 이를 pdftoppm으로 JPEG 렌더링하고 날짜·공급자 정보 영역을 확대용으로 추출했습니다. 비공개 원본을 읽거나 공개 경로로 복사하지 않았고, 기존 PDF는 변경하지 않았습니다. 이미지 자체에 기존 검은 가림이 포함되어 있으며 CSS 덮개나 가림 전 레이어는 없습니다. 새로운 문구나 이미지 내용을 생성하지 않았습니다.

재현 명령 (pdftoppm):

```sh
pdftoppm -f 40 -l 40 -scale-to 2400 -singlefile -jpeg -jpegopt quality=92 static/case-documents/D01.pdf portal/static/portal/business-number/estimate-2024-redacted
pdftoppm -f 40 -l 40 -scale-to 2400 -x 150 -y 250 -W 1350 -H 500 -singlefile -jpeg -jpegopt quality=95 static/case-documents/D01.pdf portal/static/portal/business-number/estimate-2024-detail
```

| 파일 | bytes | SHA-256 |
| --- | --- | --- |
| `estimate-2024-detail.jpg` | 112,910 | `b81106f030e806240a190b0f11b7af6714c7815dc18cadad22f225ce4913a512` |
| `estimate-2024-redacted.jpg` | 458,071 | `fe4dc29d20ef3c90d459c5c812137f76ae99a12462b4ac395771ef6f5ff3b4bc` |

이미지는 기존 Django static manifest와 WhiteNoise로 제공합니다. 해시 URL을 하드코딩하지 않습니다. 날짜·등록번호를 볼 수 있고 대체 텍스트는 대표자명 일부 가림과 원문 위치를 명시합니다. 공사명·대표자명을 가림 밖에 새로 작성하지 않습니다.

## 계산 대조

- `128031844`: 가중치 곱 합계 119, 아홉 번째 자리 곱 20의 십의 자리 2 추가 → 121 → 검증 숫자 9. 기재 끝자리 6과 불일치.
- `581160046`: 가중치 곱 합계 97, 아홉 번째 자리 곱 30의 십의 자리 3 추가 → 100 → 검증 숫자 0. 기재 끝자리 0과 일치.
- `128-03-18449`는 끝자리 변경 가정 번호이며 업체가 발급하거나 정정한 번호가 아닙니다.
- 계산 일치는 실제 등록·정상 영업의 확인이 아닙니다. 오기 위치·작성자의 고의·공사 당시 등록 상태를 계산이나 전달 캡처로 확정하지 않습니다.

## 검사 재현

```sh
APP_MODE=development .venv/bin/python manage.py check
APP_MODE=development .venv/bin/python manage.py makemigrations --check --dry-run
APP_MODE=development .venv/bin/python manage.py collectstatic --noinput
APP_MODE=development .venv/bin/python manage.py test
APP_MODE=development .venv/bin/python scripts/verify_backup.py
.venv/bin/python -m pip check
# 기존 로컬 DB는 변경하지 않고 앱을 직접 실행:
APP_MODE=development .venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:18081 --workers 1
BUSINESS_NUMBER_BASE_URL=http://127.0.0.1:18081 node scripts/verify_business_number_browser.cjs
```

기존 영상 포스터 부재 테스트는 영상 영역 안에 이미지가 없는지를 검사하도록 범위를 한정했습니다. 새 증빙 이미지를 영상 표지로 판단하지 않으며 기존 영상 부재 검사를 삭제하지 않습니다. 새 카드가 소개문 직후에 추가되므로 기존 모금 카드는 아래로 이동합니다. 모금 브라우저 검사는 첫 화면 고정 위치 대신 스크롤 후 버튼 노출과 기존 참여 안내 이동·계좌 상태 동작을 검사합니다.

[모바일 안내 카드](business-number-screenshots/card-mobile.png) · [PC 본문](business-number-screenshots/section-desktop.png)

검증 결과는 PR에 기록합니다. 실제 휴대전화·운영 laity.kr 배포 후 화면·운영 CDN 응답은 미확인입니다. 자동 병합·운영 배포·Cloudtype 설정 변경은 하지 않습니다. 모델·마이그레이션·URL·인증/MFA·CSP·검색 제한·/prepare 구현과 기존 DB는 변경하지 않습니다.

## 이번 실행 결과

- Django check 통과, makemigrations --check --dry-run 변경 없음.
- collectstatic 통과. 신규 CSS와 JPEG 2개가 기존 manifest 해시 URL로 제공되며 브라우저에서 실제 파일을 디코딩했습니다.
- 전체 Django 테스트 182개 통과. 별도 관련 테스트 40개도 통과: 신규 섹션·랜딩·공개 열람·공개 문서·준비 영역·상고·모금 포함.
- Chromium 1440×1000, 390×844, 360×844: 소개문 다음 카드 배치, 키보드/직접 앵커 이동, 제목 노출, 모바일 표 내부 스크롤, 가로 넘침 없음, 이미지 확대·전체 보기, 기존 사건 링크·72개 사건·세 플레이어·모금 보존 확인.
- 정상 페이지 콘솔/파일 요청 오류 없음, 초기 MP4 요청 0건. 로컬 비로그인 /prepare/events/T01/가 기존처럼 /prepare/로 302 이동함을 확인.
- 기존 모금 브라우저 검사 1440/390 통과: 버튼 스크롤 접근·섹션 이동, 계좌 준비 상태, 격리 fixture의 복사 성공/거부/미지원 결과.
- 가상 임시 DB 기반 백업/복구·체크섬 거부 검사 및 pip check 통과. 기존 운영/로컬 DB를 초기화하거나 변경하는 작업은 실행하지 않음.
- 원본 D01 PDF·영상·기존 관련 템플릿·인증/설정/데이터 diff 없음, git diff --check 및 두 브라우저 검사 스크립트 구문 검사 통과.
- 미확인: 실제 모바일/운영 laity.kr·CDN·배포 후 동작, 누락된 견적서 2장·홈택스 캡처 2장 원문. Docker 빌드와 실제 배포는 이번 작업에서 실행하지 않음.
