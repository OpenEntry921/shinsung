# 교인 전용 사건 열람·실명 게시판

가칭 **교회를 살리는 신도들의 모임**. 교회 공식 홈페이지·교단 판단 기관이 아닌 교인 자발 운영 사이트입니다. COMMON과 연결되는 코드·인증·환경변수·데이터는 없습니다. 회원가입, AI 판정, 댓글, 투표, 서명, 회원 목록은 제공하지 않습니다.

## 구현

- XLSX 명부 검증·미리보기·확인 반영. 교인명부 시트 / 2행 헤더 / B 이름 / C 전화번호.
- 이름·전화번호 암호화, 내부 ID 보존, 누락 자동 삭제 금지, 연락처 변경 및 비활성화 시 세션·기존 인증 무효화.
- 명부 일치 + 휴대전화 일회용 인증. 5분 유효 / 5회 시도 / 60초 재요청 제한 / 번호당 시간당 5회 / IP당 시간당 20회 요청.
- 공용 번호 일반 인증 차단. 관리자 별도 본인 확인 후 15분짜리 개인별 일회성 접속 정보 발급.
- 인증된 세션에서만 사건·게시판·문서 접근. 실명은 서버의 교인 기록에서 적용.
- 사건 / 통합 헌법 / 현재 상황 3열 비교, 모바일 1열, 제목·주제·기간 검색.
- 사실·주장·의견·공식 판단 분리, 조문 검증 전 확인 중. 실제 사건·실제 조문 초기 데이터 없음.
- 실명 글 작성·본인 수정·삭제·관련 사건 선택·신고·정정·비공개 자료 제안·이의 제기.
- 명부/내용/승인/게시판 관리자 역할 분리, 관리자 비밀번호 + TOTP, 작성자 외 게시 승인.
- 원본/열람본 분리 및 암호화 파일 저장. 열람본은 다른 검토자가 가림 검증 후 승인. 관리자 과거 버전 조회.
- 서버 측 권한 검사, Secure/HttpOnly/SameSite 쿠키(운영), Origin + CSRF 검증, CSP, 매개변수 SQL.
- SQLite WAL 영구 저장, 암호화 백업·복구 CLI, 만료 자료 정리. SMS는 영구 암호화 발송 큐에서 처리하여 네트워크 지연으로 명부 일치를 드러내지 않음.

## 설치 및 실행

Python 3.12 이상. 실제 명부를 개발용으로 사용하지 마세요.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

`.env.example`은 **설정 항목 예시**입니다. 앱이 `.env` 파일을 자동으로 읽지 않습니다. Cloudtype 환경변수 또는 셸의 export로 지정하세요. 저장소에 실제 키를 커밋하지 마세요.

```bash
export APP_ENV=development
export PUBLIC_ORIGIN=http://127.0.0.1:3000
export DATA_DIR=/absolute/private/data
export APP_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DATA_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
python -m flask --app app create-admin --username roster-admin --roles roster
python -m flask --app app create-admin --username content-author --roles content
python -m flask --app app create-admin --username reviewer --roles publish,moderate
python -m gunicorn --config gunicorn.conf.py --workers 2 --threads 2 --bind 127.0.0.1:3000 'app:create_app()'
```

관리자 생성 CLI가 비밀번호를 숨겨 입력받고 인증 앱 등록용 비밀값을 한 번 출력합니다. 이 출력은 보안 콘솔에서만 확인하고 로그로 보관하지 마세요. 아이디·인증 앱을 개인별로 운영하세요. `/admin`에서 로그인합니다. 복구가 필요하면 서버 콘솔에서 기존 관리자를 비활성화하고 새 관리자 계정을 생성하세요. 공용 관리자 비밀번호는 사용하지 마세요.

개발 모드도 SMS 미연결 시 실제 인증이 불가능합니다. 가상 SMS는 `TESTING=True`를 직접 주입하는 자동 테스트에서만 사용합니다. `APP_ENV=test`만 환경변수로 설정해 서버를 띄우면 시작을 거부합니다.

```bash
python -m pytest -q
node --check app/static/app.js
```

## 환경변수

| 이름 | 용도 |
|---|---|
| APP_ENV | production 기본 / development. test는 명시적 테스트 설정에서만 가능 |
| APP_SECRET | 32자 이상 서버 비밀값, 교체하면 세션·OTP·전화번호 조회키 영향. 일상 재배포에 변경 금지 |
| DATA_KEY | Fernet 암호화 키. 분리된 안전한 장소에 반드시 백업. 변경·분실 시 기존 개인정보·문서 복호화 불가 |
| DATA_DIR | 영구 볼륨 절대 경로. Docker 기본 `/data` |
| PUBLIC_ORIGIN | 정확한 사이트 출처, 끝 슬래시 없이. production에서는 HTTPS 필수 |
| SOLAPI_KEY / SOLAPI_SECRET / SMS_SENDER | SOLAPI API 키·비밀값·사전 등록 발신번호 |
| CONTACT_TEXT | 운영자 문의처. 명부 수정·삭제·인증 곤란 연락 방법 |
| POLICY_APPROVED | 기본 0. 아래 정책 확정·문의처 안내 수정 후 운영자가 1 설정 |
| POLICY_CONTROLLER | 실제 개인정보 처리 주체 |
| POLICY_BASIS | 명부 이용 근거와 확인 절차. 행정실 명부 수령만으로 전체 동의를 주장하지 않음 |
| POLICY_ROSTER_RETENTION | 명부 보유기간과 변경·삭제 요청 처리 |
| POLICY_DOCUMENT_RETENTION | 사건 자료·원본·과거 버전 보유기간 |
| POLICY_BACKUP_RETENTION | 백업 보유기간과 삭제 반영 일정 |
| PORT | Docker 내부 기본 3000 |

`POLICY_APPROVED=0`이면 교인 로그인을 차단합니다. 운영에서 정책 항목 미설정 상태로 승인하면 시작을 거부합니다. 정책 입력은 운영자가 확정한 내용을 표시하는 것이며, 프로그램이 적법성을 판단하지 않습니다. SMS 위탁·처리 정보는 실제 계약에 맞춰 `privacy.html`에 보완하세요.

SOLAPI 공식 [인증 문서](https://solapi.com/developers/api/authentication-api-key), [발송 문서](https://solapi.com/developers/api/messages)를 기준으로 HMAC-SHA256 및 `/messages/v4/send-many/detail` 연결 코드를 구현했습니다. 키 설정만으로 실발송 검증이 완료되지 않습니다. 발신번호 승인·잔액·실제 수신 성공을 확인해야 합니다. 업체 발송 기록에 전화번호·메시지가 저장되는 점과 업체 보유기간도 안내에 포함하세요. 앱은 요청·응답 본문을 로그로 출력하지 않습니다.

## Cloudtype 배포

1. 이 저장소의 검토·머지된 브랜치를 Dockerfile 방식으로 연결합니다. 내부 포트 3000, 상태 확인 `/healthz`.
2. **`/data`를 영구 볼륨으로 연결**하고 UID 10001에 쓰기 권한을 부여합니다. 임시 컨테이너 파일시스템으로 운영하지 마세요.
3. 위 환경변수를 서비스에 등록합니다. 서비스 외부 출처와 PUBLIC_ORIGIN을 일치시키고 HTTPS를 확인합니다.
4. 관리자 세 계정을 보안 콘솔에서 생성하거나, 같은 환경변수로 만든 로컬 초기 DB를 비공개 영구 볼륨에 안전하게 이관합니다. 웹 초기 비밀번호·우회 URL은 없습니다.
5. 개인정보 이용 목적·근거·보유기간·처리 주체·문의처 확정, 정책 안내 확인, 실제 SMS 수신 검증 후 교인 접속을 개방합니다.
6. 가상 데이터로 Cloudtype에서도 로그인·문서 권한·재배포 후 자료 유지·백업 복구를 먼저 점검합니다.

현재 배포 설정에는 Gunicorn 워커별 SMS 큐 처리와 매시간 만료 기록 정리가 포함됩니다. 별도의 실행 명령으로 배포하면 `gunicorn.conf.py`를 유지해야 합니다. 발송 프로세스 오류는 개인정보 없는 일반 오류로만 기록합니다. 컨테이너 health는 DB 연결 검사이며 실제 SMS 전달을 보장하지 않습니다.

SQLite는 **단일 서비스 인스턴스 / 로컬 영구 볼륨**을 전제로 합니다. 같은 DB를 네트워크 파일시스템으로 여러 컨테이너가 공유하거나 다중 복제본으로 배포하지 마세요. 확장 시 PostgreSQL과 객체 저장소로 별도 이전이 필요합니다. 프록시의 X-Forwarded-For를 무조건 신뢰하지 않으므로 IP 제한이 프록시 주소에 합산될 수 있습니다. Cloudtype 환경에서 정상 이용자가 차단되는지 확인한 뒤 신뢰 프록시 설정을 별도로 검증하세요.

## 운영 절차

[명부·자료·게시판 운영](docs/OPERATIONS.md), [검증 결과·미완료 사항](docs/VALIDATION.md)을 읽고 운영하세요.

백업은 서버의 `DATA_KEY`로 전체 스냅샷을 암호화합니다. 키를 백업 파일과 같은 위치에 보관하지 마세요.

```bash
python -m flask --app app backup /secure/backups/church-2026-10-12.enc
python -m flask --app app purge-expired
python -m flask --app app disable-admin retired-admin
```

자동 외부 백업 서비스는 연결하지 않았습니다. 운영자가 하루 1회 이상 백업하고 별도 저장소에 보존하도록 예약하세요. 복구는 **웹 워커를 모두 중지한 별도 빈 DATA_DIR**에서 동일 APP_SECRET/DATA_KEY로 수행합니다.

```bash
python -m flask --app app restore /secure/backups/church-2026-10-12.enc
```

복구 시 세션·인증번호·명부 미리보기를 폐기합니다. 자료 복호화·DB 무결성·권한 검사를 확인한 뒤 서비스 경로를 전환합니다. 운영 명부 삭제·원본 자료 보유기간 만료는 안전한 서버 작업으로 처리하며, 게시글 작성자 연결과 정정 이력을 고려해 담당자가 별도 절차를 확정하세요.
