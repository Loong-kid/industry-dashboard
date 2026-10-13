/* Navigation groups are menus, never new aggregate price indexes. */
export const GROUPS = [
  ["aggregate", "산업 종합", "제조업·광업·유통·운송의 공식 종합지수"],
  ["energy", "에너지·광업·유틸리티", "석유·가스, 광업, 정유, 전력·가스 공급"],
  ["chemical", "화학·플라스틱·고무", "화학제품, 의약품, 플라스틱·고무"],
  ["materials", "금속·비금속소재·건설", "철강·비철, 금속가공, 시멘트·유리, 건설"],
  ["equipment", "기계·전기·전자", "산업기계, 반도체·전자제품, 전기장비·가전"],
  ["transport", "운송장비", "자동차, 항공기, 선박 및 관련 장비"],
  ["food", "식품·음료", "식품, 음료, 담배"],
  ["consumer", "소비재·생활용품", "섬유, 의류, 가죽, 가구, 기타 제조업"],
  ["wood", "목재·종이·인쇄·임업", "벌목, 목재, 종이, 인쇄"],
  ["logistics", "유통·물류", "도매·소매, 운송, 창고"],
  ["finance", "정보·금융·부동산", "정보산업, 금융·보험, 부동산"],
  ["services", "의료·전문·생활서비스", "의료, 전문서비스, 숙박·여가 등"],
].map(([id, name, description]) => ({id, name, description}));
export const THEMES = [
  {id: "semiconductor", name: "반도체·전자부품", description: "반도체 소자·집적회로, 제조장비, PCB·전자부품을 함께 확인합니다.", prefixes: ["3344", "333242"]},
  {id: "power", name: "ESS·전력설비", description: "전지, 변압기·스위치기어, 전선, 발전·배전. 전지 지수의 범위는 ESS용 리튬이온 판매가격과 다릅니다.", prefixes: ["335911", "335912", "335311", "335312", "335313", "335314", "33592", "333611", "22111", "221122", "331420"]},
  {id: "shipping", name: "조선·해운", description: "선박 건조·수리, 수운·항만서비스와 철강·연료 가격을 비교합니다.", prefixes: ["336611", "336612", "483", "4883", "331110", "324110"]},
  {id: "copper", name: "구리·금속", description: "광업, 비철 제련·가공, 구리 압연·인발, 전선. 과거 지표는 별도로 표시합니다.", prefixes: ["212230", "331410", "331420", "33592"]},
  {id: "datacenter", name: "건설·데이터센터", description: "건설, 시멘트·유리, 전기설비, 냉방·컴퓨터 장비, 데이터 처리 서비스를 확인합니다.", prefixes: ["236", "3272", "3273", "335311", "335313", "333415", "334111", "334112", "334118", "5182"]},
];
const KOREAN = {"211":"석유·가스 채굴", "212":"광업", "213":"광업 지원", "221":"전력·가스·수도", "311":"식품", "312":"음료·담배", "313":"섬유", "314":"섬유제품", "315":"의류", "316":"가죽·신발", "321":"목재", "322":"종이", "323":"인쇄", "324":"석유·석탄제품", "325":"화학", "326":"플라스틱·고무", "327":"비금속광물 제품", "331":"1차 금속", "332":"금속가공", "333":"기계", "334":"컴퓨터·전자제품", "335":"전기장비·가전", "336":"운송장비", "337":"가구", "339":"기타 제조업", "441":"자동차·부품 유통", "444":"건축자재 유통", "445":"식품·음료 유통", "446":"건강·개인용품 유통", "448":"의류 유통", "449":"가구·전자제품 유통", "452":"종합상품 유통", "457":"주유·연료 유통", "481":"항공운송", "482":"철도운송", "483":"수운", "484":"트럭운송", "486":"파이프라인 운송", "488":"운송 지원", "491":"우편", "492":"택배·배송", "493":"창고", "423":"내구재 도매", "424":"비내구재 도매", "513":"출판", "515":"방송", "517":"통신", "523":"증권·상품계약", "524":"보험", "622":"병원", "721":"숙박"};
const SPECIAL = {"OMFG":"제조업 종합", "AMUM":"광업·유틸리티·제조업 종합", "OMIN":"광업 종합", "ARETTR":"소매 종합", "ATRADE":"도소매 종합", "AWHLTR":"도매 종합", "ATRANS":"운송 종합", "ATRNWR":"운송·창고 종합", "ADLVWR":"배송·창고 종합", "AINFO":"정보산업 종합", "ASHC":"주요 의료산업 종합"};
const FOCUS = {"334413":"반도체 소자", "333242":"반도체 제조장비", "335911":"전지 제조", "335311":"변압기", "335313":"스위치기어", "336611":"선박 건조·수리", "331110":"철강 제조", "331420":"구리 압연·인발", "333415":"냉방·난방·냉동 장비"};
const clean = s => (s.title || s.id).replace(/^(Producer Price Index by Industry: ?|PPI by Industry: )/, "");
export function parseIndustry(id) {
  const body = id.replace(/^PCU/, "");
  for (let width = 7; width >= 3; width--) {
    const code = body.slice(0, width);
    if (body.length >= width * 2 && body.slice(width, width * 2) === code) return {code, suffix: body.slice(width * 2)};
  }
  return {code: body, suffix: "", unknown: true};
}
export function groupFor(s, code = parseIndustry(s.id).code) {
  if (!/^\d/.test(code)) return "aggregate";
  const sectors = s.category_ids || [], manufacturing = sectors.includes(33597), prefix = code.slice(0, 3);
  if (sectors.includes(33596) || sectors.includes(33602) || manufacturing && prefix === "324") return "energy";
  if (manufacturing && ["325", "326"].includes(prefix)) return "chemical";
  if (sectors.includes(33589) || manufacturing && ["327", "331", "332"].includes(prefix)) return "materials";
  if (manufacturing && ["333", "334", "335"].includes(prefix)) return "equipment";
  if (manufacturing && prefix === "336") return "transport";
  if (manufacturing && ["311", "312"].includes(prefix)) return "food";
  if (manufacturing && ["313", "314", "315", "316", "337", "339"].includes(prefix)) return "consumer";
  if (sectors.includes(33585) || manufacturing && ["321", "322", "323"].includes(prefix)) return "wood";
  if (sectors.some(id => [33600, 33601, 33603].includes(id))) return "logistics";
  if (sectors.some(id => [33590, 33592, 33598].includes(id))) return "finance";
  return "services";
}
export function classify(s) {
  const {code, suffix, unknown} = parseIndustry(s.id);
  const text = clean(s);
  const kind = !suffix ? "industry" : suffix === "P" ? "primary"
    : suffix === "S" || /: Secondary Products/i.test(text) ? "secondary"
    : ["M", "MM", "SM"].includes(suffix) || /: Miscellaneous Receipts/i.test(text) ? "misc" : "product";
  return {...s, code, suffix, unknown, kind, group: groupFor(s, code),
    label: kind === "industry" ? KOREAN[code] || SPECIAL[code] || FOCUS[code] || text : text,
    themes: THEMES.filter(t => t.prefixes.some(p => code.startsWith(p))).map(t => t.id)};
}
export const KIND_NAMES = {industry: "산업 전체", primary: "주력제품", product: "세부 품목", secondary: "부차적 제품", misc: "기타 수입"};
export function themeRole(s) {
  if (/^(333|33531|33411)/.test(s.code)) return "설비가격 참고";
  if (/^(212|331|324|327)/.test(s.code)) return "재료·연료가격 참고";
  if (/^(221|483|488|518)/.test(s.code)) return "서비스·공급가격 참고";
  return "제품 판매가격";
}
export function lifecycle(lastDate, at) {
  if (lastDate === at) return "current";
  if (!lastDate) return "historical";
  const months = (Number(at.slice(0, 4)) - Number(lastDate.slice(0, 4))) * 12 + Number(at.slice(5, 7)) - Number(lastDate.slice(5, 7));
  return months > 0 && months <= 3 ? "lagged" : "historical";
}
export function representatives(records, latestDates, at) {
  const current = records.filter(s => s.kind === "industry" && latestDates[s.id] === at);
  const chosen = current.filter(s => /^\d{3}$/.test(s.code) || !/^\d/.test(s.code) || Object.hasOwn(FOCUS, s.code));
  // Selected service/construction branches lack a live 3-digit aggregate.
  const branches = ["236", "522", "531", "541", "621"];
  for (const prefix of branches) {
    if (!chosen.some(s => s.code.startsWith(prefix))) {
      const fallback = current.filter(s => s.code.startsWith(prefix)).sort((a, b) => a.code.length - b.code.length || a.id.localeCompare(b.id))[0];
      if (fallback) chosen.push(fallback);
    }
  }
  return chosen.sort((a, b) => GROUPS.findIndex(g => g.id === a.group) - GROUPS.findIndex(g => g.id === b.group) || a.code.localeCompare(b.code));
}
export function buildTree(records, metadata = records) {
  const nodes = new Map(), industryMeta = new Map(metadata.filter(s => s.kind === "industry").map(s => [s.code, s]));
  for (const s of records) {
    if (!nodes.has(s.code)) nodes.set(s.code, {code: s.code, group: s.group, industry: industryMeta.get(s.code), children: [], series: []});
    nodes.get(s.code).series.push(s);
    let parent = s.code;
    while (parent.length > 3 && /^\d/.test(parent)) {
      parent = parent.slice(0, -1);
      if (industryMeta.has(parent) && !nodes.has(parent)) {
        const meta = industryMeta.get(parent); nodes.set(parent, {code: parent, group: meta.group, industry: meta, children: [], series: []});
      }
    }
  }
  const roots = [];
  for (const node of nodes.values()) {
    let parent = node.code.slice(0, -1);
    while (parent.length >= 3 && (!nodes.has(parent) || nodes.get(parent).group !== node.group)) parent = parent.slice(0, -1);
    if (parent.length >= 3) nodes.get(parent).children.push(node); else roots.push(node);
  }
  const count = node => { node.count = node.series.length + node.children.reduce((sum, child) => sum + count(child), 0); node.children.sort((a, b) => a.code.localeCompare(b.code)); return node.count; };
  roots.forEach(count); return {nodes, roots: roots.sort((a, b) => a.code.localeCompare(b.code))};
}
export function rankIndustries(rows, metric, limit = 12) {
  const unique = new Set();
  return rows.filter(r => r.s.kind === "industry" && /^\d/.test(r.s.code) && Number.isFinite(r[metric]))
    .sort((a, b) => b[metric] - a[metric]).filter(r => {
      // Show one industry per 3-digit branch to avoid nested parent/child repeats.
      const key = /^\d/.test(r.s.code) ? r.s.code.slice(0, 3) : r.s.code;
      if (unique.has(key)) return false; unique.add(key); return true;
    }).slice(0, limit);
}
