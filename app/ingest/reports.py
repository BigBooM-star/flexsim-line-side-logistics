"""summaryreport / statereport 解析（FlexSim 报表 → KPI 字典）。"""
import pandas as pd

# 报表对象名（不带前导斜杠）→ 用途
WIP_RE = "WIP Buffer Area"
FG_RE = "Finished Goods Buffer Area"
WS_RE = "Workstation"
CAR_RE = "car "


def _clean_obj(name: str) -> str:
    return str(name).strip()


def load_summary(path) -> pd.DataFrame:
    """3 行前言 + 33 列。返回按 Object 索引的 DataFrame。"""
    df = pd.read_csv(path, skiprows=3, encoding="utf-8-sig")
    df["Object"] = df["Object"].map(_clean_obj)
    return df.set_index("Object", drop=False)


def load_state(path) -> dict:
    """FlexSim 状态报表：每对象一行百分比快照。'-' 记 None，'99.25%'→99.25。"""
    df = pd.read_csv(path, skiprows=3, encoding="utf-8-sig")
    df["Object"] = df["Object"].map(_clean_obj)
    out = {}
    for _, row in df.iterrows():
        d = {}
        for col in df.columns:
            if col in ("Object", "Class"):
                continue
            v = row[col]
            s = str(v).strip()
            if s in ("-", "", "nan"):
                continue
            if s.endswith("%"):
                try:
                    d[col] = float(s[:-1])
                except ValueError:
                    pass
        out[_clean_obj(row["Object"])] = {"class": row["Class"], "pct": d}
    return out


def wip_rows(rep: pd.DataFrame) -> pd.DataFrame:
    return rep[rep["Object"].str.contains(WIP_RE, regex=False)]


def fg_rows(rep: pd.DataFrame) -> pd.DataFrame:
    return rep[rep["Object"].str.contains(FG_RE, regex=False)]


def ws_rows(rep: pd.DataFrame) -> pd.DataFrame:
    return rep[rep["Object"].str.contains(WS_RE, regex=False)]


def car_rows(rep: pd.DataFrame) -> pd.DataFrame:
    return rep[rep["Class"] == "Transporter"]
