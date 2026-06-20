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
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Response
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    Message,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    FollowEvent,
    MessageEvent,
    PostbackEvent,
    TextMessageContent,
)

from . import config
from .invite import verify_and_link
from .line_messages import apply_postback
from .repository import Repository

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


_repo: Repository | None = None


def get_repo() -> Repository:
    """リポジトリを取得（本番=Firestore）。テストでは monkeypatch する。"""
    global _repo
    if _repo is None:
        from .firestore_repo import FirestoreRepository

        _repo = FirestoreRepository(project=config.PROJECT_ID)
    return _repo


def _access_token_ready(token: str | None) -> bool:
    return bool(token and token != "PLACEHOLDER_SET_ME")


def reply_messages(reply_token: str, messages: list[Message]) -> bool:
    """LINE へ任意のメッセージ列を返信。アクセストークン未設定時はスキップ。"""
    token = config.line_channel_access_token()
    if not _access_token_ready(token):
        logger.warning("access token 未設定のため返信スキップ (%d件)", len(messages))
        return False
    configuration = Configuration(access_token=token)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=messages)
        )
    return True


def reply(reply_token: str, text: str) -> bool:
    """テキスト1通を返信するショートカット。"""
    return reply_messages(reply_token, [TextMessage(text=text)])


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


def handle_text_message(user_id: str, text: str) -> str:
    """テキストメッセージへの応答文を生成。

    未連携ユーザーからのメッセージは招待コードとして照合し本人確認を行う。
    連携済みユーザーへの応答は後続マイルストーン（出欠等）で拡張する。
    """
    repo = get_repo()
    member = repo.get_member_by_line_user_id(user_id)
    if member is None:
        result = verify_and_link(repo, user_id, text, now=datetime.now())
        return result.message
    return f"{member.name}さん、受信しました（疎通確認）: {text}"


def handle_event(event) -> None:
    """単一の LINE イベントを処理する。"""
    if isinstance(event, FollowEvent):
        logger.info("follow event: userId=%s", event.source.user_id)
        reply(event.reply_token, WELCOME_TEXT)
    elif isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
        user_id = event.source.user_id
        text = event.message.text
        logger.info("message event: userId=%s text=%s", user_id, text)
        reply(event.reply_token, handle_text_message(user_id, text))
    elif isinstance(event, PostbackEvent):
        user_id = event.source.user_id
        data = event.postback.data
        logger.info("postback event: userId=%s data=%s", user_id, data)
        messages = handle_postback(user_id, data)
        reply_messages(event.reply_token, messages)
    else:
        logger.info("other event: %s", type(event).__name__)


def handle_postback(user_id: str, data: str) -> list[Message]:
    """postback（出欠ボタン等）を処理してメッセージ列を返す。"""
    repo = get_repo()
    member = repo.get_member_by_line_user_id(user_id)
    if member is None:
        return [TextMessage(text="先に招待コードで登録をお願いします。")]
    return apply_postback(repo, member, data, now=datetime.now())


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
