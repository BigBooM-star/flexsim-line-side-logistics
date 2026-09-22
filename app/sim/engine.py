"""迷你离散事件仿真：复刻 FlexSim 组3 逻辑 + 四组策略预设，用于参数测算校验。

事件堆 heapq；对象：2 条线 × 5 线边库 + 超市门 + 2 台 AGV（车与线绑定，与实测一致）。
需求：间隔 max(60, N(3600−1200·surge, 1080−360·surge))，surge=班次(28800s)最后 7200s。
行程模型（与日志腿结构一致）：车空闲时停在最后卸货位；任务开始先空驶回门（1段），
按箱装载 N(30,3)s，再逐库「载重行驶1段→卸货」。pull 策略逐件：重驶去→空驶回 = 2 段/箱。
路段时长：cache/distances.json 实测中位数；缺对时 曼哈顿×α 兜底。
统计窗与 FlexSim 一致：[7200, 432000]。
"""
import heapq
import json
import random

from ..settings import CACHE_DIR

W0, W1 = 7200.0, 432000.0
SHIFT, SURGE_AT = 28800.0, 21600.0
GATE = "gate"
LINES = {1: [f"L1-WIP-{i}" for i in range(1, 6)], 2: [f"L2-WIP-{i}" for i in range(1, 6)]}
CAR_OF_LINE = {1: "car 1", 2: "car 2"}
UNLOAD_MEAN, UNLOAD_SD = 30.0, 3.0

STRATEGY_PRESETS = {
    "pull": dict(strategy="pull", ss=0, target=1, cap=6, check_period=3600, cart_cap=6),
    "timer": dict(strategy="timer", ss=0, target=6, cap=6, check_period=3600, cart_cap=6),
    "threshold": dict(strategy="threshold", ss=1, target=3, cap=3, check_period=3600, cart_cap=8),
    "dynamic": dict(strategy="dynamic", ss=1, target=3, cap=3, check_period=3600, cart_cap=8),
}


def _is_surge(t):
    return (t % SHIFT) >= SURGE_AT


class _Buf:
    __slots__ = ("oid", "level", "cap", "demand_n", "starve_from", "stockout_min")

    def __init__(self, oid, cap, level):
        self.oid, self.level, self.cap = oid, level, cap
        self.demand_n = 0
        self.starve_from = None
        self.stockout_min = 0.0


class Sim:
    def __init__(self, params, seed=7, t_end=W1, ss_table=None, demand_mult=1.0):
        p = self.p = dict(params)
        self.rng = random.Random(seed)
        self.t_end = t_end
        self.ss_table = ss_table or []
        self.demand_mult = demand_mult
        dd = self._load_cache()
        self.pairs = dd["pairs"]
        self.alpha = dd["fallback_alpha_s_per_m"]
        self.xy = self._load_xy()
        self.buffers = {}
        for ln, ids in LINES.items():
            for oid in ids:
                init = p["cap"] if p["strategy"] == "pull" else min(p["target"], p["cap"])
                self.buffers[oid] = _Buf(oid, p["cap"], init)
        self.prev_levels = sum(b.level for b in self.buffers.values())
        self.cars = {}
        for i, cid in CAR_OF_LINE.items():
            self.cars[cid] = {"line": i, "pos": "gate", "free_at": 0.0, "plan": None}
        self.heap = []
        self._i = 0
        self.legs = 0
        self.travel_sec = 0.0
        self.integral = 0.0
        self.integ_t = 0.0
        self.zero_min = 0.0
        self._heat_t = 0.0
        self.output = 0
        for oid in self.buffers:
            self._at(0.0, "demand", oid)
        for ln in (1, 2):
            self._at(0.0, "tick", ln)
        self._at(0.0, "sample", None)

    @staticmethod
    def _load_cache():
        p = CACHE_DIR / "distances.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"pairs": {}, "fallback_alpha_s_per_m": 1.4}

    @staticmethod
    def _load_xy():
        p = CACHE_DIR / "layout.json"
        if not p.exists():
            return {}
        L = json.loads(p.read_text(encoding="utf-8"))
        tf = L["transform"]
        xy = {r["id"]: (r["px"][0] / tf["scale"] - tf["x_off"],
                        tf["y_off"] - r["px"][1] / tf["scale"]) for r in L["rects"]}
        xy[GATE] = xy.get("Material Supermarket Loading Point", (0, 0))
        return xy

    # ---------------- 事件堆 ----------------
    def _at(self, t, kind, payload=None):
        self._i += 1
        heapq.heappush(self.heap, (round(t, 6), self._i, kind, payload))

    def run(self):
        self.t = 0.0
        while self.heap:
            t, _, kind, payload = heapq.heappop(self.heap)
            if t > self.t_end:
                break
            self._integrate(t)
            self.t = t
            getattr(self, "_ev_" + kind)(payload)
        self._integrate(min(self.t_end, max(t, self.t)))
        return self.result()

    def _integrate(self, t):
        a, b = max(self.integ_t, W0), min(t, W1)
        if b > a:
            self.integral += self.prev_levels * (b - a)
        self.integ_t = t

    # ---------------- 需求 ----------------
    def _ev_demand(self, oid):
        b = self.buffers[oid]
        surge = _is_surge(self.t)
        dt = max(60.0, self.rng.gauss(3600 - 1200 * surge, 1080 - 360 * surge)) / self.demand_mult
        if W0 <= self.t <= W1:
            if b.level >= 1:
                b.level -= 1
                self.prev_levels -= 1
                b.demand_n += 1
                self.output += 1
                if b.starve_from is not None:      # 有货=停线结束
                    b.stockout_min += (self.t - b.starve_from) / 60
                    b.starve_from = None
            else:
                if b.starve_from is None:
                    b.starve_from = self.t
        if self.p["strategy"] == "pull":
            self._at(self.t, "pull_request", oid)
        self._at(self.t + dt, "demand", oid)

    # ---------------- 轮询 tick ----------------
    def _ev_tick(self, ln):
        if self.p["strategy"] != "pull":
            self._dispatch(ln)
        self._at(self.t + self.p["check_period"], "tick", ln)

    # ---------------- 采样（触零库·分钟）----------------
    def _ev_sample(self, _):
        if W0 <= self.t <= W1:
            self.zero_min += sum(1 for b in self.buffers.values() if b.level <= 0) * 0.5
        self._at(self.t + 30.0, "sample")

    # ---------------- 组货逻辑（threshold / dynamic / timer）----------------
    def _ss(self, t):
        p = self.p
        if p["strategy"] != "dynamic":
            return p["ss"]
        h = int(t // 3600)
        for hour, v in self.ss_table:
            if hour == h:
                return v
        return p["ss"] + (1 if _is_surge(t) else 0)   # 无表：突变窗 SS+1 启发式

    def _need_map(self, ln):
        p = self.p
        ss = p["target"] if p["strategy"] == "timer" else self._ss(self.t) + 0.001
        out = {}
        for oid in LINES[ln]:
            b = self.buffers[oid]
            if b.level < ss or p["strategy"] == "timer":
                want = min(p["target"], b.cap) - b.level
                if want > 0:
                    out[oid] = int(want)
        return out

    def _dispatch(self, ln):
        cid = CAR_OF_LINE[ln]
        car = self.cars[cid]
        if self.t < car["free_at"] or car["plan"] is not None:
            return
        need = self._need_map(ln)
        if not need:
            return
        left, plan = self.p["cart_cap"], {}
        for oid in LINES[ln]:                      # 固定 w1→w5 顺序
            if oid in need and left > 0:
                k = min(need[oid], left)
                plan[oid] = k
                left -= k
        car["plan"] = plan
        n = sum(plan.values())
        self._start_leg(cid, car["pos"], GATE, loaded=False,
                        then=("load", n), unload_at=None)

    # ---------------- pull：逐件请求（每次消耗触发一件）----------------
    def _ev_pull_request(self, oid):
        b = self.buffers[oid]
        if b.level >= b.cap:                       # 已补满，请求作废
            return
        ln = 1 if oid.startswith("L1") else 2
        cid = CAR_OF_LINE[ln]
        car = self.cars[cid]
        if self.t < car["free_at"] or car["plan"] is not None or car["pos"] != GATE:
            self._at(self.t + 10.0, "pull_request", oid)
            return
        car["plan"] = {oid: 1}
        self._start_leg(cid, GATE, oid, loaded=True, then=("unload", 1), unload_at=oid)

    # ---------------- 腿与装卸生命周期 ----------------
    def _start_leg(self, cid, frm, to, loaded, then, unload_at):
        car = self.cars[cid]
        d = self._dur(frm, to)
        self.legs += 1
        self.travel_sec += d
        car["pos"] = to
        self._at(self.t + d, "arrive", (cid, frm, to, loaded, then, unload_at))

    def _ev_arrive(self, payload):
        cid, frm, to, loaded, then, unload_at = payload
        car = self.cars[cid]
        kind, arg = then
        if kind == "load":                          # 已到门 → 装货
            dur = arg * UNLOAD_MEAN + self.rng.gauss(0, UNLOAD_SD)
            car["free_at"] = self.t + dur
            self._at(self.t + dur, "load_done", cid)
        elif kind == "unload":                      # 到达目的库 → 卸货
            plan = car["plan"] or {}
            k = plan.pop(to, arg)
            dur = max(1.0, k) * UNLOAD_MEAN + self.rng.gauss(0, UNLOAD_SD)
            self._at(self.t + dur, "unload_done", (cid, to, k))

    def _ev_load_done(self, cid):
        car = self.cars[cid]
        plan = car["plan"] or {}
        if not plan:
            car["plan"] = None
            return
        nxt = next(iter(plan))
        self._start_leg(cid, GATE, nxt, loaded=True, then=("unload", plan[nxt]), unload_at=nxt)

    def _ev_unload_done(self, payload):
        cid, oid, k = payload
        car = self.cars[cid]
        b = self.buffers[oid]
        add = min(k, b.cap - b.level)
        if add > 0:
            b.level += add
            self.prev_levels += add
        if b.starve_from is not None and b.level >= 1:
            b.stockout_min += (self.t - b.starve_from) / 60
            b.starve_from = None
        plan = car["plan"] or {}
        if plan:
            nxt = next(iter(plan))
            self._start_leg(cid, oid, nxt, loaded=True, then=("unload", plan[nxt]), unload_at=nxt)
        else:
            car["plan"] = None
            car["free_at"] = max(car["free_at"], self.t)
            ln = car["line"]
            if self.p["strategy"] == "pull":
                # 逐件：空驶回门等待下一件请求（回门=1段，计入腿数）
                self._start_leg(cid, oid, GATE, loaded=False, then=("home", 0), unload_at=None)
            else:
                self._dispatch(ln)

    def _dur(self, a, b):
        pa, pb = self.xy.get(a), self.xy.get(b)
        if not pa or not pb:
            return 60.0
        for k in (f"{a}->{b}", f"{b}->{a}"):
            rec = self.pairs.get(k)
            if rec:
                return rec["median_s"]
        return (abs(pa[0] - pb[0]) + abs(pa[1] - pb[1])) * self.alpha

    # ---------------- 结果 ----------------
    def result(self):
        hours = W1 - W0
        so = sum(b.stockout_min for b in self.buffers.values())
        return {
            "strategy": self.p["strategy"],
            "wip_avg_total": round(self.integral / hours, 2),
            "legs": self.legs,
            "output": self.output,
            "boxes_delivered": self.output,
            "stockout_min": round(so, 1),
            "zero_buf_min": round(self.zero_min, 0),
            "travel_hours": round(self.travel_sec / 3600, 1),
            "per_buffer_demand": {b.oid: b.demand_n for b in self.buffers.values()},
            "params": self.p,
            "seed_ok": True,
        }
