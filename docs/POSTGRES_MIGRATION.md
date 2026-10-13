# Cloudtype PostgreSQL 전환 — 운영 실행 전 점검

현재 사용자가 확인한 앱은 Dockerfile 배포, 디스크 미연결, `/data/portal.sqlite3` SQLite, 교인 1건·관리자 0건·사건/게시글 0건입니다. 앱의 `/data` 내부 사본은 재배포에 안전한 백업이 아닙니다. **외부 백업을 검증하기 전 현재 앱을 재배포하지 마세요.** 이 PR은 운영 이관·배포를 실행하지 않습니다.

## 1. 별도 DB 서비스의 보존 조건 확인

Cloudtype에서 PostgreSQL 서비스 제공 여부와 접속 정보를 확인하세요. 공식 문서 https://docs.cloudtype.io/ 는 작업 환경의 프록시에서 접근되지 않았습니다. 제공 버전, 데이터 디스크 자동 연결 여부, 재시작·재배포 보존, DB 서비스 삭제 시 삭제/복구 조건, 자동 백업·보유기간·복구 절차, 요금, 앱→DB 접속 및 TLS 지원을 담당자에게 확인하고 기록해야 합니다. PostgreSQL이라는 이유만으로 영구 보존을 보장하지 않습니다. 앱 Dockerfile 서비스와 **별도 DB 서비스의 저장 정책**을 구분하세요. 보존 조건이 확인되지 않으면 아래 실행을 중단합니다.

접속 URL은 실제 서비스가 제공한 호스트·포트·DB명·사용자·암호로 구성합니다. URL 안의 특수문자는 percent-encoding이 필요합니다. `DATABASE_URL`은 비밀 환경변수입니다. 설정한 값이 비었거나 형식이 잘못되면 시작을 거부하며 SQLite로 전환하지 않습니다. 변수를 아예 지정하지 않을 때만 기존 개발 SQLite를 사용합니다. 값을 채팅·로그·PR에 붙이지 마세요. TLS 기본값은 `verify-full`; 제공 인증서가 필요하면 `sslrootcert` 경로를 추가합니다. 인증서/호스트 검증이 안 된다고 TLS를 끄지 마세요. `sslmode=disable`은 로컬 격리 테스트용이며 운영 권고값이 아닙니다. 서비스의 실제 TLS 방식과 연결 가능 여부는 운영에서 확인해야 합니다.

## 2. 이전 앱을 재배포하기 전에 외부 백업 확보

이 PR의 검토된 `scripts/sqlite_transfer.py`를 현재 컨테이너의 `/tmp/sqlite_transfer.py`에 복사합니다. 저장소의 **검토한 커밋 SHA**에 고정된 GitHub raw 코드 URL로 받을 수 있습니다. 이 스크립트에는 실제 자료가 없습니다. 첨부 업로드나 SSH 기능이 있다고 가정하지 않습니다. 기존 터미널에서 코드만 받아 실행하는 절차입니다.

```sh
python -m pip install --target /tmp/shinsung-transfer-lib 'psycopg[binary]==3.3.6'
# 검토된 스크립트 커밋에 고정합니다. 다운로드 실패 시 실행하지 않습니다.
curl --fail --location 'https://raw.githubusercontent.com/OpenEntry921/shinsung/b3c21a92a3da5dae267bfe7bc48b7efaecea6a85/scripts/sqlite_transfer.py' --output /tmp/sqlite_transfer.py
PYTHONPATH=/tmp/shinsung-transfer-lib python /tmp/sqlite_transfer.py --source /data/portal.sqlite3 --persistence-confirmed
```

터미널의 숨김 입력으로 **새 DB** 접속 URL을 입력합니다. 원본은 읽기 전용으로 열고 SQLite backup API로 일관된 스냅샷을 만듭니다. 스냅샷 전체는 별도 PostgreSQL의 `shinsung_sqlite_backups` 테이블에 저장됩니다. 커밋 후 새 연결로 읽어 SHA-256과 바이트 전체를 대조합니다. 출력의 `external_copy_verified: true`, `members: 1`, `users/cases/documents/posts: 0`, `sha256`, `bytes`를 확인·보관하세요. 관리자·사건·문서·글이 생겼다면 백업은 보존하되 현재 교인 전용 이관 절차로 재배포하지 마세요. 실패하면 재배포하지 마세요. 컨테이너 임시 스냅샷은 제거되며, 검증된 외부 사본이 남습니다. 원본 데이터·전화번호·키는 출력하지 않습니다.

이 백업은 세션·인증정보도 포함하는 민감한 DB입니다. DB 서비스 관리자만 접근하고, 서비스 백업도 함께 확보하세요. 서비스 자체의 사고에 대비한 별도 외부 백업/복구·보유 정책은 여전히 필요합니다. 이 스크립트는 DB 제공업체의 보존 정책을 검증해 주지 않습니다. 현재 원본에 별도 비공개 파일이 생겼다면 그 파일의 외부 백업도 먼저 확보해야 합니다.

## 3. 설정·배포·교인 이관

외부 백업과 DB 서비스 준비가 끝난 뒤 사용자가 PR을 머지합니다. Cloudtype 앱 설정:

- `APP_MODE=production` (실제 자료를 개발 OTP로 열람하지 않음)
- `DATABASE_URL`: 위에서 연결·보존·TLS를 확인한 별도 PostgreSQL URL
- `DATABASE_PERSISTENCE_CONFIRMED=true`: **보존 조건을 실제 확인한 뒤** 지정하는 운영자 확인 값
- `REAL_MATERIALS_ENABLED=true`
- `DJANGO_SECRET_KEY`: 새 강한 비밀키 (아래 교체 절차)
- 실제 호스트의 `ALLOWED_HOSTS`, HTTPS `CSRF_TRUSTED_ORIGINS`, SMS 설정, 개인별 `ADMIN_MFA_SECRETS`

`DATA_DIR`는 기존 값을 유지합니다. `/data`를 영구 디스크라고 표현하지 않습니다. `PRIVATE_STORAGE_CONFIRMED=true`는 실제 파일 저장소가 확인된 경우에만 사용합니다. 이번 원문과 본문은 PostgreSQL에 저장하므로 이 플래그가 없어도 등록 가능합니다. 일반 PDF/명부 임시 업로드 등 기존 파일 기능은 별도 파일 보존 대책이 필요합니다.

사용자가 배포하면 시작 스크립트는 PostgreSQL에 마이그레이션→역할 초기화→정적 파일 수집→8000 Gunicorn 실행을 유지합니다. production에서는 `seed_demo`를 실행하지 않습니다. **이 순간 기존 SQLite의 교인이 자동 이전되는 것은 아닙니다.** 로그인 공개 전에 터미널에서 다음을 실행합니다.

```sh
python manage.py migrate_sqlite_members --backup-sha BACKUP_SHA256
python manage.py migrate_sqlite_members --backup-sha BACKUP_SHA256 --apply
python manage.py migrate_sqlite_members --backup-sha BACKUP_SHA256 --apply
```

첫 명령은 미리보기, 둘째는 트랜잭션 이관, 셋째는 중복 방지 확인입니다. 예상: 교인 1건, 마지막은 이미 이관한 백업 안내. 명령의 기본 예상 수량은 1건이며 다르면 중단합니다. UUID·이름·연락처·활성/가상 표시·등록일을 보존하고 세션 버전만 증가시킵니다. 이전 세션·OTP는 이전하지 않습니다. 대상에 교인·관리자·사건·글이 이미 있으면 덮어쓰지 않고 중단합니다. 원본에 관리자 또는 다른 업무 데이터가 생겼으면 이 명령 범위를 넘으므로 중단합니다. 이 경우 별도 전체 이관 계획을 준비해야 하며 무시하고 초기화하지 마세요. 외부 백업은 삭제하지 않습니다.

## 4. 원문·복원 JSON 등록

교인 이관 후 서로 다른 작성자·검토자 관리자 계정을 만듭니다. `createsuperuser`를 두 번 실행할 수 있으며 두 계정 모두 개인별 TOTP 추가 인증을 설정합니다. 역할별 권한을 지정하는 경우 작성자는 `portal.add_case`, 검토자는 `portal.publish_case`가 필요합니다. 회원가입을 제공하는 절차가 아닙니다.

실제 입력 파일은 Git 밖의 `/tmp/shinsung-private-input/source.docx`, `/tmp/shinsung-private-input/initial.review.json`에 일시적으로 전달합니다. 디렉터리 700, 파일 600; 확인되지 않은 Cloudtype 업로드 메뉴를 가정하지 않습니다. 파일의 안전한 전달 경로가 없으면 이 단계는 미완료입니다. JSON만으로 원문 대조를 주장하지 않습니다. 등록 명령은 DOCX와 JSON을 직접 대조합니다. 원문 파일명은 관리 명령의 인수 경로와 일치시킵니다.

```sh
python manage.py register_reviewed_materials /tmp/shinsung-private-input/source.docx --plan /tmp/shinsung-private-input/initial.review.json --author EDITOR_USERNAME --reviewer REVIEWER_USERNAME --publish --approval-reason '발췌 범위·분류·개인정보 검토; 공식 원자료 미대조 표시 유지'
python manage.py register_reviewed_materials /tmp/shinsung-private-input/source.docx --plan /tmp/shinsung-private-input/initial.review.json --author EDITOR_USERNAME --reviewer REVIEWER_USERNAME --publish --approval-reason '발췌 범위·분류·개인정보 검토; 공식 원자료 미대조 표시 유지' --apply
```

`python manage.py storage_status`로 비밀값 없는 수량을 확인합니다. 예상 미리보기: 사건 30·규정 11·설명 78·원본 문서 1. 반영 후 게시 사건 30. 같은 명령 재실행은 새 사건/규정/설명 0이며 기존 ID·관리자 수정·비공개 전환을 유지합니다. 원문은 PostgreSQL의 관리자 전용 바이너리 필드, 발췌는 기존 사건·규정·설명 모델에 저장합니다. 트랜잭션 실패 시 부분 반영하지 않습니다. 등록 후 임시 입력 파일은 제거합니다. 본문 파일 배치·`seed_demo`는 필요하지 않습니다.

## 5. 노출된 Django 비밀키 교체

기존 값을 출력하지 마세요. 운영자 자신의 안전한 로컬 환경에서 `secrets.token_urlsafe(64)`로 새 키를 생성하여 비밀번호 관리 도구에 보관하고, Cloudtype의 비밀 환경변수 `DJANGO_SECRET_KEY`만 교체합니다. 노출된 키를 `SECRET_KEY_FALLBACKS`에 넣지 않습니다. 변경 전 외부 백업을 확보합니다. 새 키 적용 후 기존 로그인 세션은 유효하지 않으며 재인증이 필요합니다. 기존 세션과 미사용 인증번호를 제거하는 명령은 `python manage.py invalidate_auth_tokens`입니다. 교인·관리자·게시글은 삭제하지 않습니다. 관리자 TOTP 비밀도 함께 노출되었다면 별도 재등록하고 SMS 업체 키의 노출 여부도 점검합니다.

## 6. 운영 성공 확인과 롤백

기존 기록이 가상 교인이라면 그 기록은 운영 실명 교인의 인증을 대신하지 않습니다. 실제 교인은 기존 관리자 명부 절차로 등록·확인합니다. 실제 SMS 또는 관리자 추가 인증으로 로그인해 30건(E01~E30), 네 영역 세로 순서, 날짜가 확정된 24건과 순서를 확정할 수 없는 6건, 공식 원문 미대조·출처 표기를 확인합니다. 개발 OTP를 허용하지 않습니다. 로그아웃/비활성 접근, 원본 다운로드 제한, `Cache-Control: no-store, private`를 확인합니다. 서비스 재시작·재배포 후 동일 교인 UUID와 30/11/78 수량·본문을 다시 확인합니다. PG 데이터 경로가 앱 `/data`가 아닌 서비스의 확인된 저장소인지 확인합니다.

이 검증은 운영에서 직접 수행해야 합니다. 로컬 Docker 볼륨 재시작 검증은 Cloudtype 영구 보존 증명이 아닙니다. 오류 시 대상/원본/외부 백업을 삭제하지 말고 로그인 공개를 중단합니다. 이전 코드로 돌아갈 때 새 PostgreSQL 데이터를 SQLite로 자동 역이관하거나 임시 DB로 바꾸지 마세요. 검증된 백업과 별도 복구 계획을 먼저 사용합니다.
