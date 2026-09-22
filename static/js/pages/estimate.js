/* 页面3：参数即时测算 —— 解析公式即时值 + 迷你仿真校验 + 四组实测并排 */
import { api, fmt, invalidate } from "../store.js";
import { GROUP_COLORS, COST_COLORS, COST_LABELS, baseOption, axisStyle, INK, INK2 } from "../palette.js";

const PRESETS = {
  "组1 逐件拉动": { strategy: "pull", ss: 0, target: 1, cap: 6, check_period: 3600, cart_cap: 6 },
  "组2 定时补满": { strategy: "timer", ss: 0, target: 6, cap: 6, check_period: 3600, cart_cap: 6 },
  "组3 固定SS=1": { strategy: "threshold", ss: 1, target: 3, cap: 3, check_period: 3600, cart_cap: 8 },
  "组4 动态SS_t": { strategy: "dynamic", ss: 1, target: 3, cap: 3, check_period: 3600, cart_cap: 8 },
};
const SLIDERS = [
  ["ss", "安全库存 SS（件）", 0, 4, 0.5],
  ["target", "补货目标 Q（件）", 1, 8, 1],
  ["cap", "线边库容量 cap（件）", 1, 8, 1],
  ["check_period", "检查/轮询周期 f（秒）", 600, 7200, 300],
  ["cart_cap", "单车容量（箱）", 2, 12, 1],
];
let charts = [];
let P = { ...PRESETS["组3 固定SS=1"], hours: 118 };
let busy = false;

export async function render(el) {
  charts.forEach((c) => c.dispose()); charts = [];
  const [cal, dash] = await Promise.all([api("/api/calibration"), api("/api/dashboard")]);
  el.innerHTML = `
  <div class="grid" style="grid-template-columns:340px 1fr">
    <div class="card">
      <h3>方案设定 <span class="hint">拖动即时测算</span></h3>
      <div class="slider-row"><label>载入实验组预设</label>
        <select id="pre" class="btn" style="flex:1">${Object.keys(PRESETS).map((k) => `<option ${k.includes("组3") ? "selected" : ""}>${k}</option>`).join("")}</select></div>
      ${SLIDERS.map(([id, lab, mn, mx, st]) => `
        <div class="slider-row"><label>${lab}</label>
          <input type="range" id="s-${id}" min="${mn}" max="${mx}" step="${st}" value="${P[id]}">
          <output id="o-${id}">${P[id]}</output></div>`).join("")}
      <button class="btn" id="whatif" style="width:100%;margin-top:8px">🧪 SS=0 压力演示（缺料成本复活）</button>
      <div class="disclaimer" style="margin-top:10px">
        ${cal.calibration ? `仿真校验器已按<b>组3实测</b>标定：库存 ${fmt.pct(cal.calibration.best.dev.wip_avg_total * 100)} / 段数 ${fmt.pct(cal.calibration.best.dev.legs * 100)} / 产出 ${fmt.pct(cal.calibration.best.dev.output * 100)}（3种子均值，${cal.calibration.pass_10pct ? "≤10% 验收通过" : "超10%呈灵敏度"}）。
        <br><span style="color:#8a8a82">${cal.calibration.note}</span>` : "仿真标定缺失：运行 python -m app.sim.calibrate"}</div>
    </div>
    <div class="grid" style="gap:14px">
      <div class="grid g-2">
        <div class="card"><h3>① 解析公式（即时 · 毫秒级）</h3><div id="ana"></div></div>
        <div class="card"><h3>② 迷你离散事件仿真（3种子均值）</h3><div id="sim"></div></div>
      </div>
      <div class="card"><h3>成本对比：当前方案 vs 四组实测 <span class="hint" id="basis-h"></span></h3>
        <div class="plot" id="ch-cost" style="height:320px"></div></div>
    </div>
  </div>`;

  el.querySelector("#pre").onchange = (e) => { P = { ...PRESETS[e.target.value], hours: 118 }; syncSliders(el); run(el); };
  SLIDERS.forEach(([id]) => {
    el.querySelector(`#s-${id}`).oninput = (e) => {
      P[id] = +e.target.value; el.querySelector(`#o-${id}`).textContent = P[id];
      const t = el.querySelector("#s-target"); if (id == "ss" && P.ss > P.target) { P.target = P.ss; t.value = P.ss; el.querySelector("#o-target").textContent = P.ss; }
      run(el);
    };
  });
  el.querySelector("#whatif").onclick = () => {
    P = { ...PRESETS["组3 固定SS=1"], ss: 0, hours: 118 }; syncSliders(el); run(el);
    el.querySelector("#whatif").textContent = "已置 SS=0 —— 点「组3」预设可复原";
  };
  curDash = dash;
  syncSliders(el);
  run(el);
}
let curDash = null;

function syncSliders(el) {
  SLIDERS.forEach(([id]) => {
    el.querySelector(`#s-${id}`).value = P[id];
    el.querySelector(`#o-${id}`).textContent = P[id];
  });
  el.querySelector("#pre").value = "组3 固定SS=1";
}

async function run(el) {
  if (busy) return; busy = true;
  try {
    const body = { ...P, strategy: P.strategy, cars: 2 };
    delete body.pre;
    const d = await fetch("/api/estimate", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }).then((r) => r.json());
    if (d.detail) { el.querySelector("#ana").innerHTML = `<span style="color:#c00">${JSON.stringify(d.detail)}</span>`; return; }
    renderCards(el, d);
    renderChart(el, d);
  } finally { busy = false; }
}

function kpiTable(rows, extra) {
  return `<table class="data"><tbody>${rows.map(([k, v, d]) =>
    `<tr><td>${k}</td><td class="hl">${v}</td><td style="color:${d && d.startsWith("+") ? "#8c1d1d" : d && d.startsWith("-") ? "#136c3a" : "#8a8a82"}">${d || ""}</td></tr>`).join("")}</tbody></table>${extra || ""}`;
}

function renderCards(el, d) {
  const a = d.analytic, s = d.sim;
  el.querySelector("#ana").innerHTML = kpiTable([
    ["平均在库（10库合计）", fmt.n(a.wip_avg_total, 2) + " 件", ""],
    ["行驶段数估算", fmt.n(a.legs_est, 0) + " 段", ""],
    ["单周期缺料概率", (a.stockout_prob_per_cycle * 100).toFixed(2) + " %", ""],
    ["总成本", fmt.n(a.cost.total, 1), d.basis.currency],
  ], `<div class="formula">库存 ${a.formulas.inventory}
段数 ${a.formulas.legs}
缺料 ${a.formulas.stockout}</div>
  <div class="hint" style="font-size:11px;color:#8a8a82">${a.note}</div>`);
  const dev = (x, base) => base ? `${((x - base) / base) * 100 >= 0 ? "+" : ""}${((x - base) / base * 100).toFixed(1)}% vs组3实测` : "";
  el.querySelector("#sim").innerHTML = kpiTable([
    ["平均在库（10库合计）", fmt.n(s.wip_avg_total, 2) + " 件", dev(s.wip_avg_total, 20.65)],
    ["行驶段数", fmt.n(s.legs, 0) + " 段", dev(s.legs, 1118)],
    ["产出", fmt.n(s.output, 0) + " 台", dev(s.output, 1291)],
    ["缺料停线", fmt.n(s.stockout_min, 1) + " 分钟", s.stockout_min > 0 ? "⚠ 需计入成本" : "0=与实验一致"],
    ["触零时长", fmt.n(s.zero_buf_min, 0) + " 库·分", "组3实测972"],
    ["总成本", fmt.n(s.cost.total, 1), d.basis.currency === "元" ? "元" : "相对值"],
  ]);
}

function renderChart(el, d) {
  if (curChart) curChart.dispose();
  const dom = el.querySelector("#ch-cost");
  curChart = echarts.init(dom);
  const groups = [...curDash.groups.map((g) => ({ name: `组${g.group}`, cost: g.cost })),
    { name: "当前方案\n(解析)", cost: d.analytic.cost }, { name: "当前方案\n(仿真)", cost: d.sim.cost }];
  const segs = ["transport", "inventory", "labor", "stockout"];
  curChart.setOption(baseOption({
    legend: { top: 0, data: segs.map((s) => COST_LABELS[s]) },
    grid: { left: 8, right: 14, top: 34, bottom: 4, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (ps) => { const g = groups[ps[0].dataIndex];
        return `<b>${g.name.replace("\n", " ")}</b><br>` + ps.map((p) =>
          `<span style="color:${p.color}">■</span> ${p.seriesName}：${fmt.n(p.value, 1)}`).join("<br>") +
          `<br>合计 <b>${fmt.n(g.cost.total, 1)}</b>`; } },
    xAxis: Object.assign(axisStyle(), { type: "category", splitLine: { show: false },
      data: groups.map((g) => g.name), axisLabel: { fontSize: 11, interval: 0 } }),
    yAxis: Object.assign(axisStyle(`成本（${d.basis.currency}）`), { type: "value" }),
    series: segs.map((s, i) => ({
      name: COST_LABELS[s], type: "bar", stack: "c", barMaxWidth: 54,
      itemStyle: { color: COST_COLORS[s], borderColor: "#fcfcfb", borderWidth: i ? 2 : 0,
        borderRadius: i == segs.length - 1 ? [4, 4, 0, 0] : 0,
        opacity: i >= 4 ? .5 : 1 },
      data: groups.map((g, gi) => ({ value: g.cost[s],
        itemStyle: gi >= 4 ? { color: COST_COLORS[s], opacity: 0.55, borderType: "dashed" } : undefined })),
    })).concat([{
      type: "scatter", symbolSize: 0, silent: true, name: "tot",
      label: { show: true, position: "top", fontWeight: 700, color: INK,
        formatter: (p) => fmt.n(groups[p.dataIndex].cost.total, 0) },
      data: groups.map((g, i) => [i, g.cost.total]),
    }]),
  }));
  charts.push(curChart);
  el.querySelector("#basis-h").textContent = `当前口径：${d.basis.label}`;
}
let curChart = null;
