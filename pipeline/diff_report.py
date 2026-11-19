# 전일 대비 분석 → 마크다운 보고서
# 사용법: python3 diff_report.py HISTORY.tsv DATE OUT.md
#  (a) 신규 단지·평형  (b) 사라진 단지·평형  (c) 최저호가 하락 상위 5  (d) 급지별 건수
import sys, csv, collections

HIST, DATE, OUT = sys.argv[1:4]
by = collections.defaultdict(dict)  # date -> 단지키 -> row
with open(HIST, encoding='utf-8') as f:
    r = csv.reader(f, delimiter='\t'); next(r)
    for row in r:
        if row:
            by[row[0]][row[5]] = row
if DATE not in by:
    raise SystemExit(f'{DATE} 데이터가 이력에 없음')
prev = max((d for d in by if d < DATE), default=None)
today = by[DATE]
L = [f'## 관심부동산 {DATE}', '']
tiers = collections.Counter(row[4] for row in today.values())
tier_txt = ' · '.join(f'{k}급지 {v}' for k, v in sorted(tiers.items(), key=lambda x: float(x[0])))
listings = sum(int(row[9]) for row in today.values())
L.append(f'- 단지·평형 **{len(today)}**개, 매물 {listings}건 ({tier_txt})')
if prev is None:
    L.append('- 비교할 직전 기준일 없음 (첫 수집)')
else:
    old = by[prev]
    new = [k for k in today if k not in old]
    gone = [k for k in old if k not in today]
    drops = []
    for k in today.keys() & old.keys():
        a, b = float(old[k][10]), float(today[k][10])
        if b < a:
            drops.append((b - a, k, a, b))
    drops.sort()
    L.append(f'- 직전 기준일 {prev} 대비: 신규 **{len(new)}**개 · 사라짐 **{len(gone)}**개 · 최저호가 하락 {len(drops)}개')
    if drops:
        L += ['', '**최저호가 하락 상위 5**', '', '| 단지 | 전용㎡ | 전일 → 오늘(억) |', '|---|---:|---|']
        for diff, k, a, b in drops[:5]:
            row = today[k]
            L.append(f'| {row[2]} {row[3]} {row[6]} | {float(row[7]):.1f} | {a:g} → {b:g} ({diff:+.2f}) |')
    if new:
        L += ['', '**신규 단지·평형 (최저호가 순 최대 10)**', '']
        for k in sorted(new, key=lambda k: float(today[k][10]))[:10]:
            row = today[k]
            L.append(f'- {row[4]}급지 {row[2]} {row[3]} {row[6]} {float(row[7]):.1f}㎡ — {row[10]}억')
text = '\n'.join(L) + '\n'
open(OUT, 'w', encoding='utf-8').write(text)
print(text)
