# 자발적 모금 안내 관리

홈페이지 소개 바로 아래의 안내 카드가 `/#fundraising`으로 연결됩니다. 상세 본문은 기존 사건 타임라인 다음, 푸터 앞에 펼쳐진 상태로 있습니다. 본문 소제목·문단·운영 원칙은 제공된 문구를 그대로 유지합니다. 준비 상태의 계좌 안내는 송금 버튼이나 결제 연동이 아닙니다.

## 계좌 정보를 바꾸는 위치

`portal/fundraising.py`의 `FUNDRAISING` 한곳에서 관리합니다. 현재 `bank_name`은 `카카오뱅크`, `status`는 `preparing`이며 나머지 값은 모두 빈 문자열입니다.

| 항목 | 용도 |
| --- | --- |
| `status` | 준비 중은 `preparing`, 공개 승인이 끝나면 `published` |
| `bank_name` | 은행명 |
| `account_number` | 공개 승인된 계좌번호 |
| `account_holder` | 확인된 예금주 |
| `manager` | 공개 승인된 관리 담당자 안내 |
| `contact` | 공개 승인된 문의 방법(일반 텍스트) |

계좌번호·예금주가 모두 공백이 아닌 값이고 `status`가 정확히 `published`일 때만 실제 계좌와 복사 버튼을 표시합니다. 이 조건이 충족되지 않으면 입력된 계좌·예금주·담당자·문의 방법을 공개 템플릿에 전달하지 않습니다. 빈 담당자·문의 항목의 라벨도 출력하지 않습니다. 카드와 상세 안내는 같은 상태 데이터를 사용합니다.

정보를 확인한 후 위 설정을 수정해 일반 코드 검토·배포 절차로 반영합니다. 별도의 관리자 화면·DB·신청 폼은 없습니다. 공개 상태에서는 Clipboard API가 실제 성공했을 때만 성공 안내를 표시하며, 권한 거부·미지원 시 직접 선택해 복사하라는 안내를 제공합니다. JavaScript가 없으면 표시된 계좌를 직접 선택할 수 있습니다.

## 검증

```sh
cd /workspace/shinsung
APP_MODE=development .venv/bin/python manage.py check
APP_MODE=development .venv/bin/python manage.py makemigrations --check --dry-run
APP_MODE=development .venv/bin/python manage.py collectstatic --noinput
APP_MODE=development .venv/bin/python manage.py test portal.test_fundraising portal.test_landing portal.test_public_reading portal.test_public_case_documents portal.test_preparation portal.test_appeals
node --check portal/static/portal/fundraising.js
```

별도 개발 도구인 Playwright와 Chromium이 있는 환경에서는 로컬 서버를 시작하고 다음을 실행합니다. 기본 주소는 `http://127.0.0.1:8000`이며 `FUNDRAISING_BASE_URL`, `CHROMIUM_PATH`, `FUNDRAISING_ARTIFACTS`로 변경할 수 있습니다.

```sh
FUNDRAISING_ARTIFACTS=/tmp/fundraising-artifacts node scripts/verify_fundraising_browser.cjs
```

브라우저 스크립트는 1440×1000 / 390×844에서 첫 화면 내 버튼, 키보드·직접 앵커 접근, 준비 중인 계좌와 복사 버튼 비노출, 기존 링크, 가로 넘침, 콘솔 오류를 확인합니다. 미래 공개 상태의 검사는 별도 자식 프로세스와 브라우저가 가로챈 로컬 테스트 응답에서만 식별용 테스트 문자열을 사용합니다. 실제 설정 파일이나 DB는 수정하지 않습니다. 성공 경로는 브라우저 Clipboard API로 복사한 실제 내용을 읽어 비교하고, 권한 거부·미지원 경로는 실패 안내를 확인합니다.

이번 변경에서 위 Django 테스트 37개, check·마이그레이션 변경 검사·collectstatic·JavaScript 구문 검사 및 브라우저 검사가 통과했습니다. 정상 페이지의 콘솔 오류·실패 응답·가로 넘침이 없고 초기 영상 요청도 0건입니다. 실제 계좌는 아직 제공되지 않았으므로 현재 준비 중 상태를 유지합니다. 운영 배포나 실제 송금 검증을 수행했다는 의미는 아닙니다.

[데스크톱 첫 화면](fundraising-screenshots/desktop.png) · [모바일 첫 화면](fundraising-screenshots/mobile.png) · [데스크톱 상세](fundraising-screenshots/detail-desktop.png) · [모바일 상세](fundraising-screenshots/detail-mobile.png)
