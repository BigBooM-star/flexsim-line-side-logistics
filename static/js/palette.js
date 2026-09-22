/* 验证过的配色与图表公共配置（dataviz 技能 six-checks 全过，light 表面 #fcfcfb）。
   组配色 = Okabe-Ito 色盲安全集：组1 朱红 / 组2 蓝 / 组3 橙 / 组4 粉 / 组5.1 青绿。 */
export const GROUP_COLORS = { 1: "#D55E00", 2: "#0072B2", 3: "#E69F00", 4: "#CC79A7", "5.1": "#009E73" };
export const COST_COLORS = {
  transport: "#0072B2", inventory: "#009E73", labor: "#E69F00", stockout: "#D55E00",
};
export const COST_LABELS = { transport: "运输", inventory: "库存", labor: "人工", stockout: "缺料" };
export const INK = "#1a1a19", INK2 = "#55554f", MUTED = "#8a8a82", LINE = "#e4e4de", GRID = "#ecece7";

/* 时间热力（库存水位）用 viridis 连续色带 + 数字冗余编码 */
export const VIRIDIS = ["#440154", "#482878", "#3E4A89", "#31688E", "#26828E",
  "#1F9E89", "#35B779", "#6DCD59", "#B4DE2C", "#FDE725"];

const FONT = '12px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';

/* ECharts 公共基础配置：轴/网格/提示框统一成低调样式（dataviz marks 规范） */
export function baseOption(over = {}) {
  return Object.assign({
    textStyle: { fontSize: 12, color: INK2 },
    animationDuration: 260,
    grid: { left: 8, right: 12, top: 30, bottom: 4, containLabel: true },
    tooltip: {
      trigger: "item", confine: true, borderWidth: 0,
      backgroundColor: "rgba(26,26,25,.94)", padding: [8, 11],
      textStyle: { color: "#fff", fontSize: 12 },
    },
    legend: {
      top: 2, itemWidth: 12, itemHeight: 12, icon: "roundRect",
      textStyle: { color: INK2, fontSize: 12 },
    },
    toolbox: {
      right: 6, top: 0, itemSize: 13, iconStyle: { borderColor: MUTED },
      feature: { saveAsImage: { title: "导出PNG", backgroundColor: "#fcfcfb", pixelRatio: 2 } },
    },
  }, over);
}

export function axisStyle(name = "") {
  return {
    name, nameTextStyle: { color: MUTED, fontSize: 11 },
    axisLine: { lineStyle: { color: LINE } },
    axisTick: { show: false },
    axisLabel: { color: INK2, fontSize: 11 },
    splitLine: { lineStyle: { color: GRID, type: "solid" } },
  };
}
