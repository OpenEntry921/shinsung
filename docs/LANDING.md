# 공개 랜딩페이지 운영·검증

홈페이지는 영상 → 다섯 쟁점 → 진행 상황 → 기존 72개 사건 타임라인 순서입니다. 공개 메뉴는 핵심 쟁점·사건 기록·진행 상황으로 구성합니다. 전체 공동 상황판과 기존 5단계 로드맵은 기본적으로 접힌 영역에서 그대로 열람합니다. `/#timeline`, `/#dashboard`, `/#roadmap`은 해당 콘텐츠로 이동하며, `/#progress-details`, `/#roadmap-details`는 전체 영역을 펼칩니다. 기존 E01~E30·사건 상세·문서 주소는 유지합니다.

`portal/landing.py`의 `VIDEOS`가 제목·설명·파일명·포스터·관련 사건을 관리하는 단일 목록입니다. 관련 사건은 바뀔 수 있는 표시 번호가 아니라 기존 고유 키를 사용합니다. 사건 본문과 ⑤ 우리의 의견은 수정하지 않습니다. 준비 영역·인증·자료 접근 정책도 변경하지 않습니다.

## 실제 영상과 포스터 추가

이번 작업 시 저장소에는 대상 영상과 포스터가 없었습니다. 재생·내용을 실제 영상으로 검토했다는 의미가 아닙니다. 영상 연결은 요청된 주제와 기존 사건 본문을 대조한 것입니다. 영상 공개 전에 내용과 관련 사건의 일치 여부를 운영자가 확인해야 합니다. 특히 십일조 기록·참석 현황의 수치나 세부 기록은 현재 자료로 확인되지 않아 홈페이지에 추가하지 않았습니다.

다음 파일을 **정확한 이름**으로 `portal/static/portal/videos/`에 추가합니다. 모두 공개 제공이 승인된 최종본만 사용합니다. 비공개 원본이나 개인정보 자료를 이 디렉터리에 넣지 않습니다.

| 영상 | MP4 파일명 | 포스터 파일명 |
| --- | --- | --- |
| 교회에 묻는 다섯 가지 질문 | `권한만큼_책임도_묻습니다_82초_릴스.mp4` | `questions.jpg` |
| 목적헌금의 본질을 훼손하지 마십시오 | `본질과_책임_복직과_바로잡는_용기.mp4` | `offering.jpg` |
| 누가 매일 나오시라고 합니까? | `누가_매일_나오시라고_합니까_참석현황_추가.mp4` | `example.jpg` |

포스터 권장: 세로 1080×1920px(9:16), sRGB JPEG, 가능하면 300KB 이하. 글자는 가장자리와 떨어뜨리고 휴대전화에서도 읽을 수 있게 합니다. 표지는 `object-fit: contain`으로 전체를 보여주며 가로 카드 안에서도 문구를 자르지 않습니다. MP4는 주요 브라우저가 지원하는 H.264/AAC를 권장하며, 빠른 탐색을 위해 faststart 형식으로 내보냅니다. 이번 개편에서 배경음악을 추가하지 않습니다.

업로드 후 기존 배포 절차에서 `python manage.py collectstatic --noinput`을 실행하고 앱 프로세스를 재시작합니다. 새 파일이 정적 파일 manifest에 반영되어야 합니다. 파일이 없거나 manifest 항목이 없으면 “영상 준비 중”으로 표시합니다. 포스터만 있으면 준비 중 표지가 표시되고, 영상만 있으면 제목 표지와 재생 버튼으로 활성화됩니다. 포스터가 없어도 깨진 이미지 요청을 만들지 않습니다. 파일 추가 후 템플릿이나 Python 코드를 바꿀 필요는 없습니다.

정적 URL은 Django 정적 파일 저장소에서 생성합니다. 임시 다운로드 링크·외부 가짜 URL을 사용하지 않습니다. 동영상은 기본적으로 접혀 있으며 `preload="none"`, `playsinline`, 기본 컨트롤을 사용합니다. 사용자가 재생을 누르기 전에는 영상 요청이 발생하지 않아야 합니다. 재생을 누르면 해당 카드가 열리고, 접으면 일시정지합니다. 전체화면과 탐색은 브라우저 기본 컨트롤을 사용합니다. JavaScript 없이도 펼친 후 기본 컨트롤로 재생할 수 있습니다.

## 검증 재현

```sh
cd /workspace/shinsung
APP_MODE=development .venv/bin/python manage.py check
APP_MODE=development .venv/bin/python manage.py makemigrations --check --dry-run
APP_MODE=development .venv/bin/python manage.py collectstatic --noinput
APP_MODE=development .venv/bin/python manage.py test
```

브라우저 검증 스크립트는 선택 개발 도구인 Node.js Playwright와 Chromium을 사용합니다. 환경에 없다면 별도 도구 디렉터리에 Playwright를 설치하고 `NODE_PATH`를 지정합니다. 앱 의존성은 변경하지 않습니다.

```sh
# 예: npm install --prefix /tmp/laity-browser playwright
# export NODE_PATH=/tmp/laity-browser/node_modules
APP_MODE=development .venv/bin/python manage.py runserver 127.0.0.1:8001 --noreload --insecure
# 다른 터미널:
LANDING_ARTIFACTS=/tmp/laity-landing-artifacts node scripts/verify_landing_browser.cjs
```

`--insecure`는 로컬 개발 서버에서 정적 파일을 제공하는 Django 옵션이며 TLS 검증 해제 옵션이 아닙니다. 운영에서 사용하지 않습니다. `LANDING_BASE_URL`, `CHROMIUM_PATH`, `LANDING_ARTIFACTS`로 검사 대상·브라우저·결과 경로를 지정할 수 있습니다. 실제 영상 3개가 모두 추가된 상태는 `LANDING_MEDIA=ready`로 검사합니다. 탐색 검증은 2초 지점으로 이동하므로 영상은 2초보다 길어야 합니다.

파일이 없는 기본 상태와, 체크아웃 밖 임시 정적 디렉터리에 합성 MP4/포스터를 둔 상태를 각각 검사합니다. 합성 테스트 영상은 실제 콘텐츠의 대체물이 아니며 저장소나 운영 정적 디렉터리에 추가하지 않습니다. 합성 파일 검증은 플레이어 기능만 확인하며 실제 세 영상의 내용·음성·전체 길이 검증을 대신하지 않습니다.

1440px/390px에서 초기 영상 요청 수, 콘솔 오류, 가로 넘침, 주요 버튼, 직접 앵커, 뒤로가기, 키보드로 기록 펼치기, 72개 타임라인 링크를 확인합니다. 영상 준비 상태에서는 재생·일시정지·2초 탐색·전체화면·접기 시 일시정지를 확인합니다. 운영체제·실제 휴대전화별 네이티브 컨트롤 차이는 별도 실기기 확인 대상입니다.

영상 탐색은 HTTP Range를 지원하는 실제 Gunicorn/WhiteNoise 정적 파일 경로에서 확인합니다. Django 개발 서버의 정적 파일 응답은 Range 처리가 달라 탐색 검증에 적합하지 않습니다. 실제 파일 추가·collectstatic 후 `APP_MODE=development PATH="/workspace/shinsung/.venv/bin:$PATH" sh scripts/start-production.sh`로 시작하고 `LANDING_BASE_URL=http://127.0.0.1:8000 LANDING_MEDIA=ready node scripts/verify_landing_browser.cjs`를 사용합니다.

## 이번 변경의 화면

실제 영상이 없는 기본 상태입니다. 전체 타임라인은 첫 화면 아래에 유지됩니다.

[데스크톱 1440px](landing-screenshots/desktop.png) · [모바일 390px](landing-screenshots/mobile.png)

## 실행 결과

- Django check, 마이그레이션 변경 검사, collectstatic: 통과.
- 전체 Django 테스트: 172개 통과. 기존 공개 열람·문서 권한·준비 영역 접근과 세션 격리·사건/의견 보존 검사 포함.
- 백업/복구, 체크섬 불일치와 비어 있지 않은 복구 대상 거부: 통과.
- Chromium 1440×1000, 390×844: 영상 없음/합성 영상 있음 모두 통과. 72개 링크·순서, 핵심 버튼, 기존 앵커, 직접 URL, 뒤로가기, 키보드 조작, 콘솔 오류 0건, 가로 넘침 없음 확인.
- Gunicorn/WhiteNoise에서 합성 MP4 3개: 재생·일시정지·2초 탐색·전체화면·접기 시 정지 통과. 최초 로딩 영상 요청 0건.
- 실제 요청 영상 3개 및 실제 포스터: 미제공. 내용·음성·실제 길이·실기기 재생은 미검증. 임시 합성 파일은 저장소와 운영에 포함하지 않음.
- 기존 사건 본문·⑤ 우리의 의견·준비 영역 구현·접근 미들웨어·URL·모델·마이그레이션에 변경 없음. 운영 배포는 수행하지 않음.
