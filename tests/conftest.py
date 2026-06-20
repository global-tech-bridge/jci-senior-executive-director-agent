"""テスト共通設定。

アプリ import 前に LINE シークレットを環境変数で固定し、
Secret Manager への実アクセスを避ける。
"""
import os

os.environ.setdefault("LINE_CHANNEL_SECRET", "test_channel_secret")
os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "PLACEHOLDER_SET_ME")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("ADMIN_API_SECRET", "test-admin-secret")

TEST_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
ADMIN_AUTH = {"Authorization": f"Bearer {os.environ['ADMIN_API_SECRET']}"}
