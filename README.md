# 관심부동산 일일 수집 (GitHub Actions)

매일 22:50(KST)에 아실(asil.kr) 매물을 수집해 엑셀·호가이력을 갱신합니다. PC가 꺼져 있어도 돌아갑니다.

수집 조건: 매매 / 아파트 / 50세대 이상 / 호가 14억 이하 / 전용 63㎡ 이상 / 방 3개 / 3.5급지 이상

## 구성
| 경로 | 내용 |
|---|---|
| `.github/workflows/daily.yml` | 22:50 실행, 23:25 재시도(그날 결과가 이미 있으면 건너뜀), 수동 실행 |
| `collector/collect.mjs` | 수집기 (브라우저판 collect.js와 같은 조건·출력) |
| `pipeline/build_daily.py` | 엑셀·호가이력 빌드 (기존 스크립트, 열 때 재계산 설정만 추가) |
| `pipeline/diff_report.py` | 전일 대비 분석 (신규·사라짐·최저호가 하락 상위 5·급지별) |
| `data/template.xlsx` | 엑셀 양식 |
| `data/history.tsv` | 호가이력 누적본 (2026-11-18부터) |
| `data/groups/` | 날짜별 원자료 |
| `data/latest.json` | 최신 요약 |
| `data/reports/` | 날짜별 분석 보고서 |

엑셀 파일은 매일 **Releases**(`d-YYYY-MM-DD`)에 `관심부동산_YYYYMMDD.xlsx`로 올라갑니다.

## 설치 (한 번만)
1. GitHub에서 **비공개(Private)** 저장소를 새로 만듭니다. 예: `asil-daily`
2. 이 폴더 내용을 전부 올립니다. 웹에서 올릴 때는 `.github` 폴더가 빠지지 않게 하세요.
   - Mac Finder에서는 `Cmd + Shift + .` 을 눌러야 숨김 폴더가 보입니다.
3. 저장소 **Settings → Actions → General → Workflow permissions** 에서 **Read and write permissions** 를 선택하고 저장합니다.
4. **Actions** 탭 → `관심부동산 일일 수집` → **Run workflow** 를 누릅니다. 시험 실행입니다.
5. 알림 받기: 저장소 우측 상단 **Watch → Custom → Releases** 를 체크합니다. GitHub 모바일 앱이 있으면 푸시 알림도 받을 수 있습니다.
   - 실행이 실패하면 GitHub이 계정 이메일로 실패 알림을 보냅니다.

## 시험 실행 결과 확인
- 성공: 실행 화면 Summary에 전일 대비 보고서가 보이고, Releases에 엑셀이 올라옵니다.
- `동 목록 0건` 또는 `HTTP 403`: 아실이 해외 서버 접속을 막는 경우입니다. 서울 리전 서버(B안)로 옮겨야 합니다.
- `오류율 초과`: 일시적 지연일 수 있으니 한 번 더 실행해 보고, 반복되면 `ASIL_CONCURRENCY` 를 3으로 낮춥니다(workflow의 수집 단계에 `env:` 로 지정).

## 수동 실행 옵션
- `date`: 특정 기준일로 기록합니다. 비워 두면 오늘(KST)이고, 06시 전에 실행하면 전날로 기록합니다.
- `force`: 이미 있는 기준일을 다시 수집해 덮어씁니다.
