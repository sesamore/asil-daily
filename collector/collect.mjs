// 관심부동산 매물 수집기 (아실 asil.kr) — Node 22 버전
// 브라우저용 pipeline/collect.js 와 같은 조건·같은 출력 형식(파이프 구분 19열)을 유지한다.
// 사용법: node collector/collect.mjs OUT.txt
// 환경변수: ASIL_CONCURRENCY(기본 6), ASIL_MAX_ERR_RATE(기본 0.05)
import { writeFileSync } from 'node:fs';

const OUT = process.argv[2];
if (!OUT) { console.error('사용법: node collect.mjs OUT.txt'); process.exit(2); }

const HH_MIN = 50;            // 세대수 하한
const PRICE_MAX = 140000;     // 만원 (14억)
const EX_MIN = 63;            // 전용 ㎡
const CONC = parseInt(process.env.ASIL_CONCURRENCY || '6');
const MAX_ERR_RATE = parseFloat(process.env.ASIL_MAX_ERR_RATE || '0.05');
const GU = {'11680':'강남구','11650':'서초구','11710':'송파구','11170':'용산구','11590':'동작구','11560':'영등포구','11440':'마포구','11200':'성동구','11470':'양천구','11110':'종로구','11215':'광진구','11410':'서대문구','11740':'강동구','11140':'중구','11500':'강서구','11290':'성북구','11230':'동대문구','11380':'은평구','11530':'구로구'};
const PART = {'동작구':['흑석동','상도동','사당동'],'영등포구':['여의도동','신길동','당산동','양평동'],'양천구':['목동','신정동'],'종로구':['평동'],'광진구':['광장동','자양동','화양동'],'서대문구':['북아현동','남가좌동','북가좌동'],'강동구':['고덕동','상일동','둔촌동','성내동','강일동'],'중구':['만리동','신당동'],'강서구':['마곡동'],'성북구':['길음동'],'은평구':['수색동','증산동'],'구로구':['신도림동']};

const BASE = 'https://asil.kr';
const HDR = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
  'Accept-Language': 'ko-KR,ko;q=0.9',
  'Referer': 'https://asil.kr/asil/index.jsp',
  'Origin': 'https://asil.kr',
};
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// 재시도(최대 3회, 지수 대기)와 20초 타임아웃
async function req(url, opt = {}) {
  let last;
  for (let t = 0; t < 3; t++) {
    try {
      const r = await fetch(url, { ...opt, headers: { ...HDR, ...(opt.headers || {}) }, signal: AbortSignal.timeout(20000) });
      if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
      return r;
    } catch (e) { last = e; await sleep(1000 * 2 ** t); }
  }
  throw last;
}

const dongs = async (gu) => {
  const r = await req(BASE + '/app/area_list.jsp', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'os=pc&area=' + gu });
  const b = await r.arrayBuffer(); let t = new TextDecoder('utf-8').decode(b);
  if (t.includes('�')) t = new TextDecoder('euc-kr').decode(b);
  return [...t.matchAll(/setArea\('(\d{10})',\s*'([^']*)'\)/g)].map(m => [m[1], m[2]]);
};
const sale = async (bld, page) => {
  const r = await req('https://realty.asil.kr/api_asil/data_sale_of_apt_nomal.aspx', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ asil_bldcode: bld, focus_bldcode: bld, oidx: 2, oby: 'up', total: 20, dealmode: 'A01', dong: '', user: '', ptp_no: '', asil_preminum: '', asil_focus: '', last_mm_num: page * 20, pre_mm_uid: '', focus_mm_uid: '' }) });
  return r.json();
};
const rooms = (d) => { d = d || ''; if (/방\s*4|4\s*룸|포룸/.test(d)) return 4; if (/방\s*3|3\s*룸|쓰리룸/.test(d)) return 3; if (/방\s*2|2\s*룸|투룸/.test(d)) return 2; return 0; };

const st = { dongs: 0, apts: 0, done: 0, err: [], list: [] };
const t0 = Date.now();

// 1) 동 목록
const ds = [];
for (const [code, gu] of Object.entries(GU)) {
  for (const [dc, dn] of await dongs(code)) { const p = PART[gu]; if (!p || p.some(x => dn.startsWith(x))) ds.push({ gu, dc, dn }); }
}
st.dongs = ds.length;
console.log('동', ds.length);
if (!ds.length) { console.error('동 목록 0건 — 접속 차단 또는 사이트 구조 변경'); process.exit(1); }

// 2) 단지 목록
const apts = [];
for (let i = 0; i < ds.length; i += CONC) await Promise.all(ds.slice(i, i + CONC).map(async d => {
  try { const j = await (await req(BASE + '/app/data/data_apt_list.jsp?dong=' + d.dc + '&building=&household=0&order=0&order_type=0')).json();
    for (const x of j) { const hh = parseInt(String(x.household).replace(/,/g, '')) || 0;
      if (x.building === 'apt' && x.offer && hh >= HH_MIN) apts.push({ ...d, seq: x.seq, name: x.name.trim(), hh, mv: x.movein }); }
  } catch (e) { st.err.push('d' + d.dc + ' ' + e.message); }
}));
st.apts = apts.length;
console.log('단지', apts.length, '동 오류', st.err.length);

// 3) 매물
for (let i = 0; i < apts.length; i += CONC) await Promise.all(apts.slice(i, i + CONC).map(async a => {
  try { let page = 0, more = true;
    while (more && page < 30) { const j = await sale(a.seq, page);
      for (const s of (j.list_result || [])) { const amt = parseInt((s.DEAL_AMT || '0').replace(/,/g, '')); const ex = parseFloat(s.EXCLS_SPC || '0');
        if (amt > 0 && amt <= PRICE_MAX && ex >= EX_MIN) st.list.push({ a, amt, ex, sp: parseFloat(s.SPLY_SPC || '0'), bdong: s.BDONG_NM, flr: s.CORES_FLR_CNT_NM, tflr: s.TOT_FLR_CNT, desc: (s.FETR_DESC || '').replace(/\s+/g, ' ').replace(/\|/g, '/'), date: s.SVC_DATE_STRT }); }
      more = !!j.next_page; page++; }
  } catch (e) { st.err.push('s' + a.seq + ' ' + e.message); }
  st.done++;
  if (st.done % 200 === 0) console.log('진행', st.done, '/', apts.length);
}));

// 4) 단지×전용 그룹화, 동·층·가격 동일 매물 중복 제거 (브라우저판과 동일)
const G = {};
for (const x of st.list) { const k = x.a.seq + '_' + Math.round(x.ex);
  const g = G[k] || (G[k] = { a: x.a, ex: x.ex, sp: x.sp, units: {}, r: { 2: 0, 3: 0, 4: 0 } });
  const r = rooms(x.desc); if (r) g.r[r]++;
  const uk = x.bdong + '|' + x.flr + '|' + x.amt; (g.units[uk] = g.units[uk] || []).push(x); }
const groups = Object.values(G).map(g => { const us = Object.values(g.units); const ps = us.map(u => u[0].amt).sort((p, q) => p - q); const minp = ps[0];
  const m = us.filter(u => u[0].amt === minp).flat().sort((p, q) => q.desc.length - p.desc.length)[0];
  const exp = [2, 3, 4].filter(k => g.r[k] > 0).sort((p, q) => g.r[q] - g.r[p])[0] || 0;
  return [g.a.gu, g.a.dn, g.a.seq, g.a.name, g.a.hh, g.a.mv, g.ex, g.sp, exp, us.length, minp, Math.round(ps.reduce((p, q) => p + q, 0) / ps.length), ps[ps.length - 1], m.bdong, m.flr, m.tflr, m.desc.slice(0, 45), m.date, g.r[2] + '/' + g.r[3] + '/' + g.r[4]]; });

const errRate = st.err.length / Math.max(1, ds.length + apts.length);
console.log(JSON.stringify({ dongs: st.dongs, apts: st.apts, listings: st.list.length, groups: groups.length, err: st.err.length, errRate: +errRate.toFixed(3), sec: Math.round((Date.now() - t0) / 1000) }));
if (st.err.length) console.log('오류 예시:', st.err.slice(0, 5).join(' / '));
if (!groups.length) { console.error('수집 결과 0건'); process.exit(1); }
if (errRate > MAX_ERR_RATE) { console.error('오류율 초과', errRate); process.exit(1); }
writeFileSync(OUT, groups.map(r => r.join('|')).join('\n') + '\n', 'utf-8');
console.log('저장', OUT, groups.length, '행');
