/* 全局 store：API 取数（带缓存）、订阅、健康横幅、格式化工具 */
const _cache = new Map();

export async function api(path, opts) {
  const key = path + (opts?.body ? JSON.stringify(opts.body) : "");
  if (!_cache.has(key)) {
    _cache.set(key, fetch(path, opts).then(async (r) => {
      if (!r.ok) { _cache.delete(key); throw new Error(`${path} → ${r.status}`); }
      return r.json();
    }));
  }
  return _cache.get(key);
}

export function invalidate(pathPrefix) {
  for (const k of [..._cache.keys()]) if (k.startsWith(pathPrefix)) _cache.delete(k);
}

export const fmt = {
  n: (v, d = 1) => Number(v).toLocaleString("zh-CN", { maximumFractionDigits: d, minimumFractionDigits: 0 }),
  pct: (v, d = 1) => (v >= 0 ? "+" : "") + Number(v).toFixed(d) + "%",
  hms: (s) => {
    s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  },
  h: (s) => (s / 3600).toFixed(1) + "h",
};

const subs = new Map();
export function on(evt, fn) {
  if (!subs.has(evt)) subs.set(evt, new Set());
  subs.get(evt).add(fn);
  return () => subs.get(evt).delete(fn);
}
export function emit(evt, payload) {
  (subs.get(evt) || []).forEach((fn) => fn(payload));
}

export function banner(msgs) {
  const el = document.getElementById("banner");
  if (!msgs || !msgs.length) { el.classList.add("hidden"); return; }
  el.textContent = "⚠ " + msgs.join("；");
  el.classList.remove("hidden");
}

export async function checkHealth() {
  try {
    const h = await api("/api/health");
    banner(h.warnings);
    return h;
  } catch (e) {
    banner([`后端未就绪：${e.message}`]);
    return null;
  }
}

export function basisChip(basis) {
  const el = document.getElementById("basis-chip");
  el.innerHTML = `成本口径 <b>${basis.label}</b>`;
  el.onclick = () => { location.hash = "#/cost"; };
}
