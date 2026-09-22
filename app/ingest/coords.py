"""对象坐标表 → 布局模型（世界米坐标 + 屏幕像素变换 8px/m）+ FlexSim 路径名映射。"""
import csv
import re

# 与既有 线边物流平面布局图.html 一致的变换
SCALE = 8.0
X_OFF = 20.0
Y_OFF = 60.0


def to_px(x: float, y: float):
    return SCALE * (x + X_OFF), SCALE * (Y_OFF - y)


def load_coords(path):
    """返回 (rects, xy, size)。rects: [{id,label,cls,x,y,w,h,rot}], xy: {id:(x_m,y_m)}, size:{id:(w,h)}"""
    rects, xy, size = [], {}, {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f)
        header = next(rd)
        for row in rd:
            if len(row) < 9:
                continue
            name = row[1].strip()
            cls = row[3].strip()
            x, y = float(row[4]), float(row[5])
            w, h = float(row[6]), float(row[7])
            rot = float(row[8]) if row[8].strip() else 0.0
            rects.append({"id": name, "label": name, "cls": cls,
                          "x": x, "y": y, "w": w, "h": h, "rot": rot})
            xy[name] = (x, y)
            size[name] = (w, h)
    return rects, xy, size


_FLEXSID_MAP = [
    (re.compile(r"^/Line (\d) WIP Buffer Area (\d+)$"), lambda m: f"L{m.group(1)}-WIP-{m.group(2)}"),
    (re.compile(r"^/Line (\d) Workstation (\d+)$"), lambda m: f"L{m.group(1)}-WS-{m.group(2)}"),
    (re.compile(r"^/Line (\d) Finished Goods Buffer Area (\d+)$"), lambda m: f"L{m.group(1)}-FG-{m.group(2)}"),
    (re.compile(r"^/Translation Operator (\d+)$"), lambda m: f"TO-{m.group(1)}"),
    (re.compile(r"^/car (\d)$"), lambda m: f"car {m.group(1)}"),
    (re.compile(r"^/Central Warehouse.*$"), lambda m: "Central Warehouse"),
    (re.compile(r"^/Material Supermarket.*$"), lambda m: "Material Supermarket Loading Point"),
]


def flexsim_to_id(obj_path: str):
    """FlexSim 事件对象路径 → 坐标表 id；未识别返回 None。"""
    for pat, fn in _FLEXSID_MAP:
        m = pat.match(obj_path.strip())
        if m:
            return fn(m)
    return None


# 布局模型里用到的固定对象
GATE_ID = "Material Supermarket Loading Point"


def layout_model(rects, xy):
    """给前端的布局 JSON：viewBox + 矩形 + 门到库位的连线。"""
    xs = [xy[k][0] for k in xy]
    ys = [xy[k][1] for k in xy]
    pad = 6
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    p0 = to_px(x0, y1)
    p1 = to_px(x1, y0)
    links = []
    for cls_pref, y_side in (("L1-WIP-", 31.0), ("L2-WIP-", -29.0)):
        for i in range(1, 6):
            bid = f"{cls_pref}{i}"
            if bid in xy:
                links.append({"from": GATE_ID, "to": bid})
    return {
        "viewBox": {"x": p0[0], "y": p0[1], "w": p1[0] - p0[0], "h": p1[1] - p0[1]},
        "transform": {"scale": SCALE, "x_off": X_OFF, "y_off": Y_OFF},
        "rects": [
            {**r, "px": to_px(r["x"], r["y"])} for r in rects if r["cls"] in
            ("source", "queue", "wip", "processor", "fg", "agv")
        ],
        "links": links,
    }
