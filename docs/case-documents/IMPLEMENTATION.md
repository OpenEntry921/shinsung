# 개인정보 가림 사본 연결 구현·검증 보고 (2026-11-05)

## 상태: 코드 준비됨 / 실물 미확보 / 운영 미확인

자료 브랜치 `docs/add-redacted-case-files`의 `ed0ee14`를 조사했습니다. 연결표와 안내·CSV2개는 있지만 `static/case-documents/`의 문서28개는 없습니다. 첨부 `Shinsung_Redacted_Documents_20261105.zip`은 다운로드 도구의 32MiB 한도를 초과해 전송되지 않았습니다. 최초 원본이나 가상 문서로 대신하지 않았습니다. 이 브랜치에는 실제 문서가 아직 포함되지 않으며 **웹 연결 완료가 아닙니다. 문서 파일 확보·검증 전에는 이 변경을 운영 완료로 취급하지 마세요.**

기준은 main `f18411a`(PR #23, 의견 초안15개 포함)이고 작업 브랜치는 `codex/connect-redacted-case-documents`입니다. 자료 브랜치의 앱 코드를 가져오지 않고 연결표·자료 안내·CSV만 선별 반영했습니다. CSV의 BOM과 모든 필드 값은 유지하고 줄끝만 LF로 정리했습니다.

## 구현과 보존

- `portal/public_case_documents.py`: 승인 ID/경로28개만 검증. 중복·외부/상위경로·형식·0바이트·크기 불일치·심볼릭 링크를 거부하고 누락 파일에 공개 링크를 만들지 않습니다. URL은 Django static resolver에서 생성합니다.
- `portal/reading_registry.py`: 기존 보호된 HTML의 출처 목록을 HTMLParser로 읽어 기존 키에 인용 위치를 연결합니다. 사건 본문·의견 템플릿은 바꾸지 않았습니다.
- `portal/templatetags/timeline_tags.py`, `timeline_document.html`: 검증된 가림 사본을 새 탭으로 연결. 비연속 쪽수는 각각, 범위는 시작점으로 링크하며 원래 인용 전체는 그대로 표시합니다. C02에는 page fragment가 없고 S01은 이번 자료에 미포함입니다. 기존 DB Document의 검토된 비공개 경로는 별도로 유지합니다.
- `config/settings.py`: 루트 static만 추가 수집. 기존 WhiteNoise/manifest/STATIC_ROOT/시작 절차/인증/DB 설정 보존.
- `.gitignore`, `.dockerignore`: 승인된 정확한28개 경로만 예외. 다른 PDF·DOCX·명부·DB 차단 유지.
- `verify_case_documents`: 실제 파일·크기·형식·PDF쪽수·JPG 디코딩·전체 사건 인용 검증. 실패는 종료 코드1, 개별 오류는 내부 절대경로나 문서 본문 없이 표시합니다. `--report`는 지정한 경로에 권한600으로 보고서를 생성합니다. pdfinfo와 identify가 없는 환경에서는 실제 쪽수/이미지를 검증했다고 처리하지 않습니다.
- `portal/test_public_case_documents.py`, 기존 관련 테스트: 경로·쪽수·manifest URL·누락·개인정보 가림 표시·기존 비공개 Document와 인증 회귀 검사.
- `static/.gitkeep`: 디렉터리 유지용이며 더미 문서가 아닙니다.

72개 통합사건·기존 E01~E30·안정 키·댓글/답글·의견15개·네 영역·기존 출처 문구를 보존했습니다. DB 마이그레이션·문서 DB 등록·시드·운영 환경변수 변경이 없습니다. 승인된 공개 사본 외 타임라인·댓글·원본 파일의 접근 제한과 보안 헤더를 완화하지 않았습니다.

## 실제 검사 결과

- 전체 테스트 **136개 통과**. check·마이그레이션 누락 검사·diff 검사 통과.
- 연결표28개는 PDF27개/489쪽, JPG1개/1장으로 합계490입니다. 이는 **메타데이터의 합계**이고 실물 쪽수 검증은 미완료입니다.
- 실제 파일은 **0/28**입니다. `verify_case_documents`는28개 누락을 보고하고 정상적으로 실패했습니다. findstatic 실제 문서 검색·실물 manifest URL/HTTP/해시·Docker 이미지 포함 여부는 미검증이며 완료로 보고하지 않습니다.
- 원래72개 사건의 인용156곳 중140곳이 승인 자료 인용,16곳이 S01입니다. 승인 자료 인용의 모든 쪽수가 연결표 범위 내임을 확인했습니다. 파일명·ID 특례와 표시 번호/안정 키 대응을 유지합니다.
- 실제 코드의 collectstatic 성공(문서는 없음). 기존 CSS·이미지 수집 유지.
- **별도 임시 가상 파일만 사용하는 전송 검사**: DEBUG=False, manifest 해시 URL, WhiteNoise/Gunicorn에서28개 HEAD의200·MIME·길이 및 PDF/JPG GET 바이트 확인. 실제 첨부 가림 문서 검사와 다릅니다. 임시 파일은 저장소·변경 목록에 포함하지 않았습니다.
- Chromium PC1280/모바일390에서 실제 사건 본문·OP15·네 영역·기존 탐색·권한·가로 넘침 없음 확인. 별도 가상 파일 환경에서는 A05/A06/A11변경·비연속 쪽수·이미지·S01의 링크 표시도 확인했습니다. 실물 PDF 내용/실제 뷰어 이동을 확인한 것은 아닙니다.
- 운영 Cloudtype 확인·배포·재시작은 하지 않았습니다. PR 생성·머지·리뷰 요청도 하지 않습니다.

## 실제 파일 확보 후 진행

승인 가림 사본28개를 자료 브랜치에 올리거나 ZIP을 각각32MiB 이하로 나누어 작업환경에 제공해야 합니다. 최초 개인정보 원본 ZIP은 사용하지 않습니다. 전역 PDF 차단을 풀거나 `git add -f`로 우회하지 마세요.

자료 브랜치에 파일이 실제 올라온 뒤 작업 브랜치에서 다음을 수행할 수 있습니다. 현재 자료 브랜치에는 파일이 없어 이 restore는 아직 실행할 수 없습니다.

```sh
git switch codex/connect-redacted-case-documents
git fetch origin refs/heads/docs/add-redacted-case-files:refs/remotes/origin/docs/add-redacted-case-files
git restore --source origin/docs/add-redacted-case-files -- static/case-documents/
python manage.py verify_case_documents
python manage.py findstatic case-documents/A01.pdf case-documents/A11-change.pdf case-documents/C02.jpg
python manage.py collectstatic --noinput
```

나머지25개도 findstatic과 해시 URL HEAD/GET로 확인합니다. verify에는 pdfinfo/identify가 필요합니다. 실제 파일의 크기가 현재 연결표와 다르면 버전과 가림 처리본을 대조한 뒤 승인된 연결표만 정정하며 임의로 bytes를 덮어쓰지 않습니다.28개 모두 통과하고 원본·추가 파일이 섞이지 않았는지 확인한 뒤 정확한 승인 경로만 선택합니다.

```python
# 프로젝트 .venv Python에서 실행. 승인 목록 밖의 파일을 stage하지 않습니다.
import subprocess
from portal.public_case_documents import APPROVED
subprocess.run(['git','add','--',*['static/case-documents/'+name for name in APPROVED.values()]],check=True)
```

사용자가 실제 파일 검증 결과까지 검토해 커밋·푸시하고, base main / compare codex/connect-redacted-case-documents로 PR을 직접 생성·검토·병합합니다. 코드 브랜치 업로드는 자료 실물 업로드 완료나 운영 반영 완료가 아닙니다. main 자동 배포 연결 여부는 확인되지 않았으므로 병합 전 운영 설정을 확인합니다.

기존 Cloudtype 배포 흐름을 사용하고 별도 자료 DB 등록 명령은 없습니다. collectstatic은 기존 시작 스크립트가 수행합니다. 배포 후에는 로그인 전 대표 해시 PDF/JPG 직접 GET의200/형식/길이, 로그인 후 T01의 A01 2·7쪽·T26의 A11변경·T57의 이미지·S01 미포함·기존 의견 표시를 확인합니다. 로그아웃한 사건 직접 URL은 로그인으로 보내야 합니다. 브라우저별 PDF fragment 지원은 다르므로 인용 쪽수는 계속 화면에 보입니다. 원래 비공개 파일이 공개되지 않았는지도 별도 확인합니다.

되돌리기는 이 작업의 코드/정적 파일 커밋을 되돌리는 방식이며 DB 초기화·복원·교인 기록 변경이 필요하지 않습니다.

## 수동 PR 초안

제목: **승인된 개인정보 가림 사본의 사건별 원문 링크 연결**

본문: 기존72개 통합사건과 의견·인증을 유지하면서 승인된 자료28개를 Django 정적 파일 resolver로 연결하는 경로를 추가했습니다. 개별/범위/비연속 쪽수와 A05/A06·A11변경·이미지·미포함 S01을 구분하고, 누락·잘못된 파일에는 링크를 만들지 않습니다. 기존 비공개 Document 경로는 유지합니다. 정확한28개 경로만 Git/Docker 공개 예외를 추가했습니다. DB 변경은 없습니다. **현재 실제 문서가 없어 코드 준비 상태이며, 실물 추가·검증 후 병합해야 합니다.** 검사 결과와 남은 제한은 본 문서를 참고하십시오.

## 승인 자료와 현재 실물 상태

| ID | 파일 | 연결표 쪽수/장 | 연결표 bytes | 실물 |
|---|---|---:|---:|---|
| B01 | static/case-documents/B01.pdf | 26 | 5156639 | 없음 |
| B02 | static/case-documents/B02.pdf | 19 | 4449985 | 없음 |
| B03 | static/case-documents/B03.pdf | 2 | 339445 | 없음 |
| B04 | static/case-documents/B04.pdf | 2 | 466207 | 없음 |
| B05 | static/case-documents/B05.pdf | 8 | 1681929 | 없음 |
| B06 | static/case-documents/B06.pdf | 20 | 4947379 | 없음 |
| B07 | static/case-documents/B07.pdf | 5 | 2733080 | 없음 |
| B08 | static/case-documents/B08.pdf | 3 | 696036 | 없음 |
| C01 | static/case-documents/C01.pdf | 60 | 17304466 | 없음 |
| C02 | static/case-documents/C02.jpg | 1 | 899589 | 없음 |
| C03 | static/case-documents/C03.pdf | 7 | 2060234 | 없음 |
| C04 | static/case-documents/C04.pdf | 3 | 383186 | 없음 |
| C05 | static/case-documents/C05.pdf | 3 | 812296 | 없음 |
| C06 | static/case-documents/C06.pdf | 2 | 570151 | 없음 |
| D01 | static/case-documents/D01.pdf | 48 | 13372168 | 없음 |
| E01 | static/case-documents/E01.pdf | 2 | 650143 | 없음 |
| A01 | static/case-documents/A01.pdf | 23 | 7089323 | 없음 |
| A11 | static/case-documents/A11.pdf | 10 | 3635635 | 없음 |
| A11변경 | static/case-documents/A11-change.pdf | 60 | 17795764 | 없음 |
| A12 | static/case-documents/A12.pdf | 24 | 16238076 | 없음 |
| A02 | static/case-documents/A02.pdf | 14 | 2398747 | 없음 |
| A03 | static/case-documents/A03.pdf | 8 | 4143012 | 없음 |
| A04 | static/case-documents/A04.pdf | 8 | 7121125 | 없음 |
| A06 | static/case-documents/A06.pdf | 43 | 15113234 | 없음 |
| A05 | static/case-documents/A05.pdf | 26 | 8349278 | 없음 |
| A07 | static/case-documents/A07.pdf | 18 | 5152010 | 없음 |
| A08 | static/case-documents/A08.pdf | 19 | 5903898 | 없음 |
| A09 | static/case-documents/A09.pdf | 26 | 8414312 | 없음 |

## 사건별 인용 연결 검사

파일 확보를 뜻하지 않는 인용 메타데이터입니다. 같은 문서의 반복 인용도 서로 다른 쪽수를 보존합니다. T28의 A06 4쪽과43쪽을 각각 연결합니다.

| 안정 사건 키 | 자료 ID | 파일 | 기존 인용 위치 | 상태 |
|---|---|---|---|---|
| T01 | A01 | A01.pdf | 2·7쪽 | 실물 없음 |
| T01 | A08 | A08.pdf | 8쪽 | 실물 없음 |
| T01 | B01 | B01.pdf | 24쪽 | 실물 없음 |
| T02 | B01 | B01.pdf | 6쪽 | 실물 없음 |
| T02 | B05 | B05.pdf | 8쪽 | 실물 없음 |
| T03 | A01 | A01.pdf | 4쪽 | 실물 없음 |
| T03 | A03 | A03.pdf | 1~6쪽 | 실물 없음 |
| T03 | A12 | A12.pdf | 14~15쪽 | 실물 없음 |
| T03 | C01 | C01.pdf | 18~20쪽 | 실물 없음 |
| T04 | A01 | A01.pdf | 4쪽 | 실물 없음 |
| T04 | A07 | A07.pdf | 9~10쪽 | 실물 없음 |
| T04 | A12 | A12.pdf | 15쪽 | 실물 없음 |
| T05 | A07 | A07.pdf | 9~10쪽 | 실물 없음 |
| T05 | A12 | A12.pdf | 15쪽 | 실물 없음 |
| T06 | A01 | A01.pdf | 2쪽 | 실물 없음 |
| T06 | A07 | A07.pdf | 7~8쪽 | 실물 없음 |
| T06 | A12 | A12.pdf | 3~4쪽 | 실물 없음 |
| T07 | A07 | A07.pdf | 6쪽 | 실물 없음 |
| T07 | A11 | A11.pdf | 3쪽 | 실물 없음 |
| T07 | B01 | B01.pdf | 9쪽 | 실물 없음 |
| T07 | D01 | D01.pdf | 3~5쪽 | 실물 없음 |
| T08 | B01 | B01.pdf | 9~10쪽 | 실물 없음 |
| T08 | D01 | D01.pdf | 3~6쪽 | 실물 없음 |
| T08 | S01 | 묶음 미포함 | 2절 D 사건·통합 시간표·쟁점별 대조표 | 묶음 미포함 |
| T09 | B01 | B01.pdf | 9~10쪽 | 실물 없음 |
| T09 | D01 | D01.pdf | 10쪽 이하 첨부 회의록 | 실물 없음 |
| T10 | A01 | A01.pdf | 10~12쪽 | 실물 없음 |
| T10 | A08 | A08.pdf | 8쪽 | 실물 없음 |
| T10 | A12 | A12.pdf | 13~14쪽 | 실물 없음 |
| T11 | B01 | B01.pdf | 20~22쪽 | 실물 없음 |
| T11 | A08 | A08.pdf | 8쪽 | 실물 없음 |
| T11 | B05 | B05.pdf | 8쪽 | 실물 없음 |
| T12 | A07 | A07.pdf | 6~8쪽 | 실물 없음 |
| T13 | A01 | A01.pdf | 11~12쪽 | 실물 없음 |
| T13 | A08 | A08.pdf | 8쪽 | 실물 없음 |
| T13 | A12 | A12.pdf | 9~10쪽 | 실물 없음 |
| T14 | A07 | A07.pdf | 9~10쪽 | 실물 없음 |
| T14 | A12 | A12.pdf | 15쪽 | 실물 없음 |
| T15 | A07 | A07.pdf | 4~5·11쪽 | 실물 없음 |
| T15 | B01 | B01.pdf | 18~20쪽 | 실물 없음 |
| T15 | A12 | A12.pdf | 10쪽 | 실물 없음 |
| T16 | A01 | A01.pdf | 12~14쪽 | 실물 없음 |
| T16 | A08 | A08.pdf | 2~6쪽 | 실물 없음 |
| T16 | A12 | A12.pdf | 13쪽 | 실물 없음 |
| T17 | A07 | A07.pdf | 7~8쪽 | 실물 없음 |
| T17 | A12 | A12.pdf | 7·11쪽 | 실물 없음 |
| T18 | A01 | A01.pdf | 6쪽 | 실물 없음 |
| T18 | B01 | B01.pdf | 10~16쪽 | 실물 없음 |
| T18 | A12 | A12.pdf | 15~16쪽 | 실물 없음 |
| T19 | A04 | A04.pdf | 5쪽 | 실물 없음 |
| T19 | A07 | A07.pdf | 10쪽 | 실물 없음 |
| T19 | A12 | A12.pdf | 15쪽 | 실물 없음 |
| T20 | A01 | A01.pdf | 5~6·12쪽 | 실물 없음 |
| T20 | A07 | A07.pdf | 4~5·11쪽 | 실물 없음 |
| T20 | A12 | A12.pdf | 10·15~16쪽 | 실물 없음 |
| T21 | A12 | A12.pdf | 10~11쪽 | 실물 없음 |
| T22 | B01 | B01.pdf | 8~9쪽 | 실물 없음 |
| T22 | A09 | A09.pdf | 13~15쪽 | 실물 없음 |
| T23 | B01 | B01.pdf | 7·16~18쪽 | 실물 없음 |
| T23 | A04 | A04.pdf | 3쪽 | 실물 없음 |
| T23 | A07 | A07.pdf | 6쪽 | 실물 없음 |
| T24 | A01 | A01.pdf | 1~6·23쪽 | 실물 없음 |
| T25 | A06 | A06.pdf | 13~14쪽 | 실물 없음 |
| T25 | A11 | A11.pdf | 5쪽 | 실물 없음 |
| T25 | B01 | B01.pdf | 8쪽 | 실물 없음 |
| T26 | A06 | A06.pdf | 14쪽 | 실물 없음 |
| T26 | A11변경 | A11-change.pdf | 9~10쪽 | 실물 없음 |
| T27 | A02 | A02.pdf | 1~3쪽 | 실물 없음 |
| T27 | B01 | B01.pdf | 13쪽 | 실물 없음 |
| T28 | B01 | B01.pdf | 7쪽 | 실물 없음 |
| T28 | A06 | A06.pdf | 4쪽 | 실물 없음 |
| T28 | A06 | A06.pdf | 43쪽 | 실물 없음 |
| T28 | S01 | 묶음 미포함 | 통합 시간표 2025.10.12 행 및 2절 B 사건 | 묶음 미포함 |
| T29 | A03 | A03.pdf | 1·4~8쪽 | 실물 없음 |
| T29 | A09 | A09.pdf | 2~7쪽 | 실물 없음 |
| T29 | A12 | A12.pdf | 16~17쪽 | 실물 없음 |
| T30 | B01 | B01.pdf | 1~5·23·26쪽 | 실물 없음 |
| T31 | A12 | A12.pdf | 7·11쪽 | 실물 없음 |
| T31 | A11변경 | A11-change.pdf | 6~7쪽 | 실물 없음 |
| T32 | B02 | B02.pdf | 5~8·12~13·18~19쪽 | 실물 없음 |
| T33 | B02 | B02.pdf | 9~12쪽 | 실물 없음 |
| T33 | C01 | C01.pdf | 43~44쪽 | 실물 없음 |
| T34 | B02 | B02.pdf | 9~10쪽 | 실물 없음 |
| T35 | C01 | C01.pdf | 11·28~41쪽 | 실물 없음 |
| T35 | A08 | A08.pdf | 6쪽 | 실물 없음 |
| T35 | A12 | A12.pdf | 17쪽 | 실물 없음 |
| T35 | S01 | 묶음 미포함 | 통합 시간표 2026.2.3 행 | 묶음 미포함 |
| T36 | B02 | B02.pdf | 18쪽 | 실물 없음 |
| T36 | C01 | C01.pdf | 8쪽 | 실물 없음 |
| T37 | B02 | B02.pdf | 4~17쪽 | 실물 없음 |
| T37 | C01 | C01.pdf | 8·17쪽 | 실물 없음 |
| T38 | C01 | C01.pdf | 8쪽 | 실물 없음 |
| T39 | C01 | C01.pdf | 43~44쪽 | 실물 없음 |
| T39 | A12 | A12.pdf | 11~12·20쪽 | 실물 없음 |
| T40 | C01 | C01.pdf | 42~44쪽 | 실물 없음 |
| T71 | S01 | 묶음 미포함 | 0절·2절 A 사건·통합 시간표 2026.4.20 행·쟁점별 대조표 | 묶음 미포함 |
| T41 | A11 | A11.pdf | 4~5쪽 | 실물 없음 |
| T42 | A06 | A06.pdf | 2~4쪽 | 실물 없음 |
| T42 | A11변경 | A11-change.pdf | 11~14쪽 | 실물 없음 |
| T42 | C01 | C01.pdf | 51~58쪽 | 실물 없음 |
| T43 | A04 | A04.pdf | 1~8쪽 | 실물 없음 |
| T43 | B03 | B03.pdf | 1~2쪽 | 실물 없음 |
| T43 | B05 | B05.pdf | 1~8쪽 | 실물 없음 |
| T44 | C01 | C01.pdf | 51~58쪽 | 실물 없음 |
| T44 | A06 | A06.pdf | 27쪽 | 실물 없음 |
| T45 | B04 | B04.pdf | 1~2쪽 | 실물 없음 |
| T45 | C01 | C01.pdf | 17쪽 | 실물 없음 |
| T46 | B06 | B06.pdf | 5~20쪽 | 실물 없음 |
| T46 | S01 | 묶음 미포함 | 통합 시간표 2026.6.29 행 | 묶음 미포함 |
| T47 | B05 | B05.pdf | 7~8쪽 | 실물 없음 |
| T47 | S01 | 묶음 미포함 | 2절 B 사건 | 묶음 미포함 |
| T48 | A06 | A06.pdf | 11쪽 | 실물 없음 |
| T48 | A11변경 | A11-change.pdf | 6쪽 | 실물 없음 |
| T48 | A12 | A12.pdf | 7~8·12~13쪽 | 실물 없음 |
| T49 | A06 | A06.pdf | 27쪽 | 실물 없음 |
| T49 | A11 | A11.pdf | 5쪽 | 실물 없음 |
| T49 | C01 | C01.pdf | 15쪽 | 실물 없음 |
| T50 | A08 | A08.pdf | 1~19쪽 | 실물 없음 |
| T51 | C01 | C01.pdf | 4~17쪽 | 실물 없음 |
| T51 | S01 | 묶음 미포함 | 2절 C 사건 | 묶음 미포함 |
| T52 | A06 | A06.pdf | 1~43쪽 특히 41·43쪽 | 실물 없음 |
| T52 | A05 | A05.pdf | 1~26쪽 | 실물 없음 |
| T53 | D01 | D01.pdf | 1~9쪽 | 실물 없음 |
| T53 | S01 | 묶음 미포함 | 2절 D 사건·쟁점별 대조표 | 묶음 미포함 |
| T54 | A07 | A07.pdf | 1~18쪽 | 실물 없음 |
| T54 | A09 | A09.pdf | 1~26쪽 | 실물 없음 |
| T55 | C01 | C01.pdf | 60쪽 | 실물 없음 |
| T55 | C03 | C03.pdf | 4~5쪽 | 실물 없음 |
| T55 | C06 | C06.pdf | 1쪽 | 실물 없음 |
| T56 | C01 | C01.pdf | 1~3쪽 | 실물 없음 |
| T56 | C03 | C03.pdf | 1쪽 | 실물 없음 |
| T56 | C05 | C05.pdf | 1쪽 | 실물 없음 |
| T57 | C02 | C02.jpg | 1쪽 | 실물 없음 |
| T58 | C03 | C03.pdf | 1~7쪽 | 실물 없음 |
| T59 | A11변경 | A11-change.pdf | 1~7쪽 | 실물 없음 |
| T59 | S01 | 묶음 미포함 | 2절 A 사건·7절 확인 사항 | 묶음 미포함 |
| T60 | B07 | B07.pdf | 4~5쪽 | 실물 없음 |
| T60 | S01 | 묶음 미포함 | 2절 B·D 사건 | 묶음 미포함 |
| T61 | A11 | A11.pdf | 1~10쪽 | 실물 없음 |
| T62 | A12 | A12.pdf | 1~2·9~18쪽 | 실물 없음 |
| T62 | S01 | 묶음 미포함 | 2절 A 사건·사건 현황표 | 묶음 미포함 |
| T63 | A12 | A12.pdf | 9~17쪽 | 실물 없음 |
| T63 | S01 | 묶음 미포함 | 2절 A 사건 | 묶음 미포함 |
| T64 | E01 | E01.pdf | 1~2쪽 | 실물 없음 |
| T64 | A12 | A12.pdf | 23~24쪽 | 실물 없음 |
| T64 | S01 | 묶음 미포함 | 0절·2절 A 사건·통합 시간표 2026.10월 행 | 묶음 미포함 |
| T65 | C04 | C04.pdf | 2~3쪽 | 실물 없음 |
| T66 | B08 | B08.pdf | 2~3쪽 | 실물 없음 |
| T66 | S01 | 묶음 미포함 | 2절 B 사건·사건 현황표·7절 확인 사항 | 묶음 미포함 |
| T67 | C04 | C04.pdf | 1~3쪽 | 실물 없음 |
| T67 | C05 | C05.pdf | 1~3쪽 | 실물 없음 |
| T68 | E01 | E01.pdf | 1~2쪽 | 실물 없음 |
| T68 | S01 | 묶음 미포함 | 0절·4절 호소문 검토·통합 시간표 2026.10.27 행 | 묶음 미포함 |
| T69 | C05 | C05.pdf | 1~3쪽 | 실물 없음 |
| T70 | C06 | C06.pdf | 1~2쪽 | 실물 없음 |
| T72 | S01 | 묶음 미포함 | 0절 한눈에 보기·5절 총회 제출용 새 탄원서 권고 | 묶음 미포함 |
