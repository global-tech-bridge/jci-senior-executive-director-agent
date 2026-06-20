"""リッチメニュー画像生成・領域定義のユニットテスト。"""
import os

from app.member_menu import MENU_ITEMS
from app.rich_menu import (
    HEIGHT,
    WIDTH,
    generate_image,
    menu_areas,
    rich_menu_definition,
)


def test_menu_areas_grid():
    areas = menu_areas()
    assert len(areas) == 4
    # 2x2 で全面を覆う
    assert areas[0].x == 0 and areas[0].y == 0
    assert areas[1].x == WIDTH // 2
    assert areas[2].y == HEIGHT // 2


def test_areas_labels_match_member_menu():
    labels = {a.label for a in menu_areas()}
    assert labels == set(MENU_ITEMS)


def test_rich_menu_definition_postback_data():
    d = rich_menu_definition()
    assert d["size"] == {"width": WIDTH, "height": HEIGHT}
    datas = [a["action"]["data"] for a in d["areas"]]
    assert all(x.startswith("menu|") for x in datas)
    assert "menu|出欠を回答" in datas


def test_generate_image(tmp_path):
    out = str(tmp_path / "menu.png")
    generate_image(out)
    assert os.path.exists(out)
    # PNG ヘッダ
    with open(out, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"
