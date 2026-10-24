import type {
  ComponentRow,
  ExperimentBundle,
  FailureResponse,
  NetworkSummary,
  OptimizeResponse,
  SourceInfo,
  Station,
  SubnetPreview,
  SyntheticNetwork,
  SyntheticOptimizeResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";
const DATA_BASE = `${import.meta.env.BASE_URL}data`;

class ApiError extends Error {
  status: number;
  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "No se pudo contactar la API. Inicie el backend con `python -m uvicorn api.main:app --port 8000`.",
    );
  }
  if (!response.ok) {
    let detail = `Error HTTP ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

async function staticJson<T>(path: string): Promise<T> {
  const response = await fetch(`${DATA_BASE}/${path}`);
  if (!response.ok) throw new Error(`No se pudo cargar ${path}`);
  return (await response.json()) as T;
}

export const api = {
  summary: () => staticJson<NetworkSummary>("summary.json"),
  components: async (): Promise<ComponentRow[]> => {
    const payload = await staticJson<{ components: ComponentRow[] }>("components.json");
    return payload.components;
  },
  stations: () => staticJson<{ stations: Station[] }>("stations-index.json"),
  experiment: () => staticJson<ExperimentBundle>("experiment.json"),
  health: () => request<Record<string, unknown>>("/api/health"),
  subnet: (params: {
    component_index?: number | null;
    max_nodes?: number;
    departments?: string[];
    voltages?: number[];
    seed_node?: string | null;
  }) => {
    const search = new URLSearchParams();
    if (params.component_index !== undefined && params.component_index !== null) {
      search.set("component_index", String(params.component_index));
    }
    if (params.max_nodes) search.set("max_nodes", String(params.max_nodes));
    if (params.departments?.length) search.set("departments", params.departments.join(","));
    if (params.voltages?.length) search.set("voltages", params.voltages.join(","));
    if (params.seed_node) search.set("seed_node", params.seed_node);
    return request<SubnetPreview>(`/api/subnet?${search.toString()}`);
  },
  optimize: (payload: Record<string, unknown>) =>
    request<OptimizeResponse>("/api/optimize", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  failure: (payload: Record<string, unknown>) =>
    request<FailureResponse>("/api/failure", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  sources: () => request<SourceInfo>("/api/sources"),
  syntheticNetwork: (nodes = 12) =>
    request<{ network: SyntheticNetwork; nodes: number }>(`/api/synthetic/network?nodes=${nodes}`),
  syntheticOptimize: (payload: Record<string, unknown>) =>
    request<SyntheticOptimizeResponse>("/api/synthetic/optimize", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export { ApiError };
