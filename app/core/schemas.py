"""pydantic 请求/响应模型 —— API 契约的唯一来源。"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Strategy = Literal["pull", "timer", "threshold"]


class EstimateReq(BaseModel):
    strategy: Strategy = "threshold"
    ss: float = Field(1.0, ge=0, le=10)
    target: float = Field(3, ge=1, le=12)
    cap: float = Field(6, ge=1, le=12)
    check_period: float = Field(3600, ge=300, le=7200)
    cart_cap: float = Field(12, ge=1, le=24)
    cars: int = Field(2, ge=1, le=4)
    hours: float = Field(118.0, gt=0, le=120)

    @field_validator("target")
    @classmethod
    def _target_ge_ss(cls, v, info):
        if "ss" in info.data and v < info.data["ss"]:
            raise ValueError("补货目标 target 不能低于安全库存 ss")
        return v


class SimRunReq(EstimateReq):
    seed: int = 7
    run_sim: bool = True          # false 时只回解析结果


class CostCoefficients(BaseModel):
    c_d_per_leg: float = Field(ge=0, le=100000)
    h_per_unit_hour: float = Field(ge=0, le=100000)
    c_labor_per_shift_hour: float = Field(ge=0, le=100000)
    c_stop_per_minute: float = Field(ge=0, le=1000000)


class CostQuantities(BaseModel):
    labor_person_hours: float = Field(ge=0, le=1000000)
    cost_window_hours: float = Field(ge=1, le=720)


class CostBasisPut(BaseModel):
    preset: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=60)
    currency: str = Field(min_length=1, max_length=12)
    disclaimer: str = Field(default="", max_length=500)
    coefficients: CostCoefficients
    quantities: CostQuantities


class SSTableRow(BaseModel):
    hour: int = Field(ge=0, le=120)
    value: float = Field(ge=0, le=10)
