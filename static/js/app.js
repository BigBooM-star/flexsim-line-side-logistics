/* hash 路由 + 健康检查 + 页面模块按需加载 */
import { checkHealth, api, basisChip } from "./store.js";
import * as dashboard from "./pages/dashboard.js";

const PAGES = {
  dashboard: () => dashboard,
  replay: () => import("./pages/replay.js"),
  estimate: () => import("./pages/estimate.js"),
  cost: () => import("./pages/cost.js"),
  pipeline: () => import("./pages/pipeline.js"),
};

const DEFAULT = "dashboard";

async function route() {
  const name = (location.hash.replace(/^#\//, "") || DEFAULT).split("?")[0];
  const loader = PAGES[name] || PAGES[DEFAULT];
  document.querySelectorAll(".tabs a").forEach((a) =>
    a.classList.toggle("on", a.dataset.route === name));
  const el = document.getElementById("page");
  el.innerHTML = '<div class="card" style="color:#8a8a82">加载中…</div>';
  let mod;
  try { mod = await loader(); } catch (e) {
    el.innerHTML = `<div class="card"><b>页面模块加载失败</b><div class="formula">${e.message}</div></div>`;
    return;
  }
  try { await mod.render(el); } catch (e) {
    el.innerHTML = `<div class="card"><b>页面渲染失败</b><div class="formula">${e.stack || e.message}</div></div>`;
  }
}

window.addEventListener("hashchange", route);
(async () => {
  await checkHealth();
  try {
    const d = await api("/api/dashboard");
    if (d.ready) basisChip(d.basis);
  } catch { /* 健康横幅已提示 */ }
  route();
})();
