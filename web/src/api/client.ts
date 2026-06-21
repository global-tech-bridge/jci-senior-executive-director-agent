// 管理API クライアント。IAP 配下では Cookie 認証のため credentials を含める。
// ローカル開発では Vite プロキシ経由で FastAPI に届く。

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opts.headers ?? {}) },
    ...opts,
  });
  if (res.status === 401) {
    throw new Error("認証エラー: アクセス権を確認してください。");
  }
  if (!res.ok) {
    throw new Error(`APIエラー (${res.status})`);
  }
  return res.json() as Promise<T>;
}
