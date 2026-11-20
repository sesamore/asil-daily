# 관심부동산 일일 빌드
# (GitHub Actions판: 저장 시 fullCalcOnLoad 지정)
# 사용법: python3 build_daily.py TEMPLATE.xlsx GROUPS.txt HISTORY_IN.tsv YYYY-MM-DD "수집시각/출처" OUT.xlsx HISTORY_OUT.tsv
#  - GROUPS.txt : collect.js의 __show 출력(파이프 구분 19열, 1행=단지×전용 그룹)
#  - HISTORY.tsv: 호가이력 누적본(헤더 포함, 탭 구분). 같은 기준일 행은 교체
import sys, re, copy, csv, datetime, glob, os
import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

TPL, RAW, HIN, DATE, LABEL, OUT, HOUT = sys.argv[1:8]
BASE_DATE = datetime.date.fromisoformat(DATE)
HH_MIN = 50

cols = ['gu','dn','seq','apt','hh','mv','ex','sp','exp','cnt','minp','avg','maxp','bdong','flr','tflr','desc','date','rc']
rows = []
for line in open(RAW, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    p = line.split('|')
    if len(p) != 19:
        raise SystemExit(f'열 수 오류({len(p)}): {line}')
    d = dict(zip(cols, p))
    d['hh'] = int(str(d['hh']).replace(',', '') or 0)
    d['mv'] = int(d['mv']); d['ex'] = float(d['ex']); d['sp'] = float(d['sp'])
    d['exp'] = int(d['exp']); d['cnt'] = int(d['cnt'])
    for k in ('minp', 'avg', 'maxp'):
        d[k] = int(float(d[k]))
    d['apt'] = d['apt'].strip()
    rows.append(d)
print('raw groups', len(rows))

def tier(gu, dn):
    if gu in ('강남구', '서초구'): return 1, False
    if gu == '송파구': return (3.5, False) if dn in ('거여동', '마천동') else (1.5, False)
    if gu == '용산구': return 1.5, False
    if gu == '동작구': return (1.5, False) if dn == '흑석동' else (3, False)
    if gu == '영등포구':
        if dn == '여의도동': return 1.5, False
        if dn.startswith('신길') or dn.startswith('당산'): return 3, False
        return 3, True
    if gu == '마포구': return 2, False
    if gu == '성동구': return (2.5, True) if dn in ('하왕십리동', '상왕십리동') else (2, False)
    if gu == '양천구': return (2, False) if dn.startswith('목동') else (2.5, True)
    if gu == '종로구': return 2, False
    if gu == '광진구': return (2, False) if dn == '광장동' else (2.5, True)
    if gu == '서대문구': return (2.5, False) if dn == '북아현동' else (3.5, False)
    if gu == '강동구':
        if dn in ('고덕동', '상일동'): return 3, False
        if dn == '강일동': return 3.5, True
        return 3, True
    if gu == '중구': return (3, False) if dn.startswith('만리') else (3, True)
    if gu in ('강서구', '성북구'): return 3, False
    if gu == '동대문구': return (3, False) if dn == '전농동' else (3.5, False)
    if gu in ('은평구', '구로구'): return 3.5, False
    raise ValueError(gu + dn)

kept, dropped = [], []
for d in rows:
    d['tier'], d['tier_est'] = tier(d['gu'], d['dn'])
    reason = None
    if d['hh'] < HH_MIN: reason = f'{HH_MIN}세대 미만'
    elif d['exp'] == 4: reason = '매물설명상 방4'
    elif d['exp'] == 2: reason = '매물설명상 방2'
    elif d['exp'] == 0 and d['ex'] >= 100: reason = '전용 100㎡ 이상(방4 추정)'
    elif re.search(r'오피스텔|상가 지하', d['desc']): reason = '오피스텔/상가 매물'
    if reason:
        d['reason'] = reason; dropped.append(d)
    else:
        kept.append(d)
kept.sort(key=lambda d: (d['tier'], d['gu'], d['dn'], d['apt'], d['ex']))
dropped.sort(key=lambda d: (d['tier'], d['gu'], d['apt'], d['ex']))
print('kept', len(kept), 'dropped', len(dropped), 'listings', sum(d['cnt'] for d in kept))

def key(d): return f"{d['seq']}_{round(d['ex'])}"
def baths(desc):
    m = re.search(r'(?:화장실|욕실|화)\s*(\d)', desc)
    return int(m.group(1)) if m else None
def floor_txt(d):
    dong = d['bdong']
    dong = dong + '동' if dong and not dong.endswith('동') else dong
    return f"{dong} {d['flr']}층/{d['tflr']}층".strip()

# ---------- 호가이력 누적 ----------
HH = ['기준일', '수집시각/출처', '구', '동', '급지', '단지키', '아파트명', '전용㎡', '공급평형', '매물수(건)', '최저호가', '평균호가', '최고호가', '최저호가 동/층', '최저호가매물 특징', '최저호가 등록일', '세대수']
# 단지키 → 세대수 (예전 이력 행에 세대수가 없으면 groups 원본 파일로 채움. 기존 열 위치는 그대로 두고 맨 끝에 추가)
hh_map = {}
for gf in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(RAW)), 'groups_*.txt'))):
    for line in open(gf, encoding='utf-8'):
        p = line.rstrip('\n').split('|')
        if len(p) != 19: continue
        try: hh_map[f"{p[2]}_{round(float(p[6]))}"] = int(p[4].replace(',', '') or 0)
        except ValueError: pass
for d in rows:
    hh_map[key(d)] = d['hh']
hist = []
with open(HIN, encoding='utf-8') as f:
    r = csv.reader(f, delimiter='\t')
    next(r)
    for row in r:
        if row and row[0] != DATE:
            row = (row + [''] * len(HH))[:len(HH)]
            if row[16] == '' and row[5] in hh_map:
                row[16] = str(hh_map[row[5]])
            hist.append(row)
prev_dates = sorted({row[0] for row in hist})
prev_keys = {row[5] for row in hist if prev_dates and row[0] == prev_dates[-1]}
for d in kept:
    hist.append([DATE, LABEL, d['gu'], d['dn'], str(d['tier']), key(d), d['apt'], f"{d['ex']:.2f}", str(round(d['sp'] / 3.3058)),
                 str(d['cnt']), f"{d['minp']/10000:g}", f"{d['avg']/10000:.2f}", f"{d['maxp']/10000:g}", floor_txt(d), d['desc'], d['date'], str(d['hh'])])
hist.sort(key=lambda x: x[0])
with open(HOUT, 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f, delimiter='\t', lineterminator='\n')
    w.writerow(HH); w.writerows(hist)

# ---------- 워크북 ----------
wb = openpyxl.load_workbook(TPL)
ws = wb['관심부동산']
tmpl = {}
for c in range(1, 34):
    cell = ws.cell(2, c)
    tmpl[c] = (copy.copy(cell.font), copy.copy(cell.border), copy.copy(cell.alignment), cell.number_format)
hdr_style = copy.copy(ws['E1']._style)
for m in list(ws.merged_cells.ranges):
    ws.unmerge_cells(str(m))
ws.delete_rows(2, ws.max_row)

gray = 'FF7F7F7F'
for i, d in enumerate(kept, start=2):
    room_est = d['exp'] != 3
    flags = []
    if prev_keys and key(d) not in prev_keys: flags.append('신규')
    if room_est: flags.append('방수 추정')
    if d['hh'] < 100: flags.append(f"{d['hh']}세대")
    desc = f"{floor_txt(d)} | {d['desc']} (등록 {d['date'][5:]})" if d['desc'] else f"{floor_txt(d)} (등록 {d['date'][5:]})"
    vals = {
        1: ', '.join(flags) or None, 2: d['gu'], 3: d['dn'], 4: d['tier'], 5: d['apt'],
        6: d['mv'], 7: 2027 - d['mv'], 8: d['hh'], 11: round(d['ex'], 2), 12: round(d['sp'] / 3.3058),
        13: 3, 14: baths(d['desc']), 16: d['minp'] / 10000, 17: desc,
        19: f'=IF(OR(O{i}="",R{i}=""),"",O{i}-R{i})',
        22: f'=IF(OR(O{i}="",U{i}=""),"",(O{i}-U{i})/U{i})',
        28: d['cnt'], 29: round(d['avg'] / 10000, 2),
        30: f'=IF(COUNTIFS(호가이력!$F:$F,$AG{i},호가이력!$A:$A,MAX(호가이력!$A:$A)-1)=0,"",_xlfn.MINIFS(호가이력!$K:$K,호가이력!$F:$F,$AG{i},호가이력!$A:$A,MAX(호가이력!$A:$A)-1))',
        31: f'=IF(AD{i}="","",P{i}-AD{i})',
        32: f'=_xlfn.MINIFS(호가이력!$K:$K,호가이력!$F:$F,$AG{i},호가이력!$A:$A,">="&(MAX(호가이력!$A:$A)-6))',
        33: key(d),
    }
    for c in range(1, 34):
        cell = ws.cell(i, c)
        f, b, a, nf = tmpl[c]
        cell.font = copy.copy(f); cell.border = copy.copy(b); cell.alignment = copy.copy(a); cell.number_format = nf
        if vals.get(c) is not None:
            cell.value = vals[c]
    ws.cell(i, 4).alignment = Alignment(horizontal='center')
    ws.cell(i, 16).font = Font(name=tmpl[16][0].name, size=tmpl[16][0].sz, bold=True)
    ws.cell(i, 22).number_format = '0.0%'
    ws.cell(i, 29).number_format = '0.00'
    for c in (30, 31, 32):
        ws.cell(i, c).number_format = '0.00;[Red]-0.00'
    if d['tier_est']:
        ws.cell(i, 4).font = Font(italic=True, color=gray)
        ws.cell(i, 4).comment = Comment('[추정] 이미지 미기재 동 — 급지기준 시트 참고', '급지기준')
    if room_est:
        ws.cell(i, 13).font = Font(italic=True, color=gray)
ws.auto_filter.ref = f'A1:AG{len(kept) + 1}'

thin = Side(style='thin', color='FFBFBFBF')
bd = Border(left=thin, right=thin, top=thin, bottom=thin)
hs = wb['호가이력']
hs.delete_rows(2, hs.max_row)
num_cols = {5: float, 8: float, 9: int, 10: int, 11: float, 12: float, 13: float, 17: int}
for c in range(1, len(HH) + 1):  # 템플릿에 없는 새 머리글(세대수)은 앞 열 서식을 복사
    if hs.cell(1, c).value is None:
        hs.cell(1, c, HH[c - 1])._style = copy.copy(hs.cell(1, c - 1)._style)
        hs.column_dimensions[get_column_letter(c)].width = 9
for i, row in enumerate(hist, start=2):
    for c, val in enumerate(row, 1):
        if c == 1:
            val = datetime.date.fromisoformat(val)
        elif c in num_cols and val != '':
            val = num_cols[c](val)
        cell = hs.cell(i, c, val)
        cell.font = Font(name='맑은 고딕', size=10); cell.border = bd
    hs.cell(i, 1).number_format = 'yyyy-mm-dd'
    for c in (11, 12, 13):
        hs.cell(i, c).number_format = '0.00'
    hs.cell(i, 17).number_format = '#,##0'
hs.auto_filter.ref = f'A1:{get_column_letter(len(HH))}{len(hist) + 1}'

xs = wb['제외매물']
xs.delete_rows(2, xs.max_row)
for i, d in enumerate(dropped, start=2):
    v = [d['reason'], d['gu'], d['dn'], d['tier'], d['apt'], d['hh'], d['mv'], round(d['ex'], 2), d['minp'] / 10000, d['cnt'], d['desc']]
    for c, val in enumerate(v, 1):
        cell = xs.cell(i, c, val); cell.font = Font(name='맑은 고딕', size=10); cell.border = bd
    xs.cell(i, 9).number_format = '0.00'

# 수식은 파일을 열 때 엑셀이 다시 계산(LibreOffice 없이 실행 환경에서 빌드)
from openpyxl.workbook.properties import CalcProperties
wb.calculation = CalcProperties(fullCalcOnLoad=True)
wb.save(OUT)

# ---------- 요약 (latest.json용) ----------
import json, collections
summary = {
    'date': DATE, 'label': LABEL, 'groups': len(kept), 'listings': sum(d['cnt'] for d in kept), 'dropped': len(dropped),
    'new': sum(1 for d in kept if prev_keys and key(d) not in prev_keys),
    'by_tier': {str(k): v for k, v in sorted(collections.Counter(d['tier'] for d in kept).items())},
    'top': [{'tier': d['tier'], 'gu': d['gu'], 'dn': d['dn'], 'apt': d['apt'], 'ex': round(d['ex'], 1), 'hh': d['hh'], 'mv': d['mv'], 'minp': d['minp'] / 10000, 'cnt': d['cnt'], 'desc': floor_txt(d) + ' · ' + d['desc']}
            for d in sorted(kept, key=lambda d: (d['tier'], d['minp']))],
}
json.dump(summary, open(OUT + '.summary.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(json.dumps({k: summary[k] for k in ('date', 'groups', 'listings', 'dropped', 'new', 'by_tier')}, ensure_ascii=False))
