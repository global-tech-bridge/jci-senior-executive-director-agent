import type { ReactNode } from "react";

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="bg-white rounded-lg shadow-sm p-4 mb-3">
      {title && <h2 className="text-sm font-semibold text-navy mb-2">{title}</h2>}
      {children}
    </div>
  );
}
