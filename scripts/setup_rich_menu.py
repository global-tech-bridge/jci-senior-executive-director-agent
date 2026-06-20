#!/usr/bin/env python3
"""リッチメニューを生成して LINE に登録し、デフォルトに設定する。

使い方:
  LINE_CHANNEL_ACCESS_TOKEN=... python scripts/setup_rich_menu.py
  python scripts/setup_rich_menu.py --image-only out.png   # 画像生成のみ(登録しない)

登録は LINE Messaging API を直接叩く（line-bot-sdk のバージョン差異を避けるため requests）。
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, ".")

from app import config  # noqa: E402
from app.rich_menu import generate_image, rich_menu_definition  # noqa: E402

API = "https://api.line.me"
DATA_API = "https://api-data.line.me"


def _req(url: str, token: str, *, method: str, data: bytes | None = None, content_type: str):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if content_type:
        req.add_header("Content-Type", content_type)
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read().decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-only", metavar="PATH", default=None)
    args = ap.parse_args()

    if args.image_only:
        print("生成:", generate_image(args.image_only))
        return 0

    token = config.line_channel_access_token()
    if not token or token == "PLACEHOLDER_SET_ME":
        print("ERROR: LINE_CHANNEL_ACCESS_TOKEN が未設定です。", file=sys.stderr)
        return 1

    image_path = "/tmp/jci_rich_menu.png"
    generate_image(image_path)

    # 1) リッチメニュー作成
    definition = json.dumps(rich_menu_definition()).encode()
    status, body = _req(
        f"{API}/v2/bot/richmenu", token, method="POST",
        data=definition, content_type="application/json",
    )
    rich_menu_id = json.loads(body)["richMenuId"]
    print(f"作成: {rich_menu_id} (HTTP {status})")

    # 2) 画像アップロード
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    status, _ = _req(
        f"{DATA_API}/v2/bot/richmenu/{rich_menu_id}/content", token, method="POST",
        data=img_bytes, content_type="image/png",
    )
    print(f"画像アップロード: HTTP {status}")

    # 3) デフォルト設定（全ユーザー）
    status, _ = _req(
        f"{API}/v2/bot/user/all/richmenu/{rich_menu_id}", token, method="POST",
        data=None, content_type="",
    )
    print(f"デフォルト設定: HTTP {status}")
    print("完了。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
