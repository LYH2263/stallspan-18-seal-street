"""可分配时段（窗）判定 —— 全应用唯一口径。

集日页展示、确认入口、试摆入口、运行条数页都必须走这里，
不得各自再算一遍，口径分叉即废。

窗用开/收市两个墙钟表示：window_start <= t < window_end 为窗内；
window_start == window_end 视为闭窗（无可分配时段）。
跨零点（start > end，如 20:00–02:00）按环绕处理。
"""
from __future__ import annotations

from datetime import time

# 测试可直接替换以模拟“现在”；生产留空取系统墙钟。
_clock_override: time | None = None


def set_now(t: time | None) -> None:
    """注入当前墙钟（仅供测试/夹具）。传 None 恢复系统时间。"""
    global _clock_override
    _clock_override = t


def now() -> time:
    return _clock_override if _clock_override is not None else time()


def in_window(window_start: time, window_end: time, at: time | None = None) -> bool:
    """当前（或指定）墙钟是否落在可分配时段内。端点：含起点、不含终点。"""
    if at is None:
        at = now()
    if window_start == window_end:
        return False
    if window_start < window_end:
        return window_start <= at < window_end
    # 跨零点
    return at >= window_start or at < window_end


def window_message(market_day) -> str:
    return (
        f"当前时刻 {now().strftime('%H:%M')} 不在集日「{market_day.name}」"
        f"的可分配时段 {market_day.window_start.strftime('%H:%M')}–"
        f"{market_day.window_end.strftime('%H:%M')} 内，确认与试摆均关闭"
    )
