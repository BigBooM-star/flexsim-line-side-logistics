/* 页面1：四组对比看板 */
import { api, fmt, basisChip } from "../store.js";
import { GROUP_COLORS, COST_COLORS, COST_LABELS, baseOption, axisStyle, INK, INK2, MUTED, LINE } from "../palette.js";

const charts = [];

export async function render(el) {
  charts.forEach((c) => c.dispose());
  charts.length = 0;
  const d = await api("/api/dashboard");
  if (!d.ready) { el.innerHTML = `<div class="card">${d.hint}</div>`; return; }
  basisChip(d.basis);
  const cur = d.basis.currency;

  el.innerHTML = `
  <div class="toolbar">
    <span class="hint" style="color:#8a8a82;font-size:12px">
      统计窗 2h–120h · 四组对照实验 · 成本随口径实时联动</span>
    <a class="btn" style="margin-left:auto;text-decoration:none" href="/api/export/kpi.csv"
       download="kpi_actuals.csv">⬇ 导出KPI+成本 CSV</a>
  </div>

  <div class="kpi-row" id="kpis"></div>

  <div class="sec-title">方案成本构成对比 <span class="hint">运输/库存/人工/缺料四段 · 当前口径：${d.basis.label}</span></div>
  <div class="grid g-21">
    <div class="card"><h3>四段成本堆叠 <span class="hint">人工为固定班组常数；现行实验缺料=0</span></h3>
      <div class="plot" id="ch-cost"></div></div>
    <div class="card"><h3>相对基线成本节省</h3><div class="plot" id="ch-save"></div></div>
  </div>

  <div class="sec-title">成本瀑布归因 <span class="hint">每一步 = 一次方案升级的净效果</span></div>
  <div class="card tall"><div class="plot" id="ch-waterfall" style="height:340px"></div></div>

  <div class="sec-title" id="stress-sec" style="display:none">压力工况验证 <span class="hint">组3 同参数 · 消耗节奏 ≈×1.5 · 静态安全边际压力测试</span></div>
  <div class="grid g-21" id="stress-grid" style="display:none">
    <div class="card"><h3>10库合计库存：组3 vs 组5.1 <span class="hint">灰带 = 班次末需求突变窗</span></h3>
      <div class="plot" id="ch-stress" style="height:300px"></div></div>
    <div class="card"><h3>对照指标 <span class="hint" id="st-cur"></span></h3>
      <div style="overflow:auto"><table class="data" id="tbl-stress"></table></div>
      <div class="disclaimer" id="st-note"></div></div>
  </div>

  <div class="sec-title">10 库线边库存时间序列 <span class="hint">灰带 = 班次末需求突变窗（15 次）</span></div>
  <div class="card tall"><div class="plot" id="ch-series" style="height:360px"></div></div>

  <div class="sec-title">明细指标 <span class="hint">由 summaryreport + 原始日志计算</span></div>
  <div class="card" style="overflow:auto"><table class="data" id="tbl"></table></div>

  <div class="sec-title">设备状态（statereport）</div>
  <div class="grid g-2">
    <div class="card"><h3>AGV 小车时间占比</h3><div class="plot" id="ch-cars"></div></div>
    <div class="card"><h3>工位加工占比（10 工位均值）</h3><div class="plot" id="ch-ws"></div></div>
  </div>
  <div class="disclaimer">${d.basis.disclaimer} 公式回算可信度：库存均值公式复现组2=54.4/实测54.0、组3=20.0/实测20.65、组1=5.98/实测5.95 件/库（详见「参数即时测算」页）。</div>`;

  buildKpiCards(el, d);
  buildCostBar(el, d);
  buildSave(el, d);
  buildWaterfall(el, d);
  buildStress(el);
  buildSeries(el, d);
  buildTable(el, d);
  buildState(el, d);
}

function mk(el, id, opt) {
  const dom = el.querySelector(id);
  const c = echarts.init(dom, null, { renderer: "canvas" });
  c.setOption(opt);
  charts.push(c);
  return c;
}

function buildKpiCards(el, d) {
  const totals = d.groups.map((g) => g.cost.total);
  const best = Math.min(...totals);
  el.querySelector("#kpis").innerHTML = d.groups.map((g) => {
    const k = g.kpi;
    return `<div class="card kpi ${k && g.cost.total === best ? "best" : ""}">
      <div class="name"><span class="dot" style="background:${GROUP_COLORS[g.group]}"></span>${g.label}</div>
      <div class="big">${fmt.n(g.cost.total, 0)}<small>${curShort(g.cost.currency)}</small></div>
      <div class="line">平均库存 ${fmt.n(k.wip_avg_total)} 件 · 行驶 ${fmt.n(k.legs_total, 0)} 段</div>
      <div class="line">产出 ${fmt.n(k.station_output, 0)} 台 · 缺料 0 · 触零 ${fmt.n(k.recon_zero_min_total, 0)} 库·分</div>
    </div>`;
  }).join("");
}
const curShort = (c) => (c === "元" ? "元" : "相对值");

function buildCostBar(el, d) {
  const segs = ["transport", "inventory", "labor", "stockout"];
  const opt = baseOption({
    legend: { top: 0, data: segs.map((s) => COST_LABELS[s]) },
    grid: { left: 8, right: 16, top: 34, bottom: 4, containLabel: true },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (ps) => {
        const g = d.groups[ps[0].dataIndex];
        const rows = ps.map((p) =>
          `<span style="color:${p.color}">■</span> ${p.seriesName}：${fmt.n(p.value, 1)}`);
        return `<b>${g.label}</b><br>${rows.join("<br>")}<br>合计：<b>${fmt.n(g.cost.total, 1)}</b>`;
      },
    },
    xAxis: Object.assign(axisStyle(), { type: "category", data: d.groups.map((g) => `组${g.group}`), splitLine: { show: false } }),
    yAxis: Object.assign(axisStyle(`成本（${curShort(d.basis.currency)}）`), { type: "value" }),
    series: segs.map((s, i) => ({
      name: COST_LABELS[s], type: "bar", stack: "c", barMaxWidth: 56,
      itemStyle: {
        color: COST_COLORS[s],
        borderColor: "#fcfcfb", borderWidth: i ? 2 : 0, borderRadius: i === segs.length - 1 ? [4, 4, 0, 0] : 0,
      },
      data: d.groups.map((g) => g.cost[s]),
    })).concat([{
      name: "total", type: "scatter", symbolSize: 0, silent: true,
      label: { show: true, position: "top", color: INK, fontWeight: 700, fontSize: 12,
        formatter: (p) => fmt.n(d.groups[p.dataIndex].cost.total, 0) },
      data: d.groups.map((g) => [d.groups.indexOf(g), g.cost.total]),
    }]),
  });
  mk(el, "#ch-cost", opt);
}

function buildSave(el, d) {
  const base = d.groups[0].cost.total;
  const data = d.groups.slice(1).map((g) => ({
    value: +(((base - g.cost.total) / base) * 100).toFixed(1),
    itemStyle: { color: GROUP_COLORS[g.group], borderRadius: [0, 4, 4, 0] },
  }));
  mk(el, "#ch-save", baseOption({
    grid: { left: 8, right: 46, top: 26, bottom: 4, containLabel: true },
    legend: { show: false },
    tooltip: { formatter: (p) => `组${p.name} 较基线成本 −${p.value}%` },
    xAxis: Object.assign(axisStyle("%"), { type: "value", max: 60 }),
    yAxis: Object.assign(axisStyle(), { type: "category", data: d.groups.slice(1).map((g) => String(g.group)), inverse: true, splitLine: { show: false } }),
    series: [{
      type: "bar", data, barMaxWidth: 30,
      label: { show: true, position: "right", formatter: "−{c}%", color: INK, fontWeight: 700 },
    }],
  }));
}

function buildWaterfall(el, d) {
  const g = Object.fromEntries(d.groups.map((x) => [x.group, x]));
  const steps = [
    { name: "组1 基线\n逐件拉动", total: g[1].cost.total },
    { name: "批量补给\n(组1→组2定时)", delta: g[2].cost.total - g[1].cost.total, note: "" },
    { name: "阈值最小化\n(组2→组3 固定SS)⚠", delta: g[3].cost.total - g[2].cost.total, note: "策略+批量双变量" },
    { name: "AI 动态参数\n(组3→组4 SS_t)" , delta: g[4].cost.total - g[3].cost.total, note: "唯一干净对照" },
    { name: "组4 最终", total: g[4].cost.total },
  ];
  let run = 0; const helper = [], up = [], down = [], tot = [];
  steps.forEach((s, i) => {
    if (s.total !== undefined) {
      helper.push(0); up.push("-"); down.push("-"); tot.push(s.total);
      run = s.total;
    } else {
      const a = run, b = run + s.delta;
      helper.push(Math.min(a, b));
      if (s.delta >= 0) { up.push(Math.abs(s.delta)); down.push("-"); }
      else { up.push("-"); down.push(Math.abs(s.delta)); }
      tot.push("-");
      run = b;
    }
  });
  mk(el, "#ch-waterfall", baseOption({
    legend: { show: false },
    tooltip: {
      formatter: (p) => {
        if (p.seriesName !== "v") return "";
        const s = steps[p.dataIndex];
        const v = s.total !== undefined ? s.total : s.delta;
        const sign = s.total !== undefined ? "" : (v >= 0 ? "+" : "");
        return `<b>${s.name.replace("\n", " ")}</b><br>${s.total !== undefined ? "总成本" : "成本变化"}：${sign}${fmt.n(v, 1)}${s.note ? "<br>" + s.note : ""}`;
      },
    },
    xAxis: Object.assign(axisStyle(), { type: "category", data: steps.map((s) => s.name), splitLine: { show: false }, axisLabel: { color: INK2, fontSize: 11, interval: 0 } }),
    yAxis: Object.assign(axisStyle("成本"), { type: "value" }),
    series: [
      { name: "h", type: "bar", stack: "w", silent: true, itemStyle: { color: "transparent" }, data: helper, barMaxWidth: 64 },
      {
        name: "v", type: "bar", stack: "w", barMaxWidth: 64,
        data: steps.map((s, i) => ({
          value: s.total !== undefined ? s.total : Math.abs(s.delta),
          itemStyle: {
            color: s.total !== undefined ? "#3B3B36" : (s.delta >= 0 ? "#D55E00" : "#009E73"),
            borderRadius: [4, 4, 0, 0],
          },
          label: {
            show: true, position: "top", color: INK, fontWeight: 700, fontSize: 12,
            formatter: () => s.total !== undefined ? fmt.n(s.total, 0)
              : (s.delta >= 0 ? "+" : "−") + fmt.n(Math.abs(s.delta), 0),
          },
        })),
      },
    ],
  }));
}

async function buildStress(el) {
  const s = await api("/api/stress");
  if (!s.ready) return;
  el.querySelector("#stress-sec").style.display = "";
  el.querySelector("#stress-grid").style.display = "";
  const curN = s.basis.currency === "元" ? "元" : "相对值";
  el.querySelector("#st-cur").textContent = `当前口径：${s.basis.label}`;
  el.querySelector("#st-note").textContent = s.note;

  const ser = await api("/api/dashboard/series?groups=3,5.1");
  const cols = { "3": GROUP_COLORS[3], "5.1": GROUP_COLORS["5.1"] };
  const d = await api("/api/dashboard");
  mk(el, "#ch-stress", baseOption({
    legend: { top: 0, data: ser.groups.map((g) => g.label) },
    grid: { left: 8, right: 16, top: 30, bottom: 4, containLabel: true },
    tooltip: { trigger: "axis", valueFormatter: (v) => Number(v).toFixed(1) + " 件" },
    xAxis: Object.assign(axisStyle("仿真时刻"), { type: "value", min: 7200, max: 432000,
      axisLabel: { color: INK2, fontSize: 11, formatter: (v) => (v / 3600).toFixed(0) + "h" } }),
    yAxis: Object.assign(axisStyle("10库合计库存（件）"), { type: "value" }),
    series: ser.groups.map((grp, i) => ({
      name: grp.label, type: "line", large: true, sampling: "lttb", showSymbol: false,
      lineStyle: { width: 2, color: cols[grp.group] }, itemStyle: { color: cols[grp.group] },
      data: grp.t.map((t, j) => [t, grp.v[j]]),
      markArea: i === 0 ? {
        silent: true, itemStyle: { color: "rgba(138,138,130,.10)" },
        data: d.meta.surge_windows.map((w) => [{ xAxis: w[0] }, { xAxis: w[1] }]),
      } : undefined,
    })),
  }));

  const b = s.base.kpi, x = s.stress.kpi;
  const rows = [
    ["平均在库（10库合计，件）", b.wip_avg_total, x.wip_avg_total, 2, false],
    ["行驶段数", b.legs_total, x.legs_total, 0, true],
    ["入库箱数", b.boxes_in, x.boxes_in, 0, false],
    ["工作站产出（台）", b.station_output, x.station_output, 0, false],
    ["触零时长（库·分钟）", b.recon_zero_min_total, x.recon_zero_min_total, 0, true],
    ["任一库空库分钟", b.any_zero_min, x.any_zero_min, 0, true],
    ["缺料停线（分钟）", 0, 0, 0, false],
  ];
  const dot = (c) => `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${c};margin-right:5px"></span>`;
  el.querySelector("#tbl-stress").innerHTML =
    `<thead><tr><th>指标</th><th>${dot(GROUP_COLORS[3])}组3 基线</th><th>${dot(GROUP_COLORS["5.1"])}组5.1 压力</th><th>Δ</th></tr></thead><tbody>${
      rows.map(([name, v0, v1, dg, risk]) => {
        const dv = v1 - v0;
        const pct = v0 ? (dv / v0) * 100 : 0;
        const col = risk && dv > 0 ? "#D55E00" : risk && dv < 0 ? "#0072B2" : INK2;
        const dtxt = dv === 0 ? `<span class='badge ok'>0 ↔ 0</span>`
          : `<span style="color:${col};font-weight:700">${dv > 0 ? "+" : "−"}${fmt.n(Math.abs(pct), 0)}%</span>`;
        return `<tr><td>${name}</td><td>${fmt.n(v0, dg)}</td><td class="hl">${fmt.n(v1, dg)}</td><td>${dtxt}</td></tr>`;
      }).join("")}<tr><td>总成本（${curN}）</td><td>${fmt.n(s.base.cost.total, 1)}</td>
        <td class="hl">${fmt.n(s.stress.cost.total, 1)}</td>
        <td><span style="color:#D55E00;font-weight:700">+${fmt.n((s.stress.cost.total / s.base.cost.total - 1) * 100, 0)}%</span></td></tr>
    </tbody>`;
}

async function buildSeries(el, d) {
  const s = await api("/api/dashboard/series");
  const opt = baseOption({
    legend: { top: 0, data: Object.values(d.meta.labels) },
    toolbox: {
      right: 8, top: 0, itemSize: 14, iconStyle: { borderColor: MUTED },
      feature: { saveAsImage: { title: "导出PNG", name: "库存时序对比", backgroundColor: "#fff" } },
    },
    grid: { left: 8, right: 16, top: 34, bottom: 22, containLabel: true },
    tooltip: { trigger: "axis", confine: true },
    dataZoom: [{ type: "slider", height: 14, bottom: 2, borderColor: LINE, fillerColor: "rgba(0,114,178,.08)" }],
    xAxis: Object.assign(axisStyle("仿真时刻"), {
      type: "value", min: 7200, max: 432000,
      axisLabel: { color: INK2, fontSize: 11, formatter: (v) => (v / 3600).toFixed(0) + "h" },
    }),
    yAxis: Object.assign(axisStyle("10库合计库存（件）"), { type: "value" }),
    series: s.groups.map((grp, gi) => ({
      name: `组${grp.group} ${grp.label.split("·").pop()}`, type: "line",
      large: true, sampling: "lttb", showSymbol: false,
      lineStyle: { width: 2, color: GROUP_COLORS[grp.group], type: grp.group == 1 ? "dashed" : "solid" },
      itemStyle: { color: GROUP_COLORS[grp.group] },
      data: grp.t.map((t, i) => [t, grp.v[i]]),
      markArea: gi === 0 ? {
        silent: true, itemStyle: { color: "rgba(138,138,130,.10)" },
        data: d.meta.surge_windows.map((w) => [{ xAxis: w[0] }, { xAxis: w[1] }]),
      } : undefined,
    })),
  });
  mk(el, "#ch-series", opt);
}

function buildTable(el, d) {
  const rows = [
    ["平均在库件数（10库合计）", (g) => fmt.n(g.kpi.wip_avg_total, 2), true],
    ["库存最低值（单库）", (g) => fmt.n(g.kpi.wip_min_total, 1)],
    ["触零库位数量", (g) => fmt.n(g.kpi.zero_buffers, 0) + " / 10"],
    ["任一库位触零时长", (g) => fmt.n(g.kpi.any_zero_min, 0) + " 分钟"],
    ["入库箱数", (g) => fmt.n(g.kpi.boxes_in, 0)],
    ["行驶段数（车1+车2）", (g) => fmt.n(g.kpi.legs_total, 0) + `（${g.kpi.legs_car1}+${g.kpi.legs_car2}）`, true],
    ["工作站产出", (g) => fmt.n(g.kpi.station_output, 0) + " 台"],
    ["缺料停线", () => "0 分钟 <span class='badge ok'>四组一致</span>"],
    ["曲线重建标定", (g) => g.kpi.calibration_ok ? "<span class='badge ok'>通过</span>" : "<span class='badge warn'>有偏差</span>"],
  ];
  const totals = d.groups.map((g) => g.cost.total);
  const best = Math.min(...totals);
  el.querySelector("#tbl").innerHTML = `<thead><tr><th>指标</th>${
    d.groups.map((g) => `<th><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${GROUP_COLORS[g.group]};margin-right:5px"></span>组${g.group} ${g.label.split(" ").slice(1).join(" ")}</th>`).join("")
  }</tr></thead><tbody>${
    rows.map(([name, f, hl]) => `<tr><td>${name}</td>${
      d.groups.map((g) => `<td class="${hl ? "hl" : ""}">${f(g)}</td>`).join("")}</tr>`).join("")
  }<tr><td>总成本（${curShort(d.basis.currency)}）</td>${
    d.groups.map((g, i) => `<td class="hl">${fmt.n(totals[i], 1)}${totals[i] === best ? " <span class='badge ok'>最低</span>" : ""}</td>`).join("")}</tr>
  </tbody>`;
}

function buildState(el, d) {
  const carSegs = [["travel loaded", "重驶", "#0072B2"], ["travel empty", "空驶", "#56B4E9"],
    ["loading", "装货", "#009E73"], ["unloading", "卸货", "#E69F00"],
    ["waiting for transporter", "等任务", "#B8B8B0"]];
  const mk_ = (carState) => d.groups.map((g) => {
    const cars = Object.values(g.cars || {});
    return carSegs.map(([k, , col]) => {
      const v = cars.length ? cars.reduce((a, c) => a + (c[k] || 0), 0) / cars.length : 0;
      return { value: +v.toFixed(2), itemStyle: { color: col }, name: k };
    });
  });
  const data = mk_();
  mk(el, "#ch-cars", baseOption({
    legend: { top: 0, data: carSegs.map((s) => s[1]) },
    grid: { left: 8, right: 16, top: 30, bottom: 4, containLabel: true },
    xAxis: Object.assign(axisStyle(), { type: "category", data: d.groups.map((g) => `组${g.group}`), splitLine: { show: false } }),
    yAxis: Object.assign(axisStyle("%"), { type: "value", max: 100 }),
    series: carSegs.map((s, si) => ({
      name: s[1], type: "bar", stack: "t", barMaxWidth: 52,
      itemStyle: { color: s[2], borderColor: "#fcfcfb", borderWidth: 1 },
      data: data.map((row) => row[si].value),
    })),
  }));
  const wsAvg = d.groups.map((g) => {
    const wss = Object.values(g.workstations || {});
    return +(wss.reduce((a, w) => a + (w.processing || 0), 0) / Math.max(1, wss.length)).toFixed(2);
  });
  mk(el, "#ch-ws", baseOption({
    legend: { show: false },
    grid: { left: 8, right: 16, top: 26, bottom: 4, containLabel: true },
    xAxis: Object.assign(axisStyle(), { type: "category", data: d.groups.map((g) => `组${g.group}`), splitLine: { show: false } }),
    yAxis: Object.assign(axisStyle("%"), { type: "value", min: 90, max: 100 }),
    series: [{
      type: "bar", data: wsAvg.map((v, i) => ({ value: v, itemStyle: { color: GROUP_COLORS[d.groups[i].group], borderRadius: [4, 4, 0, 0] } })),
      barMaxWidth: 52, label: { show: true, position: "top", formatter: "{c}%", color: INK, fontWeight: 700 },
    }],
  }));
}
