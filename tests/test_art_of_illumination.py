"""光影栖身处刮卡：扫描判据的纯逻辑测试 + 素材/出处对账。

判据是**相对**的（未开格彼此幅度一致、已翻开的恒为 0），这里把实测踩过的坑钉住：
固定阈值时代，一次 3.0 的瞬态被当成未开格，于是点了已翻开的格子 → 弹详情面板 → 管线没有出口。
"""

import re
from pathlib import Path

import numpy as np
import pytest

from agent.custom.action.art_of_illumination import FINISH_NODE, SWITCH_NODE, ArtOfIlluminationScratch


def _motion(fill: float = 0.0) -> np.ndarray:
    """6×6 的逐格帧间差矩阵；缺省全 0（= 格子全翻开，或次数归零后动画停了）。"""
    return np.full((6, 6), fill, dtype=np.float64)


def test_no_motion_yields_no_unopened() -> None:
    """全静止：要么全翻开了、要么次数归零动画停了——两种都不该点任何格子。"""
    assert ArtOfIlluminationScratch._unopened(_motion()) == []


def test_peak_below_floor_is_treated_as_no_measurement() -> None:
    """基准太小说明这一测不可信（两帧实际挨得太近），宁可报 0 也不要瞎点。"""
    weak = _motion(ArtOfIlluminationScratch.MOTION_PEAK_FLOOR - 0.1)
    assert ArtOfIlluminationScratch._unopened(weak) == []


def test_covered_cells_are_returned_row_major_with_controller_coords() -> None:
    motion = _motion()
    motion[0, 5] = 27.0  # 第 1 行第 6 列
    motion[1, 0] = 23.6  # 第 2 行第 1 列
    cells = ArtOfIlluminationScratch._unopened(motion)
    assert cells == [
        (1, 6, ArtOfIlluminationScratch.COL_X[5], ArtOfIlluminationScratch.ROW_Y[0]),
        (2, 1, ArtOfIlluminationScratch.COL_X[0], ArtOfIlluminationScratch.ROW_Y[1]),
    ]


def test_low_transient_on_a_revealed_cell_is_not_picked() -> None:
    """回归实测现场：未开格幅度 ~24.8，而已翻开的 (1,6) 抖出 3.0。

    固定阈值 1.0 时它被判成未开格，于是点了已翻开的格子、弹出详情面板而管线没有出口。
    相对判据（峰值 × 0.25 ≈ 6.2）下它落在分界之下，被正确排除。
    """
    motion = _motion()
    motion[0, 5] = 3.0  # 已翻开的格子抖了一下
    motion[1, 5] = 24.88  # 真正未开
    motion[2, 4] = 22.77
    assert [cell[:2] for cell in ArtOfIlluminationScratch._unopened(motion)] == [(2, 6), (3, 5)]


def test_cutoff_scales_with_the_measured_amplitude() -> None:
    """同一块棋盘换两帧间隔，幅度整体差一个数量级也要照样分对（相对判据的意义所在）。"""
    for peak in (8.0, 25.0):
        motion = _motion(peak * 0.9)  # 未开格幅度一致
        assert len(ArtOfIlluminationScratch._unopened(motion)) == 36
        motion[5, 5] = 0.0  # 一个已翻开
        assert len(ArtOfIlluminationScratch._unopened(motion)) == 35


def test_pick_is_random_over_the_unopened_cells() -> None:
    """翻哪一格是**随机**的：既不能跳出候选集合，也不能恒取行优先的第一个。"""
    cells = [(1, 1, 168, 162), (1, 2, 261, 162), (2, 1, 168, 247), (2, 2, 261, 247)]
    picks = {ArtOfIlluminationScratch._pick(cells) for _ in range(300)}
    assert picks <= set(cells)
    assert len(picks) > 1, "300 次抽样只出现同一个格子，说明还是行优先取第一个"


# ------------------------------------------------------------------ 翻幕布的分支


class _FakeContext:
    """只记 override_next 的最小替身（本模块只用到这一个 context 能力）。"""

    def __init__(self) -> None:
        self.overrides: list[tuple[str, list[str]]] = []

    def override_next(self, node_name: str, next_list: list[str]) -> None:
        self.overrides.append((node_name, next_list))


def _stub_round(monkeypatch: pytest.MonkeyPatch, counter: int | None) -> _FakeContext:
    """把「扫两帧」与「读计数条」换成替身：棋盘全静止（= 本页已翻完）、计数条读指定值。"""
    monkeypatch.setattr(
        ArtOfIlluminationScratch,
        "_scan",
        classmethod(lambda cls, context, gap: (np.zeros((6, 6), dtype=np.float64), None)),
    )
    monkeypatch.setattr(
        ArtOfIlluminationScratch,
        "_read_counter",
        classmethod(lambda cls, context, img: counter),
    )
    return _FakeContext()


def test_page_finished_with_refractions_left_switches_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """本页翻完、计数条还有次数 → 覆写到 AOI_PageSwitch 去翻另一幕布，而不是直接收尾。"""
    context = _stub_round(monkeypatch, counter=2)
    assert ArtOfIlluminationScratch._round(context, "AOI_FlipRound") is True  # pyright: ignore[reportArgumentType]
    assert context.overrides == [("AOI_FlipRound", [SWITCH_NODE])]


def test_page_finished_without_refractions_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    """次数为 0：不翻页，直接收尾（次数归零后动画会停，此处的「未开 0 格」不代表翻完了）。"""
    context = _stub_round(monkeypatch, counter=0)
    assert ArtOfIlluminationScratch._round(context, "AOI_FlipRound") is True  # pyright: ignore[reportArgumentType]
    assert context.overrides == [("AOI_FlipRound", [FINISH_NODE])]


# ------------------------------------------------------------------ 素材对账

_AOI_PIPELINE = Path("resource/base/pipeline/activity/ArtOfIllumination.json")
_PACK_IMAGE = Path("resource/base/image")


def test_pipeline_templates_all_exist() -> None:
    """pipeline 里引用到的本模块模板，文件都得在。

    模板路径是**运行期**解析的：写错或改名不会在加载期报错，只会在跑的时候「模板懒加载缺图」，
    所以拿一条用例把它钉住。
    """
    repo = Path(__file__).resolve().parents[1]
    pipeline = (repo / _AOI_PIPELINE).read_text(encoding="utf-8")
    refs = sorted(set(re.findall(r'"(ArtOfIllumination/[A-Za-z0-9_]+\.png)"', pipeline)))
    assert refs, "pipeline 里应当引用到本模块的模板"
    missing = [ref for ref in refs if not (repo / _PACK_IMAGE / ref).is_file()]
    assert missing == [], f"模板文件缺失：{missing}"
