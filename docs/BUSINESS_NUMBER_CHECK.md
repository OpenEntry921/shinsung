# 공사 견적서 사업자등록번호 확인

## 이번 보완의 기준

최신 main `e82db1b`에 기존 섹션이 병합되어 있어 중복 생성하지 않고 `feat/business-number-evidence`에서 보완했습니다. AGENTS.md는 저장소와 상위 작업 경로에서 발견되지 않았습니다. 기존 `docs/OPERATIONS.md`, `docs/LANDING.md`, 공개 자료 운영 지침을 유지합니다.

소개문 직후 카드의 설명과 버튼을 최종 문구로 변경했습니다. 본문에는 핵심 요약, 견적서 비교, 가중치·계산, 홈택스 두 결과, 성도 설명·요지, 여섯 확인 요청을 구분했습니다. 비교표는 모바일에서 카드형 행으로 표시합니다. 새 공개 답변 접수 기능이나 연락처는 만들지 않았습니다.

## 전달된 내용과 실제 파일 확보 상태

사용자가 대화에 표시한 견적서 사진 3장과 홈택스 캡처 2장에서 다음 내용을 시각적으로 대조했습니다. 그러나 실행 환경에 전달된 신규 첨부 파일은 `붙여넣은 텍스트.txt`뿐이며, 표시된 이미지 5장의 다운로드 가능한 파일 경로·파일 ID는 제공되지 않았습니다. 텍스트를 이미지로 만들거나 표시 이미지를 재생성하지 않았습니다. 이미지 파일 재첨부가 필요함을 작업 중 안내했습니다.

| 구분 | 날짜/조회일 | 번호 | 표시 금액 또는 결과 | 공개 파일 상태 |
| --- | --- | --- | --- | --- |
| 임시성전 인테리어 견적서 | 2021. 9. 25. | 581-16-00460 | 51,890,000원, VAT 별도 | 신규 사진 파일 미확보 |
| 임시성전 철거 견적서 | 2023. 10. 10. | 581-16-00460 | 12,090,000원, VAT 별도 | 신규 사진 파일 미확보 |
| 4층 개조공사 견적서 | 2024. 2. 25. | 128-03-18446 | 15,444,000원, VAT 별도 | 신규 사진 파일 미확보. 기존 공개 D01 40쪽 가림 사본은 유지 |
| 견적서 기재 번호의 홈택스 캡처 | 2026-11-17 | 128-03-18446 | 국세청에 등록되지 않은 사업자등록번호입니다. | 신규 캡처 파일 미확보 |
| 끝자리 변경 가정 번호의 홈택스 캡처 | 2026-11-17 | 128-03-18449 | 국세청에 등록되지 않은 사업자등록번호입니다. | 신규 캡처 파일 미확보 |

화면에는 일부 공개용 이미지가 준비 중임을 표시합니다. 현재 실제 이미지 연결은 기존 2024년 견적서 한 항목뿐입니다. 홈택스 결과를 읽은 것과 해당 이미지 파일의 배포·가림을 완료한 것은 구별합니다. 홈택스 실시간 조회는 수행하지 않았습니다.

표시된 견적서의 상호·대표자명은 선목인테리어·김득만으로 읽힙니다. 도장이 이름과 겹친 부분은 확정하거나 재작성하지 않습니다. 주소·연락처의 동일 여부는 비교 설명으로만 표시하고 값은 본문·대체 텍스트에 전사하지 않습니다. 동일인이 직접 작성했다는 결론으로 확대하지 않습니다. 금액은 견적서 표시 금액이며 지급·계약 확정액이 아닙니다.

별도 영수증, 자료 요청/회신, 감사 설명은 이번 첨부에서 확인되지 않았습니다. 해당 내용은 직접 인용 없이 성도 설명·요지로 분리하고 추가 대조 필요성을 명시합니다.

## 파일 연결과 이미지 확대

`portal/business_number.py`에서 날짜·번호·금액·공개 파일 논리 경로를 관리합니다. 기존 `asset_url()`을 재사용해 실제 파일과 manifest 항목이 있을 때만 이미지를 연결합니다. 없는 파일의 URL이나 대체 이미지는 출력하지 않습니다.

파일을 확보하고 파일 자체의 가림 검수를 마친 뒤 다음 **공개용 사본만** 등록합니다. 원본은 저장소·정적 경로·배포 이미지에 추가하지 않습니다.

- `portal/static/portal/business-number/estimate-2021-redacted.jpg`
- `portal/static/portal/business-number/estimate-2021-detail.jpg`
- `portal/static/portal/business-number/estimate-2023-redacted.jpg`
- `portal/static/portal/business-number/estimate-2023-detail.jpg`
- `portal/static/portal/business-number/estimate-2024-redacted.jpg` / `estimate-2024-detail.jpg` (현재 기존 D01 사본. 신규 사진으로 교체하면 본문 D01 출처 표기도 함께 갱신)
- `portal/static/portal/business-number/hometax-1280318446.png`
- `portal/static/portal/business-number/hometax-1280318449.png`

가림 기준: 날짜·공사 구분·상호·읽을 수 있는 대표자명·등록번호·금액 유지. 전화·팩스·상세주소·서명·도장은 이미지 픽셀에 불투명하게 가림. 도장과 겹친 이름은 복원하지 않음. 홈택스는 번호·결과·조회일·법적 효력 안내와 주의사항을 유지. 공개용 전체와 확대 사본을 각각 검수해야 합니다.

이번에는 신규 이미지 파일이 없어 위 5장에 대한 가림 작업과 가림 후 픽셀 검수를 실행하지 못했습니다. 기존 D01에서 추출된 두 JPEG와 원본 공개 PDF는 바꾸지 않았습니다. 신규 무가림 이미지는 커밋하지 않습니다.

실제 이미지 링크는 native dialog로 확대합니다. 키보드 Enter로 열기, Esc·닫기 버튼으로 종료, 종료 시 트리거로 초점 복귀를 지원합니다. 원본 크기/화면 맞춤 버튼과 스크롤 가능한 확대 영역을 제공하며, JavaScript가 없으면 원래 이미지 링크로 이동합니다. CSS 덮개로 개인정보를 가리지 않습니다.

## 계산과 표현

- 128031844: 가중치 곱 합계 119 + 아홉 번째 곱 20의 십의 자리 2 = 121. 검증 숫자 `(10 - 121 % 10) % 10 = 9`. 기재 6과 불일치.
- 581160046: 곱 합계 97 + 추가 3 = 100. 검증 숫자 0, 기재 0과 계산 일치. 실제 등록·영업 확인은 아님.
- 128-03-18449는 끝자리 변경 가정 번호이며 업체 정정 번호가 아님.
- 조회 화면은 2026년 11월 17일 결과로 한정. 공사 당시 상태·고의·위법을 확정하지 않음. 홈택스 법적 효력 제한을 읽을 수 있게 표시.

## 검증 방법

```sh
APP_MODE=development .venv/bin/python manage.py check
APP_MODE=development .venv/bin/python manage.py makemigrations --check --dry-run
APP_MODE=development .venv/bin/python manage.py collectstatic --noinput
APP_MODE=development .venv/bin/python manage.py test
APP_MODE=development .venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:18082 --workers 1
BUSINESS_NUMBER_BASE_URL=http://127.0.0.1:18082 BUSINESS_NUMBER_IMAGES=1 node scripts/verify_business_number_browser.cjs
```

이번 실행 결과는 PR에 기록합니다.

기존 72개 사건·의견·영상·모금·/prepare·인증과 DB는 변경하지 않습니다. 자동 병합·운영 배포는 하지 않습니다.

[모바일 안내 카드](business-number-screenshots/card-mobile.png) · [모바일 카드형 비교](business-number-screenshots/comparison-mobile.png) · [PC 본문](business-number-screenshots/section-desktop.png)

## 이번 검증 결과

- Django check, collectstatic, 마이그레이션 변경 없음 검사 통과.
- 전체 Django 테스트 184개 통과. 관련 Django 테스트 42개도 통과. 5개 파일 연결 경로와 누락 시 처리는 격리된 URL 모의값으로 검사했으며, 실제 이미지 5장 배포 검증은 아닙니다.
- 로컬 Gunicorn/WhiteNoise와 Chromium 1440×1000, 390×844, 360×844에서 새 문구·앵커 이동·모바일 카드형 표·가로 넘침 없음·확대 창 Enter/Esc/닫기·초점 복귀·원본 크기 보기 확인.
- 실제 이미지는 기존 견적서 1항목의 두 JPEG만 검사했습니다. 해시 정적 URL·image/jpeg·200·이미지 디코딩 성공. 페이지 콘솔·파일 요청 오류 없음. 초기 MP4 요청 0건.
- JavaScript 비활성 상태의 섹션 이동과 실제 이미지 링크 fallback 확인.
- 기존 모금 브라우저 검사 통과: 계좌 준비 상태·스크롤 접근·키보드 이동·격리된 복사 성공/실패/미지원 fixture.
- 기존 사건 72개와 세 플레이어 유지, 기존 사건 링크 200, 비로그인 /prepare/events/T01/의 /prepare/ 이동 유지.
- 미실행: 신규 원본 5장 파일 가림·가림 후 픽셀 검수·새 사진/캡처 실제 HTTP 연결, 실기기·운영 laity.kr/CDN·Docker 빌드·실제 배포.
