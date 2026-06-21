"""Vertex AI Gemini による議案の内容レビュー（F6-5, docs/dashboard-design.md §6）。

- 本番は Vertex AI の Gemini を呼ぶ。
- 認証/ライブラリ未設定や呼び出し失敗時は graceful degrade（reviewed=False を返す）。
- テストでは `generate_review_json` をモックする。

レビューは「助言」であり最終判断は人間（専務理事）が行う（F6-8）。
"""
from __future__ import annotations

import json
import logging

from . import config
from .models import LlmReview

logger = logging.getLogger("jci-agent.llm")

DEFAULT_MODEL = "gemini-2.5-pro"

_PROMPT = """あなたは青年会議所(JC)の専務理事を補佐するアシスタントです。
次の議案(事業計画書)の内容をレビューし、JSONで出力してください。
出力フィールド:
- summary: 議案の3行以内の要約
- points: 審議のポイント(論点)の配列(最大5件)
- concerns: 曖昧・矛盾・記載不足など要確認点の配列(最大5件)
助言が目的で最終判断は人間が行います。事実を断定しすぎないでください。

# 議案本文
{content}

# 出力(JSONのみ)
"""


def _model_name() -> str:
    import os

    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def generate_review_json(content: str, *, model: str, project: str, location: str) -> str:
    """Vertex AI Gemini を呼んで JSON 文字列を返す（テストでモックする境界）。"""
    import vertexai
    from vertexai.generative_models import GenerativeModel

    vertexai.init(project=project, location=location)
    gm = GenerativeModel(model)
    resp = gm.generate_content(
        _PROMPT.format(content=content),
        generation_config={"response_mime_type": "application/json"},
    )
    return resp.text


def review_proposal(content: str) -> LlmReview | None:
    """議案本文をレビューして LlmReview を返す。失敗時は None。"""
    if not content or not content.strip():
        return None
    import os

    model = _model_name()
    project = config.PROJECT_ID
    location = os.environ.get("VERTEX_AI_LOCATION", "asia-northeast1")
    try:
        raw = generate_review_json(content, model=model, project=project, location=location)
        data = json.loads(raw)
        return LlmReview(
            summary=str(data.get("summary", "")).strip(),
            points=[str(x) for x in data.get("points", [])][:5],
            concerns=[str(x) for x in data.get("concerns", [])][:5],
            model=model,
        )
    except Exception:  # noqa: BLE001 - LLM未設定/失敗でも本処理は止めない
        logger.exception("LLMレビューに失敗しました")
        return None
