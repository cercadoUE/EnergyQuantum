export const nf = new Intl.NumberFormat("es-PE");
export const nf1 = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 1 });
export const nf2 = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const nf4 = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 4, maximumFractionDigits: 4 });

export function int(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return nf.format(value);
}

export function km(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${nf1.format(value)} km`;
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function seconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value < 1) return `${(value * 1000).toFixed(0)} ms`;
  return `${value.toFixed(2)} s`;
}

export function kv(value: number | null | undefined): string {
  if (value === null || value === undefined) return "s/t";
  return `${nf1.format(value)} kV`;
}

export function dateLabel(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("es-PE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

export function dateTimeLabel(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("es-PE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export function fileStem(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function downloadText(filename: string, text: string, mime = "application/json") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function downloadJson(filename: string, payload: unknown) {
  downloadText(filename, JSON.stringify(payload, null, 2));
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const escape = (value: unknown) => {
    const text = value === null || value === undefined ? "" : String(value);
    return `"${text.replace(/"/g, '""')}"`;
  };
  const csv = [headers.join(","), ...rows.map((row) => headers.map((key) => escape(row[key])).join(","))].join("\n");
  downloadText(filename, csv, "text/csv;charset=utf-8");
}
