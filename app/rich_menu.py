"""リッチメニューの画像生成と領域定義（docs/mvp-design.md §4.3）。

2x2 グリッドの常時表示メニュー。各領域タップで postback "menu|<label>" を送り、
member_menu のルーティングに合流する。LINE Messaging API への登録は
scripts/setup_rich_menu.py が行う（本モジュールは生成と定義のみ）。
"""
from __future__ import annotations

from dataclasses import dataclass

from .member_menu import MENU_ANSWER, MENU_CONTACT, MENU_MY_ATT, MENU_SCHEDULE

# LINE リッチメニュー大サイズ
WIDTH = 2500
HEIGHT = 1686

# 2x2 の各セル: (label, 表示テキスト)
CELLS = [
    (MENU_ANSWER, "出欠を回答"),
    (MENU_SCHEDULE, "次回の予定"),
    (MENU_MY_ATT, "自分の出欠状況"),
    (MENU_CONTACT, "事務局に連絡"),
]

# 背景色（落ち着いた紺～青のトーン）
CELL_COLORS = ["#1f3a5f", "#2e5a88", "#2e5a88", "#1f3a5f"]


@dataclass
class MenuArea:
    x: int
    y: int
    width: int
    height: int
    label: str  # postback の menu|<label>


def menu_areas() -> list[MenuArea]:
    """2x2 グリッドのタップ領域を返す。"""
    cw, ch = WIDTH // 2, HEIGHT // 2
    areas = []
    for idx, (label, _text) in enumerate(CELLS):
        col, row = idx % 2, idx // 2
        areas.append(MenuArea(x=col * cw, y=row * ch, width=cw, height=ch, label=label))
    return areas


def rich_menu_definition(name: str = "jci-default") -> dict:
    """LINE Rich Menu 作成用の JSON 定義を返す。"""
    return {
        "size": {"width": WIDTH, "height": HEIGHT},
        "selected": True,
        "name": name,
        "chatBarText": "メニュー",
        "areas": [
            {
                "bounds": {"x": a.x, "y": a.y, "width": a.width, "height": a.height},
                "action": {"type": "postback", "data": f"menu|{a.label}", "displayText": a.label},
            }
            for a in menu_areas()
        ],
    }


def _load_font(size: int):
    from PIL import ImageFont

    # 日本語フォント候補（環境により存在するものを使う）
    candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def generate_image(path: str) -> str:
    """リッチメニュー画像を生成して保存し、パスを返す。"""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (WIDTH, HEIGHT), "#1f3a5f")
    draw = ImageDraw.Draw(img)
    font = _load_font(110)
    areas = menu_areas()

    for area, color, (_label, text) in zip(areas, CELL_COLORS, CELLS, strict=True):
        # セル背景（境界を少し空けてタイル状に）
        m = 12
        draw.rectangle(
            [area.x + m, area.y + m, area.x + area.width - m, area.y + area.height - m],
            fill=color,
        )
        # 中央にテキスト
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx = area.x + area.width // 2 - tw // 2
        cy = area.y + area.height // 2 - th // 2
        draw.text((cx, cy), text, fill="#ffffff", font=font)

    img.save(path, "PNG")
    return path
