"""JCI 専務理事エージェント — M0: LINE Webhook 疎通 PoC.

エンドポイント:
- GET  /              : 稼働確認
- GET  /healthz       : ヘルスチェック（Cloud Run用）
- POST /line/webhook  : LINE Messaging API の Webhook 受信
    - 署名検証（channel secret）
    - follow（友だち追加）→ 歓迎メッセージ
    - message（テキスト）→ オウム返し（疎通確認用）

設計方針:
- シークレットは関数経由で遅延解決（テスト時に環境変数で差し替え可能）。
- チャネルアクセストークン未設定でも Webhook は 200 を返し受信ログを残す（返信のみスキップ）。
"""
import logging

from fastapi import FastAPI, HTTPException, Request, Response
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent

from . import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jci-agent")

app = FastAPI(title="JCI SED Agent", version="0.0.1-m0")

WELCOME_TEXT = (
    "友だち追加ありがとうございます！\n"
    "猪苗代JC 専務理事エージェントです。\n"
    "登録のため、事務局から配布された招待コードを入力してください。"
)


def get_parser() -> WebhookParser | None:
    """channel secret から Webhook パーサを構築（未設定なら None）。"""
    secret = config.line_channel_secret()
    return WebhookParser(secret) if secret else None


def _access_token_ready(token: str | None) -> bool:
    return bool(token and token != "PLACEHOLDER_SET_ME")


def reply(reply_token: str, text: str) -> bool:
    """LINE へ返信。アクセストークン未設定時はスキップして False を返す。"""
    token = config.line_channel_access_token()
    if not _access_token_ready(token):
        logger.warning("access token 未設定のため返信スキップ: %s", text)
        return False
    configuration = Configuration(access_token=token)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )
    return True


@app.get("/")
def root():
    return {"service": "jci-sed-agent", "stage": "M0", "status": "ok"}


@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "channel_secret_loaded": bool(config.line_channel_secret()),
        "access_token_loaded": _access_token_ready(config.line_channel_access_token()),
    }


def handle_event(event) -> None:
    """単一の LINE イベントを処理する。"""
    if isinstance(event, FollowEvent):
        logger.info("follow event: userId=%s", event.source.user_id)
        reply(event.reply_token, WELCOME_TEXT)
    elif isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
        text = event.message.text
        logger.info("message event: userId=%s text=%s", event.source.user_id, text)
        reply(event.reply_token, f"受信しました（疎通確認）: {text}")
    else:
        logger.info("other event: %s", type(event).__name__)


@app.post("/line/webhook")
async def line_webhook(request: Request):
    parser = get_parser()
    if parser is None:
        logger.error("channel secret 未設定。Webhook を処理できません。")
        raise HTTPException(status_code=503, detail="channel secret not configured")

    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError as exc:
        logger.warning("署名検証に失敗しました。")
        raise HTTPException(status_code=400, detail="invalid signature") from exc

    for event in events:
        handle_event(event)

    # LINE には常に 200 を返す（個別失敗は内部でログ化）
    return Response(status_code=200)
