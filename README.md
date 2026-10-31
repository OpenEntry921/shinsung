# 교회를 살리는 신도들의 모임 — 교인 전용 독립 앱

교인 전용 독립 Django 서버 앱입니다. 교회의 공식 홈페이지·교단의 판단 기관이 아닙니다. 실제 명부·신청·댓글 DB는 포함하지 않습니다. 기존 사건 30건의 HTML 본문은 저장소에 포함되어 있으므로 저장소 공개 범위와 자료 취급을 별도로 검토해야 합니다. 개발 변경은 별도 브랜치와 PR에서 검토합니다.

## 개발 환경

Python 3.12, Django 5.2, SQLite 영구 DB, 비공개 파일 저장을 사용합니다.

```sh
sh scripts/install.sh
APP_MODE=development .venv/bin/python manage.py test
. .venv/bin/activate
APP_MODE=development sh scripts/start-production.sh
```

개발은 `APP_MODE=development`, 운영은 `APP_MODE=production`을 사용합니다. 시작 시 샘플 교인이나 운영 데이터를 자동 생성하지 않습니다. 서버에서 개별 지정된 기존 운영자는 종전 이름·전화번호 로그인으로 내부 화면과 본인 댓글에 접근합니다. 일반 교인·신규 이용자의 동의·확인·승인 요건은 유지합니다. [로그인 복구·운영 반영 순서](docs/LOGIN_RECOVERY.md)를 확인하세요. 기존 체크아웃을 사용하며 별도 Git worktree를 만들지 않습니다.

[통합 개편 검토·운영 전 설정](docs/INTEGRATION_REVIEW.md)을 먼저 확인하세요. 가입 접수는 운영 주체·연락처·보유기간·교회 수신 창구가 모두 확정되기 전 차단됩니다. 개인정보를 자동 전송하지 않습니다.

관리자 계정은 `createsuperuser`로 별도 생성합니다. 관리자도 개인별 TOTP 추가 인증이 필수입니다. 공개 운영 전 설정·정책·자료 검증이 필요하며 현재 배포된 서비스가 아닙니다.

[운영·배포·자료 관리 안내](docs/OPERATIONS.md) · [구현 및 검증 범위](docs/STATUS.md)

`DATA_DIR` 설정과 실제 영구 디스크 연결은 다릅니다. 운영 전 외부 비공개 백업·복구와 동일 영구 볼륨 재시작 후 보존을 확인해야 합니다.

[인증된 사건 HTML 본문 안내](docs/CASE_REVIEW.md). 사건 30건의 발췌를 Django 템플릿에서 직접 렌더링합니다. 사건 DB·외부 본문 파일은 필요하지 않으며 기존 교인 인증 DB는 유지합니다. 이미 저장소에 있는 사건 본문은 유지하며 새 비공개 자료를 PR에 추가하지 않습니다. 운영 인증과 로그인 DB 보존은 별도 확인이 필요합니다.
