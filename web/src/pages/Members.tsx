import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Card } from "../components/Card";

type Row = {
  member_id: string;
  name: string;
  committee: string | null;
  officer_role: string | null;
  member_type: string;
  linked: boolean;
  invite_issued: boolean;
  invite_active: boolean;
  invite_used: boolean;
};

type History = {
  name: string;
  counted: number;
  present: number;
  answered: number;
  attendance_rate: number;
  items: { event_id: string; title: string; datetime_start: string; status: string }[];
};

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full ${
        ok ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"
      }`}
    >
      {label}
    </span>
  );
}

export default function Members() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [hist, setHist] = useState<History | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () =>
    api<Row[]>("/members/invite-status").then(setRows).catch((e) => setErr(e.message));

  useEffect(() => {
    load();
  }, []);

  async function issueInvite(id: string) {
    try {
      const r = await api<{ code: string }>(`/members/${id}/invite`, { method: "POST" });
      setMsg(`招待コードを発行: ${r.code}`);
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function showHistory(id: string) {
    try {
      setHist(await api<History>(`/members/${id}/attendance-history`));
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  if (err) return <Card title="会員管理"><p className="text-red-600 text-sm">{err}</p></Card>;

  return (
    <div>
      <h1 className="text-lg font-semibold text-navy mb-3">会員管理</h1>
      {msg && <div className="mb-2 text-sm text-brand">{msg}</div>}

      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="py-1">氏名</th>
              <th>委員会/役職</th>
              <th>LINE連携</th>
              <th>招待コード</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.member_id} className="border-t">
                <td className="py-1">{r.name}</td>
                <td className="text-slate-500">{r.officer_role || r.committee || "-"}</td>
                <td><Badge ok={r.linked} label={r.linked ? "連携済" : "未連携"} /></td>
                <td>
                  {r.invite_used ? (
                    <Badge ok label="使用済" />
                  ) : r.invite_active ? (
                    <Badge ok label="発行済(有効)" />
                  ) : (
                    <Badge ok={false} label="未発行" />
                  )}
                </td>
                <td className="space-x-2 whitespace-nowrap">
                  {!r.linked && (
                    <button
                      className="text-xs bg-brand text-white rounded px-2 py-1"
                      onClick={() => issueInvite(r.member_id)}
                    >
                      招待発行
                    </button>
                  )}
                  <button
                    className="text-xs bg-slate-200 text-navy rounded px-2 py-1"
                    onClick={() => showHistory(r.member_id)}
                  >
                    出欠履歴
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="text-slate-500 text-sm">会員がいません。</p>}
      </Card>

      {hist && (
        <Card title={`出欠履歴: ${hist.name}`}>
          <p className="text-sm mb-2">
            出席率 <b>{Math.round(hist.attendance_rate * 100)}%</b>（出席 {hist.present} /
            対象 {hist.counted}、回答 {hist.answered}）
            <button className="ml-3 text-xs text-slate-500 underline" onClick={() => setHist(null)}>
              閉じる
            </button>
          </p>
          <table className="w-full text-sm">
            <tbody>
              {hist.items.map((it) => (
                <tr key={it.event_id} className="border-t">
                  <td className="py-1">{it.datetime_start.slice(0, 10)}</td>
                  <td>{it.title}</td>
                  <td className="font-semibold">{it.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
