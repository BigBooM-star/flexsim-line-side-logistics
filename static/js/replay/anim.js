/* 回放时间轴工具：车腿二分查找与位置插值 */

/* 在 legs（按 t0 升序）中找 t 所在/最近的一段索引 */
export function legIndexAt(legs, t) {
  let lo = 0, hi = legs.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (legs[mid][0] <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return ans;
}

/* 返回 {x,y,loaded,active}；active=false 表示车在等待（停在上一段终点） */
export function carPosAt(legs, t) {
  if (!legs.length) return null;
  const i = legIndexAt(legs, t);
  if (i < 0) {
    const [x0, y0] = [legs[0][2], legs[0][3]];
    return { x: x0, y: y0, loaded: false, active: false };
  }
  const L = legs[i];
  if (t >= L[1]) {
    if (i === legs.length - 1) return { x: L[4], y: L[5], loaded: false, active: false };
    const N = legs[i + 1];
    return { x: N[2], y: N[3], loaded: false, active: false };
  }
  const f = (t - L[0]) / Math.max(0.001, L[1] - L[0]);
  return {
    x: L[2] + (L[4] - L[2]) * f,
    y: L[3] + (L[5] - L[3]) * f,
    loaded: !!L[6], active: true,
  };
}

/* 统计截至 t 的完成腿数 / 重驶腿数 */
export function legsDone(legs, t) {
  const i = legIndexAt(legs, t);
  if (i < 0) return [0, 0];
  let loaded = 0;
  for (let j = 0; j < i; j++) if (legs[j][6]) loaded++;
  return [i, loaded];
}
