/* SVG 车间地图：布局渲染 + 库存热力 + AGV 动点（dataviz：热力用 viridis + 数字冗余编码） */
import { VIRIDIS } from "../palette.js";

const S = 8; // px/m（与后端 layout.transform 一致）

function viridis(t) {
  t = Math.max(0, Math.min(1, t)) * (VIRIDIS.length - 1);
  const i = Math.floor(t), f = t - i;
  const a = hex(VIRIDIS[i]), b = hex(VIRIDIS[Math.min(i + 1, VIRIDIS.length - 1)]);
  return `rgb(${mix(a[0], b[0], f)},${mix(a[1], b[1], f)},${mix(a[2], b[2], f)})`;
}
function hex(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
function mix(a, b, f) { return Math.round(a + (b - a) * f); }

const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs) => {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
};

export class ShopMap {
  /** container: HTMLElement; layout: /api/layout 返回 */
  constructor(container, layout, { maxStock = 6 } = {}) {
    this.maxStock = maxStock;
    const tf = layout.transform || { scale: 8, x_off: 20, y_off: 60 };
    /* 日志腿坐标是 FlexSim 米制 → 与布局同一 px 空间 */
    this.m2px = (x, y) => [tf.scale * (x + tf.x_off), tf.scale * (tf.y_off - y)];
    this.vb = { ...layout.viewBox };
    const svg = this.svg = el("svg", {
      viewBox: `${this.vb.x} ${this.vb.y} ${this.vb.w} ${this.vb.h}`,
      preserveAspectRatio: "xMidYMid meet", style: "width:100%;height:100%;background:#fcfcfb",
    });
    container.appendChild(svg);

    const gLink = el("g", {}), gRect = el("g", {}), gLab = el("g", {}), gCar = el("g", {});
    svg.append(gLink, gRect, gLab, gCar);

    const pxOf = {}; const byId = {};
    for (const r of layout.rects) { pxOf[r.id] = r.px; byId[r.id] = r; }

    /* 链接：超市门 → WIP */
    for (const l of layout.links) {
      const a = pxOf[l.from], b = pxOf[l.to];
      if (!a || !b) continue;
      gLink.appendChild(el("line", {
        x1: a[0], y1: a[1], x2: b[0], y2: b[1],
        stroke: "#dcdcd4", "stroke-width": 1.2, "stroke-dasharray": "4 3",
      }));
    }

    /* 对象矩形 */
    this.bufEls = {}; // id -> {rect, text, ring}
    for (const r of layout.rects) {
      const w = Math.max(10, r.w * S), h = Math.max(10, r.h * S);
      const [cx, cy] = r.px;
      const isWip = r.cls === "wip", isFg = r.cls === "fg", isProc = r.cls === "processor";
      const rect = el("rect", {
        x: cx - w / 2, y: cy - h / 2, width: w, height: h, rx: 3,
        fill: isWip ? "#eee" : isProc ? "#3B3B36" : "#e8e8e2",
        stroke: isWip ? "#c8c8c0" : "#b8b8ae", "stroke-width": 1,
      });
      gRect.appendChild(rect);
      let text = null;
      if (isWip) {
        text = el("text", {
          x: cx, y: cy + 3.5, "text-anchor": "middle", "font-size": 9,
          "font-weight": 700, fill: "#fff", style: "paint-order:stroke;stroke:rgba(0,0,0,.35);stroke-width:2",
        });
        gLab.appendChild(text);
        const ring = el("circle", { cx, cy, r: 11, fill: "none", stroke: "#D55E00", "stroke-width": 2.5, visibility: "hidden" });
        gLab.appendChild(ring);
        this.bufEls[r.id] = { rect, text, ring, cx, cy };
      }
      /* 静态小标签 */
      const short = isWip ? r.id.replace(/^L(\d)-WIP-/, "L$1·") :
        isFg ? r.id.replace(/^L(\d)-FG-/, "出$1·") :
        isProc ? r.id.replace(/^L(\d)-WS-/, "工位$1·") : r.label;
      const lab = el("text", {
        x: cx, y: cy - h / 2 - 4, "text-anchor": "middle", "font-size": 8.5, fill: "#8a8a82",
      });
      lab.textContent = short;
      gLab.appendChild(lab);
    }

    /* AGV 动点 */
    this.carEls = {};
    for (const cid of Object.keys(byId).filter((k) => k.startsWith("car "))) {
      const dot = el("g", {});
      const c = el("circle", { r: 7, fill: "#0072B2", stroke: "#fcfcfb", "stroke-width": 2 });
      const t = el("text", { x: 0, y: -10, "text-anchor": "middle", "font-size": 9, "font-weight": 700, fill: "#1a1a19" });
      t.textContent = cid.replace("car ", "车");
      dot.append(c, t);
      gCar.appendChild(dot);
      this.carEls[cid] = { dot, c };
    }

    /* 缩放/平移 */
    this._drag = null;
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const k = e.deltaY > 0 ? 1.12 : 1 / 1.12;
      const p = this._toVb(e);
      this.vb.x = p.x - (p.x - this.vb.x) * k; this.vb.y = p.y - (p.y - this.vb.y) * k;
      this.vb.w *= k; this.vb.h *= k;
      this._applyVb();
    }, { passive: false });
    svg.addEventListener("pointerdown", (e) => { this._drag = [e.clientX, e.clientY]; });
    svg.addEventListener("pointermove", (e) => {
      if (!this._drag) return;
      const sc = this.vb.w / svg.clientWidth;
      this.vb.x -= (e.clientX - this._drag[0]) * sc;
      this.vb.y -= (e.clientY - this._drag[1]) * sc;
      this._drag = [e.clientX, e.clientY];
      this._applyVb();
    });
    const stop = () => { this._drag = null; };
    svg.addEventListener("pointerup", stop); svg.addEventListener("pointerleave", stop);
    svg.addEventListener("dblclick", () => { this.vb = { ...layout.viewBox }; this._applyVb(); });
    this._home = { ...layout.viewBox };
  }
  _toVb(e) {
    const b = this.svg.getBoundingClientRect();
    return {
      x: this.vb.x + (e.clientX - b.left) / b.width * this.vb.w,
      y: this.vb.y + (e.clientY - b.top) / b.height * this.vb.h,
    };
  }
  _applyVb() {
    this.svg.setAttribute("viewBox", `${this.vb.x} ${this.vb.y} ${this.vb.w} ${this.vb.h}`);
  }

  /** buffers: {id: {bins:[int×100]}}, bin/window; t 秒 → 更新热力/触零/车辆 */
  update(t, replay) {
    const { buffers, window: win, bin } = replay;
    const idx = Math.max(0, Math.min(bins_len(buffers) - 1, Math.floor((t - win[0]) / bin)));
    this.idx = idx;
    for (const id in this.bufEls) {
      const b = buffers[id]; if (!b) continue;
      const v = b.bins[idx] / 100;
      const B = this.bufEls[id];
      B.rect.setAttribute("fill", viridis(v / this.maxStock));
      B.text.textContent = v.toFixed(0);
      B.ring.setAttribute("visibility", v <= 0.5 ? "visible" : "hidden");
    }
    for (const cid in this.carEls) {
      const legs = (replay.cars[cid] || {}).legs || [];
      const pos = carAt(legs, t);
      if (!pos) continue;
      const [px, py] = this.m2px(pos.x, pos.y);
      const E = this.carEls[cid];
      E.dot.setAttribute("transform", `translate(${px.toFixed(1)},${py.toFixed(1)})`);
      E.c.setAttribute("fill", pos.loaded ? "#0072B2" : "#B8B8B0");
    }
  }
}

function bins_len(buffers) {
  for (const k in buffers) return buffers[k].bins.length;
  return 1;
}
function carAt(legs, t) {
  let cur = null;
  for (const L of legs) {
    if (L[0] <= t) {
      if (t >= L[1]) cur = { x: L[4], y: L[5], loaded: !!L[6] };
      else {
        const f = (t - L[0]) / Math.max(0.001, L[1] - L[0]);
        return { x: L[2] + (L[4] - L[2]) * f, y: L[3] + (L[5] - L[3]) * f, loaded: !!L[6] };
      }
    } else break;
  }
  return cur || (legs.length ? { x: legs[0][2], y: legs[0][3], loaded: false } : null);
}
