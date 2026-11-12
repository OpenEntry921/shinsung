# 공개 랜딩페이지 운영·검증

홈페이지는 영상 → 다섯 쟁점 → 진행 상황 → 기존 72개 사건 타임라인 순서입니다. 공개 메뉴는 핵심 쟁점·사건 기록·진행 상황으로 구성합니다. 전체 공동 상황판과 기존 5단계 로드맵은 기본적으로 접힌 영역에서 그대로 열람합니다. `/#timeline`, `/#dashboard`, `/#roadmap`은 해당 콘텐츠로 이동하며, `/#progress-details`, `/#roadmap-details`는 전체 영역을 펼칩니다. 기존 E01~E30·사건 상세·문서 주소는 유지합니다.

`portal/landing.py`의 `VIDEOS`가 제목·설명·파일명·포스터·관련 사건을 관리하는 단일 목록입니다. 관련 사건은 바뀔 수 있는 표시 번호가 아니라 기존 고유 키를 사용합니다. 실제 영상 연결 작업에서는 기존 카드 제목·설명·관련 기록·디자인·정보 구조를 변경하지 않았습니다.

## 연결된 실제 영상

세 파일은 사용자가 첨부한 MP4 원본입니다. 업로드 순서 대신 길이와 여러 시점의 화면을 확인해 대응시켰습니다. 문구·순서·길이를 수정하거나 재인코딩·재다중화하지 않았습니다. 원본 모두 1080×1920 H.264이며 **오디오 트랙이 없습니다**. 음성·배경음악·효과음을 추가하지 않았습니다. 영상 속 주장이나 통계를 이번 작업에서 별도로 검증·재작성한 것은 아닙니다.

파일은 기존 앱 정적 디렉터리인 `portal/static/portal/videos/`에 직접 포함합니다. 개별 크기는 약 3.65MiB / 1.37MiB / 1.27MiB로 GitHub 단일 파일 제한(100MiB) 미만입니다. Git LFS와 외부 영상 호스팅은 사용하지 않습니다.

| 카드 | 첨부 원본 식별명 | 저장 파일 | 길이 | 크기(bytes) | 표지 |
| --- | --- | --- | --- | --- | --- |
| 교회에 묻는 다섯 가지 질문 | 권한만큼_책임도_묻습니다_최종카드_무음릴스.mp4 | `church-questions.mp4` | 86초 | 3,822,225 | `questions.jpg` |
| 목적헌금의 본질을 훼손하지 마십시오 | 본질과_책임_십일조수치_수정.mp4 | `offering-and-restoration.mp4` | 82초 | 1,438,080 | `offering.jpg` |
| 누가 매일 나오시라고 합니까? | 누가_매일_나오시라고_합니까_참석수치_사역목록_수정.mp4 | `prayer-and-service.mp4` | 58초 | 1,329,066 | `example.jpg` |

첫 영상은 최신 카드뉴스의 01/07~07/07 화면을 확인했습니다. 두 번째 영상의 십일조 장면(약 50초)에는 “9월 1명 · 10월 2명”이 표시됩니다. 세 번째 영상의 04/07 화면(약 26초)은 수요예배·다니엘기도회가 각각 “5% 미만”이며, 사역실행위원회·전교인 수련회·마을사역·성경공부·구역모임·기도모임·더자람데이·더자람위원회·각 공동체 리트릿 등으로 사역 목록이 수정된 것을 확인했습니다. 표지는 각각 **2초 지점**의 선명한 첫 본문 화면에서 JPEG로 추출했습니다. 각 표지는 1080×1920이며 새 문구·가림·장식을 덧씌우지 않았습니다. 기존 `object-fit: contain`으로 표지와 영상 전체를 표시합니다.

원본과 저장 파일의 SHA-256이 동일합니다. 테스트에서도 이 값으로 잘못된 교체·LFS 포인터·파일 누락을 확인합니다.

```text
church-questions.mp4
c4df5b4ac30c2a067597b5f1fa0d21cd1dd60c1e75162dff9d46de5c2479c903
offering-and-restoration.mp4
f4e88bdc204e55fb524212a96720adbf56fcfdc1eb8a96c16d894067a1be1f49
prayer-and-service.mp4
acb7fadfa34b437a60e720e978ad29830b937cf33ab8ce6bfdeefcfc20a502c0
```

## 정적 파일 배포와 재생 경로

기존 Dockerfile이 앱의 실제 바이너리를 이미지에 복사합니다. 기존 `scripts/start-production.sh`가 collectstatic을 수행하고 WhiteNoise가 파일을 제공합니다. 로컬 이미지의 소스·수집된 파일을 확인했으며, 로컬 Gunicorn/WhiteNoise의 HTTP 전체 응답 SHA-256도 첨부 원본과 일치했습니다. 준비 상태를 결정하는 기존 `asset_url()`은 소스 또는 수집된 정적 파일의 존재와 manifest URL을 확인합니다. 파일이 없거나 manifest 항목이 없으면 “영상 준비 중”으로 돌아가며, 잘못된 플레이어를 출력하지 않습니다.

논리 경로는 `/static/portal/videos/<영문 파일명>`이며 Django manifest 저장소가 실제 페이지에 해시 경로를 출력합니다. 이번 파일을 수집한 결과는 다음과 같습니다. 파일을 교체하면 해시는 바뀌므로 **템플릿에 이 해시를 하드코딩하지 않습니다**.

| 파일 | 실제 페이지의 재생 경로 |
| --- | --- |
| `church-questions.mp4` | `/static/portal/videos/church-questions.2574cfc12316.mp4` |
| `offering-and-restoration.mp4` | `/static/portal/videos/offering-and-restoration.5ded3d1218db.mp4` |
| `prayer-and-service.mp4` | `/static/portal/videos/prayer-and-service.b288987c1c32.mp4` |

로컬 절대 경로·임시 다운로드 주소·GitHub blob 링크·외부 임베드를 사용하지 않습니다. CSP·접근 제어·noindex/nofollow는 변경하지 않습니다. 비공개 원본이나 개인정보 파일을 이 공개 정적 디렉터리에 추가하지 않습니다.

동영상은 기본적으로 접혀 있으며 `preload="none"`, `poster`, `playsinline`, 기본 컨트롤을 유지합니다. 사용자의 재생 동작 전에는 MP4 요청이 없습니다. 접으면 일시정지하며 JavaScript 없이도 펼친 후 기본 컨트롤로 재생할 수 있습니다. 소스 로딩 실패 시 “영상을 불러오지 못했습니다. 아래 관련 기록을 먼저 살펴보세요.”를 표시합니다.

## 검증 재현

```sh
cd /workspace/shinsung
APP_MODE=development .venv/bin/python manage.py check
APP_MODE=development .venv/bin/python manage.py collectstatic --noinput
APP_MODE=development .venv/bin/python manage.py test portal.test_landing portal.test_public_reading portal.test_public_case_documents portal.test_preparation portal.test_appeals
```

브라우저 검증에는 별도 개발 도구인 Node.js Playwright와 Chromium을 사용합니다. 없다면 별도 도구 디렉터리에 Playwright를 설치하고 `NODE_PATH`를 지정합니다. 앱 의존성을 바꿀 필요는 없습니다.

```sh
# 예: npm install --prefix /tmp/laity-browser playwright
# export NODE_PATH=/tmp/laity-browser/node_modules
APP_MODE=development PATH="/workspace/shinsung/.venv/bin:$PATH" sh scripts/start-production.sh
# 다른 터미널:
LANDING_BASE_URL=http://127.0.0.1:8000 LANDING_ARTIFACTS=/tmp/laity-video-artifacts node scripts/verify_landing_browser.cjs
```

스크립트는 기본적으로 설치된 실제 영상 3개를 검사합니다. 파일 부재를 따로 검사하는 환경은 `LANDING_MEDIA=absent`를 지정합니다. `CHROMIUM_PATH`로 Chromium 위치를 바꿀 수 있습니다. 로컬 **운영 모드** 컨테이너를 검사할 때에만 `LANDING_FORWARDED_HTTPS=true`로 신뢰 프록시 헤더를 전달합니다. 실제 사이트를 HTTP로 운영하기 위한 설정이 아닙니다.

탐색은 HTTP Range를 지원하는 실제 Gunicorn/WhiteNoise 경로에서 검사합니다. Django 개발 서버의 정적 파일 응답은 Range 처리가 달라 탐색 검증에 적합하지 않습니다.

## 최신 수정본 교체 검증 결과

- Django check와 collectstatic 통과.
- 관련 Django 테스트 **37개 통과**: 실제 파일 무결성·카드 연결, 파일/포스터 부재 fallback, 수집된 파일만 남은 환경, 72개 사건·공개 열람·문서 권한, 준비 영역 접근·세션 격리와 모금 안내 보존 포함.
- 기존 Dockerfile로 로컬 이미지 빌드 통과. 이미지 안 실제 MP4 3개·표지 3개와 collectstatic 결과 확인. 브라우저 검사는 개발 모드의 로컬 Gunicorn/WhiteNoise에서 수행함.
- 세 실제 MP4의 HTTP 전체 응답: 200, `video/mp4`, 원본 SHA-256 일치. `Range: bytes=1000-2023` 요청: 206, 올바른 Content-Range와 해당 1,024바이트 일치. 표지 응답: 200, `image/jpeg`.
- Chromium 1440×1000 / 390×844: 세 영상 각각 재생·일시정지·2초 탐색·전체화면·접기 시 정지 통과. 초기 MP4 요청 0건, 정상 경로 콘솔 오류/404 없음, 가로 넘침 없음, 표지 원본 비율·contain 확인.
- 핵심 버튼·직접 앵커·뒤로가기·키보드 접근·기존 사건 링크 유지 확인. 의도적으로 영상 응답을 실패시킨 별도 검사에서 안내 문구 표시 확인.
- 실제 첨부 영상으로 로컬 브라우저를 검사했으며 합성 영상으로 대체하지 않음. 실제 휴대전화·운영 도메인/CDN의 배포 결과는 아직 미검증. 운영 모드 컨테이너의 전체 앱 구동 검사는 읽기 전용으로 연결한 호스트 DB의 UID/파일 권한 차이로 완료하지 못했으며, DB나 원본 권한을 변경하지 않고 로컬 Gunicorn/WhiteNoise에서 재생 검사를 완료함.
- 운영 배포·자동 병합·main 직접 반영은 수행하지 않음. 기존 사건 본문·⑤ 우리의 의견·준비 영역 구현·인증/MFA·접근 미들웨어·URL·모델·마이그레이션은 변경하지 않음.

이전 연결 작업의 참고 화면: [데스크톱 첫 화면](landing-screenshots/desktop.png) · [모바일 첫 화면](landing-screenshots/mobile.png) · [데스크톱 영상 카드](landing-screenshots/video-cards-desktop.png) · [모바일 영상 카드](landing-screenshots/video-cards-mobile.png)

## 병합·배포 후 확인

배포 담당자가 기존 배포 절차를 실행한 뒤 `https://laity.kr`에서 세 표지와 영상을 확인합니다. 실제 배포 manifest의 해시 URL에 대해 MP4 MIME, 200/206과 Content-Range, 초기 MP4 요청 0건을 확인합니다. CDN이 있다면 Range 응답과 캐시된 구버전 여부도 확인합니다. iOS Safari·Android Chrome 실기기에서 재생·일시정지·탐색·전체화면 및 세로 화면의 전체 문구 표시를 확인합니다. 운영 설정의 CSP·noindex/nofollow와 비공개 영역 보호를 유지합니다. 이번 작업은 이 운영 배포를 수행하지 않았습니다.
