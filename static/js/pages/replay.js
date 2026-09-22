/* 页面2：仿真回放 —— 地图热力 + AGV 动点 + 同步曲线 + 时间轴 */
import { api, fmt, invalidate } from "../store.js";
import { GROUP_COLORS, baseOption, axisStyle, INK, INK2, MUTED, LINE } from "../palette.js";
import { ShopMap } from "../replay/svg_map.js";
import { legIndexAt } from "../replay/anim.js";

const W0 = 7200, W1 = 432000;
const GROUPS = ["1", "2", "3", "4", "5.1"];
const SPEEDS = [["×60", 60], ["×300", 300], ["×1200", 1200], ["×3600", 3600]];
let cur = { g: "4", t: W0, playing: false, speed: 300, replay: null, map: null,
  chart: null, chartBuf: "L1-WIP-1", raf: 0, lastTs: 0, markTs: 0 };

export async function render(el) {
  stopAnim();
  if (cur.map) { cur.map = null; cur.chart = null; cur.chart2 = null; }  // 容器将被重建
  el.innerHTML = `
  <div class="toolbar">
    <div class="seg" id="gtabs">${GROUPS.map((g) =>
      `<button data-g="${g}" class="${g == cur.g ? "on" : ""}" style="${g == cur.g ? `background:${GROUP_COLORS[g]};color:#fff` : ""}">${g == "5.1" ? "压力5.1" : "组" + g}</button>`).join("")}</div>
    <button class="btn primary" id="play">▶ 播放</button>
    <div class="seg" id="spdtabs">${SPEEDS.map(([n, v]) =>
      `<button data-s="${v}" class="${v == cur.speed ? "on" : ""}">${n}</button>`).join("")}</div>
    <select id="bufsel" class="btn" style="padding:6px 10px"></select>
    <span style="font-variant-numeric:tabular-nums;font-size:15px;font-weight:700" id="clock">02:00:00</span>
    <span id="live" style="font-size:12px;color:#8a8a82"></span>
    <button class="btn" id="plan-btn" style="margin-left:auto">📐 模型平面图参考层</button>
  </div>

  <div class="grid" style="grid-template-columns:1.15fr 1fr">
    <div class="card" style="position:relative;overflow:hidden">
      <h3>车间布局回放 <span class="hint">滚轮缩放 · 拖拽平移 · 双击复位；红圈=该库触零（曲线为常数标定重建）</span></h3>
      <div id="map" style="height:560px"></div>
      <div id="plan-layer" class="plan-layer hidden">
        <div class="plan-head">FlexSim 模型平面图（用户提供，参考层）<button class="btn" id="plan-close">✕</button></div>
        <object data="/gen/plan.svg" type="image/svg+xml" style="width:100%;height:100%"></object>
      </div>
      <div class="hint" id="heat-legend" style="position:absolute;right:12px;bottom:8px;color:#8a8a82;font-size:11px"></div>
    </div>
    <div class="grid" style="grid-template-rows:auto 1fr;gap:14px">
      <div class="card"><h3>选中线边库库存曲线 <span class="hint">竖线=回放时刻</span></h3>
        <div class="plot" id="ch-inv" style="height:252px"></div></div>
      <div class="card"><h3>全线累计产出（台）</h3>
        <div class="plot" id="ch-out" style="height:200px"></div></div>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <input type="range" id="tl" min="${W0}" max="${W1}" step="60" value="${cur.t}"
      style="width:100%;accent-color:${GROUP_COLORS[cur.g]}">
    <div style="display:flex;justify-content:space-between;font-size:11px;color:#8a8a82">
      <span>02h</span><span>30h</span><span>60h</span><span>90h</span><span>120h</span></div>
  </div>
  <style>.plan-layer{position:absolute;inset:0;background:rgba(252,252,251,.97);z-index:5;display:flex;flex-direction:column}
    .plan-layer.hidden{display:none}
    .plan-head{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;font-size:12.5px;color:#55554f;border-bottom:1px solid #e4e4de}</style>`;

  el.querySelector("#plan-btn").onclick = () => el.querySelector("#plan-layer").classList.toggle("hidden");
  el.querySelector("#plan-close").onclick = () => el.querySelector("#plan-layer").classList.add("hidden");
  el.querySelectorAll("#gtabs button").forEach((b) => b.onclick = () => switchGroup(b.dataset.g, el));
  el.querySelectorAll("#spdtabs button").forEach((b) => b.onclick = () => {
    cur.speed = +b.dataset.s;
    el.querySelectorAll("#spdtabs button").forEach((x) => x.classList.toggle("on", x == b));
  });
  el.querySelector("#play").onclick = () => togglePlay(el);
  const tl = el.querySelector("#tl");
  tl.oninput = () => { cur.t = +tl.value; paint(el); };

  await loadGroup(cur.g, el);
}

async function loadGroup(g, el) {
  cur.g = String(g);
  el.querySelectorAll("#gtabs button").forEach((b) => {
    const on = b.dataset.g === cur.g;
    b.classList.toggle("on", on);
    b.style.cssText = on ? `background:${GROUP_COLORS[cur.g]};color:#fff` : "";
  });
  el.querySelector("#tl").style.accentColor = GROUP_COLORS[cur.g];
  let rp;
  try {
    rp = await api(`/api/replay/${g}`);
  } catch (e) {
    el.querySelector("#live").innerHTML = `<span style="color:#D55E00">组${g} 数据未接入（缺少压力数据文件或缓存未重建）</span>`;
    return;
  }
  const layout = await api("/api/layout");
  cur.replay = rp;
  if (!cur.map) cur.map = new ShopMap(el.querySelector("#map"), layout);
  let mx = 1;
  for (const b in rp.buffers) for (const v of rp.buffers[b].bins) { if (v > mx) mx = v; }
  cur.map.maxStock = mx / 100;
  const legend = el.querySelector("#heat-legend");
  if (legend) {
    legend.innerHTML = `库存水位色标 0 → ${mx / 100} 件：
      <span style="display:inline-block;width:110px;height:9px;border-radius:5px;vertical-align:middle;
        background:linear-gradient(90deg,#440154,#31688e,#1f9e89,#6dcd59,#fde725)"></span>`;
  }
  const bufsel = el.querySelector("#bufsel");
  bufsel.innerHTML = Object.keys(rp.buffers).map((b) =>
    `<option value="${b}" ${b == cur.chartBuf ? "selected" : ""}>${b.replace("L", "线").replace("-WIP-", "·库")}</option>`).join("");
  bufsel.onchange = () => { cur.chartBuf = bufsel.value; drawCharts(el); paint(el); };
  cur.t = W0;
  drawCharts(el);
  paint(el);
}

function switchGroup(g, el) { stopAnim(); cur.playing = false; setPlayBtn(el); loadGroup(g, el); }

function bufSeries(rp, id) {
  const b = rp.buffers[id];
  return b.bins.map((v, i) => [rp.window[0] + i * rp.bin + rp.bin / 2, v / 100]);
}

function drawCharts(el) {
  const rp = cur.replay;
  if (cur.chart) cur.chart.dispose();
  const dom = el.querySelector("#ch-inv");
  cur.chart = echarts.init(dom);
  const surge = rp.meta.surge_windows.map((w) => [{ xAxis: w[0] }, { xAxis: w[1] }]);
  const opt = baseOption({
    legend: { show: false },
    toolbox: { right: 4, feature: { saveAsImage: {} } },
    grid: { left: 8, right: 14, top: 26, bottom: 4, containLabel: true },
    tooltip: { trigger: "axis", valueFormatter: (v) => Number(v).toFixed(2) + " 件" },
    xAxis: Object.assign(axisStyle(), { type: "value", min: W0, max: W1,
      axisLabel: { color: INK2, fontSize: 10, formatter: (v) => (v / 3600).toFixed(0) + "h" } }),
    yAxis: Object.assign(axisStyle("件"), { type: "value", minInterval: 1 }),
    series: [{
      name: cur.chartBuf, type: "line", showSymbol: false, large: true, sampling: "lttb",
      lineStyle: { width: 2, color: GROUP_COLORS[cur.g] },
      areaStyle: { color: GROUP_COLORS[cur.g], opacity: 0.08 },
      data: bufSeries(rp, cur.chartBuf),
      markArea: { silent: true, itemStyle: { color: "rgba(138,138,130,.09)" }, data: surge },
      markLine: {
        symbol: "none", animation: false, silent: true,
        lineStyle: { color: INK, width: 1.5 },
        label: { show: false },
        data: [{ xAxis: cur.t }],
      },
    }],
  });
  cur.chart.setOption(opt);

  if (cur.chart2) cur.chart2.dispose();
  cur.chart2 = echarts.init(el.querySelector("#ch-out"));
  const ids = Object.keys(rp.station_out);
  const nb = rp.station_out[ids[0]].length;
  const tot = new Array(nb).fill(0);
  for (const id of ids) { const s = rp.station_out[id]; for (let i = 0; i < nb; i++) tot[i] += s[i]; }
  cur.chart2.setOption(baseOption({
    legend: { show: false },
    grid: { left: 8, right: 14, top: 26, bottom: 4, containLabel: true },
    xAxis: Object.assign(axisStyle(), { type: "value", min: W0, max: W1,
      axisLabel: { color: INK2, fontSize: 10, formatter: (v) => (v / 3600).toFixed(0) + "h" } }),
    yAxis: Object.assign(axisStyle("台"), { type: "value" }),
    series: [{
      type: "line", step: "end", showSymbol: false,
      lineStyle: { width: 2, color: "#3B3B36" }, areaStyle: { color: "#3B3B36", opacity: .06 },
      data: tot.map((v, i) => [W0 + i * rp.bin, v]),
      markLine: { symbol: "none", animation: false, silent: true,
        lineStyle: { color: INK, width: 1.5 }, label: { show: false }, data: [{ xAxis: cur.t }] },
    }],
  }));
}

function setPlayBtn(el) { el.querySelector("#play").textContent = cur.playing ? "⏸ 暂停" : "▶ 播放"; }

function togglePlay(el) {
  cur.playing = !cur.playing;
  setPlayBtn(el);
  if (cur.playing) { cur.lastTs = performance.now(); cur.raf = requestAnimationFrame((ts) => tick(ts, el)); }
  else stopAnim();
}
function stopAnim() { if (cur.raf) cancelAnimationFrame(cur.raf); cur.raf = 0; }

function tick(ts, el) {
  const dt = (ts - cur.lastTs) / 1000;
  cur.lastTs = ts;
  cur.t = Math.min(W1, cur.t + dt * cur.speed);
  paint(el, ts);
  if (cur.t >= W1) { cur.playing = false; setPlayBtn(el); return; }
  if (cur.playing) cur.raf = requestAnimationFrame((x) => tick(x, el));
}

function paint(el, ts = performance.now()) {
  const rp = cur.replay; if (!rp) return;
  el.querySelector("#tl").value = cur.t;
  el.querySelector("#clock").textContent = fmt.hms(cur.t);
  cur.map.update(cur.t, rp);
  /* 实时小计（≤8fps 更新文本/标线，防抖） */
  if (ts - cur.markTs > 120) {
    cur.markTs = ts;
    let legs = 0, loadedLegs = 0;
    for (const cid in rp.cars) {
      const L = rp.cars[cid].legs, i = legIndexAt(L, cur.t); legs += Math.max(0, i);
      for (let j = 0; j < i; j++) if (L[j][6]) loadedLegs++;
    }
    const idx = Math.min(rp.buffers["L1-WIP-1"].bins.length - 1, Math.floor((cur.t - W0) / rp.bin));
    let stock = 0;
    for (const b in rp.buffers) stock += rp.buffers[b].bins[idx] / 100;
    el.querySelector("#live").innerHTML =
      `线边在库 <b>${stock.toFixed(1)}</b> 件 · 已行驶 <b>${legs}</b>/${rp.meta.legs_expected} 段（重驶占 ${Math.round(loadedLegs / Math.max(1, legs) * 100)}%）`;
    if (cur.chart) {
      cur.chart.setOption({ series: [{ markLine: { data: [{ xAxis: cur.t }] } }] });
      cur.chart2.setOption({ series: [{ markLine: { data: [{ xAxis: cur.t }] } }] });
    }
  }
}
