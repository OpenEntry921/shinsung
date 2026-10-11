# 교회를 살리는 신도들의 모임 — 교인 전용 독립 앱

COMMON과 연결하지 않는 Django 서버 앱입니다. 교회의 공식 홈페이지·교단의 판단 기관이 아닙니다. 실제 명부·사건·조문 데이터는 포함하지 않습니다. 개발 변경은 별도 브랜치와 PR에서 검토합니다.

## 개발 환경

Python 3.12, Django 5.2, SQLite 영구 DB, 비공개 파일 저장을 사용합니다.

```sh
sh scripts/install.sh
APP_MODE=development .venv/bin/python manage.py seed_demo
APP_MODE=development .venv/bin/python manage.py runserver 127.0.0.1:8000
APP_MODE=development .venv/bin/python manage.py test
```

개발 모드에서 `가상교인` / `01000000000`만 명시적으로 생성합니다. 인증번호는 가상 교인에만 화면에 나타나며 실제 교인의 인증을 처리하지 않습니다. 사건·판결·조문은 시연용으로 채우지 않습니다. 실제 명부를 개발 DB에 업로드하지 마세요. 새로운 작업도 기존 체크아웃을 사용하며 별도의 Git worktree를 만들 필요가 없습니다.

관리자 계정은 `createsuperuser`로 별도 생성합니다. 관리자도 개인별 TOTP 추가 인증이 필수입니다. 공개 운영 전 설정·정책·자료 검증이 필요하며 현재 배포된 서비스가 아닙니다.

[운영·배포·자료 관리 안내](docs/OPERATIONS.md) · [구현 및 검증 범위](docs/STATUS.md)
