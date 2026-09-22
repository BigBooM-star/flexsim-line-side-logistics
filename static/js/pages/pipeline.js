/* 页面5：闭环演示 —— 数据→对比→测算→SS_t导出→回填FlexSim（导出为真实功能） */
import { api, fmt } from "../store.js";
import { GROUP_COLORS } from "../palette.js";

const NODES = [
  ["📥", "数据接入", "FlexSim 120h 实验日志<br>报表 · 坐标表 · 平面图"],
  ["📊", "四组对比看板", "KPI+成本口径联动<br>曲线重建 · 标定校验"],
  ["🧮", "参数即时测算", "解析公式 + 迷你仿真<br>组3标定偏差 ≤6%"],
  ["📤", "SS_t 参数导出", "生成 FlexSim importtable<br>121 行 hour,value（本页真实功能）"],
  ["🔄", "回填仿真实验", "调参→重跑→再对比<br>形成方案优化闭环"],
];

export async function render(el) {
  const dash = await api("/api/dashboard");
  el.innerHTML = `
  <div class="pipe">
    ${NODES.map(([ic, t, s], i) => `
      <div class="pnode"><div class="pic">${ic}</div><b>${t}</b><span>${s}</span></div>
      ${i < NODES.length - 1 ? '<div class="parrow">→</div>' : ""}`).join("")}
  </div>
  <style>
    .pipe{display:flex;align-items:stretch;gap:6px;flex-wrap:wrap;justify-content:center}
    .pnode{flex:1;min-width:170px;max-width:230px;background:var(--card);border:1px solid var(--line);
      border-radius:12px;box-shadow:var(--shadow);padding:14px;text-align:center;font-size:12.5px;color:var(--ink-2)}
    .pnode b{display:block;color:var(--ink);margin:6px 0 3px}
    .pic{font-size:26px}
    .parrow{align-self:center;font-size:20px;color:#b0b0a8}
  </style>

  <div class="grid g-2" style="margin-top:16px">
    <div class="card">
      <h3>📤 SS_t 参数表导出 <span class="hint">真实可用 · FlexSim importtable 直读</span></h3>
      <div class="slider-row"><label>基线 SS（件）</label><input id="base" class="ipt" type="number" step="0.5" min="0" max="4" value="1" style="width:80px"></div>
      <div class="slider-row"><label>突变班增提（件）</label><input id="boost" class="ipt" type="number" step="0.5" min="0" max="3" value="1" style="width:80px"></div>
      <div style="display:flex;gap:10px">
        <button class="btn" id="pv">预览前12行</button>
        <a class="btn primary" id="dl" href="/api/export/ss-table?base=1&surge_boost=1" download="ss_table.csv">⬇ 下载 ss_table.csv（121行）</a>
      </div>
      <pre class="formula" id="pvout" style="max-height:220px;overflow:auto"></pre>
      <div class="disclaimer">FlexSim 端用法：<code>importtable("SS_t", "ss_table.csv", 0)</code>，组4 逻辑按小时查表取 SS。
        这就是「参数变活」的落地通道：本软件测算出的 SS_t 可直接灌回实验环境复跑验证。</div>
    </div>
    <div class="card">
      <h3>🤖 AI 动态安全库存模块 <span class="badge na">本版未启用</span></h3>
      <p style="font-size:13px">本软件当前呈现的是<b>四组对照实验的既成结论</b>与参数测算能力；SS_t 表由实验方案给定。</p>
      <table class="data"><tbody>
        <tr><td>实验设计</td><td>组3 静态 SS=1 ↔ 组4 动态 SS_t（唯一干净对照）</td></tr>
        <tr><td>AI 净贡献①</td><td class="hl">库存均值 20.65→23.25 件（+12.6%过配）</td></tr>
        <tr><td>AI 净贡献②</td><td class="hl">行驶段数 1118→1299（+16.2%）</td></tr>
        <tr><td>AI 净贡献③ ⭐</td><td class="hl" style="color:#136c3a">触零时长 972→120 库·分钟（<b>−87%</b>，10/10→7/10 库）</td></tr>
        <tr><td>产出/缺料</td><td>产出 1291 台持平；缺料四组=0（下限达成，无可再降）</td></tr>
        <tr><td>拟合现状（诚实口径）</td><td>XGBoost 对最优 SS_t 回归 R²=0.020 → 启发式查表优于学习模型</td></tr>
      </tbody></table>
      <div class="disclaimer">答辩话术：AI 的价值不在"省库存"而在<b>消隐触零风险</b>——缺料=0 的严约束下用 +12.6% 库存杠杆换取 −87% 断供暴露；
        这正是「SS=0 压力演示」（测算页）能翻盘的原因：无动态调节时缺料成本立刻复活。</div>
    </div>
  </div>`;
  const upd = () => {
    const b = el.querySelector("#base").value, s = el.querySelector("#boost").value;
    el.querySelector("#dl").href = `/api/export/ss-table?base=${b}&surge_boost=${s}`;
  };
  ["#base", "#boost"].forEach((q) => el.querySelector(q).oninput = upd);
  el.querySelector("#pv").onclick = async () => {
    const b = el.querySelector("#base").value, s = el.querySelector("#boost").value;
    const txt = await fetch(`/api/export/ss-table?base=${b}&surge_boost=${s}`).then((r) => r.text());
    el.querySelector("#pvout").textContent = txt.split("\r\n").slice(0, 12).join("\n") + "\n…";
  };
}
