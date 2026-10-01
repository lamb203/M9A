"""SwitchAccountSelect 纯函数单测。

覆盖：目标账号匹配（可见片段 / 完整手机号 / 未命中）、文本归一化、页签名与行坐标推导。
"""

from agent.custom.action.switch_account import SwitchAccountSelect, _AccountRow

_ACTION = SwitchAccountSelect()


def test_match_target_accepts_masked_text_fragments() -> None:
    assert _ACTION._match_target("1896002", "1896002")
    assert _ACTION._match_target("189", "1896002")
    assert _ACTION._match_target("6002", "1896002")


def test_match_target_accepts_full_phone_number() -> None:
    assert _ACTION._match_target("18912346002", "1896002")


def test_match_target_rejects_invisible_or_mismatched_input() -> None:
    # 掩码遮住的中间 4 位无法作为查找依据
    assert not _ACTION._match_target("1234", "1896002")
    assert not _ACTION._match_target("1891234600", "1896002")
    assert not _ACTION._match_target("", "1896002")
    assert not _ACTION._match_target("18912346002", "")


def test_normalize_text_keeps_digits_only() -> None:
    assert _ACTION._normalize_text("189****6002") == "1896002"
    assert _ACTION._normalize_text(" 18 9*6002 ") == "1896002"
    assert _ACTION._normalize_text("") == ""


def test_page_signature_drops_empty_texts() -> None:
    rows = [
        _AccountRow(box=(0, 0, 10, 10), text="189****6002", normalized_text="1896002"),
        _AccountRow(box=(0, 20, 10, 10), text="", normalized_text=""),
    ]

    assert _ACTION._page_signature(rows) == ("1896002",)


def test_account_row_center_is_box_middle() -> None:
    row = _AccountRow(box=(10, 20, 101, 31), text="", normalized_text="")

    assert row.center == (60, 35)
