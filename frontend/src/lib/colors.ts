export const VOLTAGE_COLORS: Record<string, string> = {
  "500": "#e11d48",
  "220": "#2563eb",
  "138": "#059669",
  "60": "#f59e0b",
  "50": "#d97706",
  "33": "#ca8a04",
  "30": "#a16207",
  "66": "#7c3aed",
  "69": "#8b5cf6",
  "34.5": "#0891b2",
  "44": "#0d9488",
  "72.5": "#db2777",
  "145": "#be123c",
};

export const VOLTAGE_ORDER = [500, 220, 138, 66, 60, 50, 33, 30, 145, 72.5, 69, 44, 34.5];

export function voltageColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "#64748b";
  return VOLTAGE_COLORS[String(value)] ?? "#64748b";
}

export function voltageMatchExpression(property: string) {
  const pairs: (string | number)[] = [];
  for (const [key, color] of Object.entries(VOLTAGE_COLORS)) {
    pairs.push(Number(key), color);
  }
  return ["match", ["get", property], ...pairs, "#64748b"];
}

export const STATUS_COLORS: Record<string, string> = {
  verified: "#22d3ee",
  unverified_not_found: "#94a3b8",
  unverified_far_from_geometry: "#a8a29e",
  unverified_missing: "#cbd5e1",
  unverified_ambiguous: "#fbbf24",
  invalid_self_loop: "#fb7185",
};

export const STATUS_LABELS: Record<string, string> = {
  verified: "Verificada",
  unverified_not_found: "No encontrada",
  unverified_far_from_geometry: "Lejos de geometría",
  unverified_missing: "Extremos faltantes",
  unverified_ambiguous: "Ambigua",
  invalid_self_loop: "Bucle propio",
};
