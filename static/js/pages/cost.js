/* 页面4：成本口径 —— 预设切换 + 系数编辑（PUT 持久化） */
import { api, invalidate, fmt, banner } from "../store.js";
import { COST_COLORS, COST_LABELS } from "../palette.js";

const UNITS = {
  c_d_per_leg: "元(或相对值) / 行驶段",
  h_per_unit_hour: "元 / 件·小时",
  c_labor_per_shift_hour: "元 / 人·小时",
  c_stop_per_minute: "元 / 停线分钟",
};
export async function render(el) {
  const d = await api("/api/cost");
  const a = d.active, ps = d.presets;
  el.innerHTML = `
  <div class="grid g-2">
    <div class="card">
      <h3>预设方案 <span class="hint">一键切换，看板/测算/导出全局联动</span></h3>
      ${Object.entries(ps).map(([k, v]) => `
        <label class="btn" style="display:flex;gap:10px;align-items:flex-start;margin:8px 0;width:auto;
          ${k == a.preset ? "outline:2px solid " + "#1a1a19;outline-offset:-2px" : ""};cursor:pointer">
          <input type="radio" name="pre" value="${k}" ${k == a.preset ? "checked" : ""} style="margin-top:4px">
          <span><b>${v.label}</b><br>
          <span style="font-size:11.5px;color:#8a8a82">${v.disclaimer}<br>
          ${Object.keys(v.coefficients).map((c) => `${COST_LABELS[{"c_d_per_leg":"transport","h_per_unit_hour":"inventory","c_labor_per_shift_hour":"labor","c_stop_per_minute":"stockout"}[c]]}系数 = ${v.coefficients[c]}`).join(" · ")}</span></span>
        </label>`).join("")}
    </div>
    <div class="card">
      <h3>逐系数编辑 <span class="hint">保存后立即生效并持久化到 config/cost_basis.json</span></h3>
      <div class="slider-row"><label>预设名称</label><input id="f-preset" class="ipt" value="${a.preset}" style="flex:1"></div>
      <div class="slider-row"><label>显示名 label</label><input id="f-label" class="ipt" value="${a.label}" style="flex:1"></div>
      <div class="slider-row"><label>货币单位</label><input id="f-currency" class="ipt" value="${a.currency}" style="width:100px">
        <label style="width:auto">人·小时总量</label><input id="f-labor" class="ipt" type="number" value="${a.quantities.labor_person_hours}" style="width:90px"></div>
      ${Object.entries(a.coefficients).map(([k, v]) => `
        <div class="slider-row"><label><span style="display:inline-block;width:9px;height:9px;border-radius:3px;background:${COST_COLORS[{"c_d_per_leg":"transport","h_per_unit_hour":"inventory","c_labor_per_shift_hour":"labor","c_stop_per_minute":"stockout"}[k]]};margin-right:6px"></span>${k}</span>
          <span class="hint" style="width:130px;color:#8a8a82;font-size:11px">${UNITS[k]}</span>
          <input id="c-${k}" class="ipt" type="number" step="0.01" min="0" value="${v}" style="flex:1"></div>`).join("")}
      <div class="slider-row"><label>免责声明</label><input id="f-disc" class="ipt" value="${a.disclaimer}" style="flex:1"></div>
      <div style="display:flex;gap:10px;margin-top:12px">
        <button class="btn primary" id="save">保存并应用</button>
        <button class="btn" id="reset">恢复激活预设原值</button>
      </div>
      <style>.ipt{border:1px solid #d8d8d0;border-radius:6px;padding:6px 8px;font:inherit;background:#fff}</style>
    </div>
  </div>
  <div class="disclaimer">为什么人工是常数：四组实验的配送作业由同一班组+同一双车承担，方案改变的是<b>参数与节拍</b>而非人力配置，
    因此本软件只声称「运输/库存成本」的相对节省，不声称节省人工——这是答辩防挑刺口径。</div>
  <div class="disclaimer">合规提示：预设B的绝对单价为行业惯例占位值（非企业实价），答辩引用绝对金额前需企业参数确认；预设A只给相对改善幅度。</div>`;

  el.querySelectorAll("input[name=pre]").forEach((r) => r.onchange = async () => {
    invalidate("/api/");
    await fetch(`/api/cost/preset/${r.value}`, { method: "POST" });
    render(el);
  });
  el.querySelector("#save").onclick = async () => {
    const body = {
      preset: el.querySelector("#f-preset").value,
      label: el.querySelector("#f-label").value,
      currency: el.querySelector("#f-currency").value,
      disclaimer: el.querySelector("#f-disc").value,
      coefficients: Object.fromEntries(Object.keys(UNITS).map((k) =>
        [k, +el.querySelector("#c-" + k).value])),
      quantities: { labor_person_hours: +el.querySelector("#f-labor").value, cost_window_hours: 120 },
    };
    const r = await fetch("/api/cost", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (r.ok) {
      invalidate("/api/"); banner([]);
      const ok = document.createElement("span");
      ok.textContent = " ✓ 已保存"; ok.style.color = "#136c3a";
      el.querySelector("#save").after(ok); setTimeout(() => ok.remove(), 2500);
    } else {
      const e = await r.json();
      banner(["保存被拒绝：" + JSON.stringify(e.detail || e)]);
    }
  };
  el.querySelector("#reset").onclick = () => render(el);
}
