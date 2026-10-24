export type Tone = "cyan" | "blue" | "green" | "amber" | "rose" | "violet" | "slate";

export interface LayerTarget {
  layer_id?: number;
  name?: string;
  role?: string;
  geometry_type?: string;
  voltage_kv?: number | null;
}

export interface SourceBrief {
  institution: string;
  service?: string;
  downloaded_at_utc?: string;
  provenance?: string;
  classification_note?: string;
  layers?: LayerTarget[];
}

export interface QualityBrief {
  nodes_total?: number;
  nodes_in_verified_graph?: number;
  nodes_isolated?: number;
  edges_verified?: number;
  lines_total?: number;
  lines_verified?: number;
  lines_unverified?: number;
  components_verified?: number;
  components_with_edges?: number;
  largest_component_nodes?: number;
  largest_component_edges?: number;
  bridges?: number;
  cycle_basis_size?: number;
  [key: string]: unknown;
}

export interface ComponentRow {
  index: number;
  label: string;
  nodes: number;
  edges: number;
  total_length_km: number;
  departments: string[];
  voltages_kv: number[];
  node_ids: string[];
  sample_names: string[];
}

export interface Station {
  id: string;
  name: string;
  voltage_kv: number | null;
  department: string | null;
  company?: string | null;
  degree?: number;
  lon: number;
  lat: number;
}

export interface TopStation extends Station {
  degree: number;
}

export interface NetworkSummary {
  generated_at_utc?: string;
  source: SourceBrief;
  metadata: Record<string, string>;
  quality: QualityBrief;
  counts: {
    stations: number;
    stations_in_verified_graph: number;
    lines: number;
    lines_verified: number;
    lines_unverified: number;
    edges: number;
    components_with_edges: number;
    generation: number;
    coes_validated_edges: number;
  };
  voltage_counts: {
    stations: Record<string, number>;
    edges: Record<string, number>;
    lines: Record<string, number>;
  };
  department_counts: Record<string, number>;
  line_status_counts: Record<string, number>;
  components: ComponentRow[];
  top_stations: TopStation[];
  availability: Record<string, { available: boolean; largest_component: number; message: string }>;
}

export interface SubnetNode {
  id: string;
  name: string;
  lon: number;
  lat: number;
  voltage_kv: number | null;
  department: string | null;
  company?: string | null;
  capacity_mva?: number | null;
  operational?: boolean;
  verified_degree?: number;
  selection_role?: string;
  [key: string]: unknown;
}

export interface SubnetEdge {
  id: string;
  source: string;
  target: string;
  source_name: string;
  target_name: string;
  length_km: number;
  voltage_kv: number | null;
  line_ids: string[];
  line_names: string[];
  line_count: number;
  parallel: boolean;
  available: boolean;
  failed: boolean;
  geometry?: { type: string; coordinates: unknown };
  validation?: string;
  coes_validated?: boolean;
  [key: string]: unknown;
}

export interface SubnetStats {
  nodes: number;
  edges: number;
  total_length_km: number;
  voltages_kv: number[];
  departments: string[];
  components: number;
  bridges: string[][];
  cycle_basis_size: number;
}

export interface Subnet {
  schema_version?: number;
  created_at_utc?: string;
  nodes: SubnetNode[];
  edges: SubnetEdge[];
  selection: {
    actual_nodes: number;
    max_nodes: number;
    component_index: number | null;
    seed_node: string | null;
    truncated: boolean;
    pool_nodes: number;
    message: string;
    [key: string]: unknown;
  };
  stats: SubnetStats;
}

export interface Partition {
  assignment: Record<string, number>;
  groups: { A: string[]; B: string[] };
}

export interface RunResult {
  method: string;
  objective: number | null;
  cut: number | null;
  balance?: number | null;
  imbalance?: number | null;
  seconds: number;
  evaluations?: number;
  bits: number[] | null;
  status?: string;
  feasible?: boolean;
  validation?: Record<string, unknown>;
  partition?: Partition | null;
  p?: number;
  qubits?: number;
  depth?: number;
  shots?: number;
  optimizer?: string;
  feasible_fraction?: number;
  sampled_expected?: number;
  expected?: number;
  trace?: number[];
  counts?: Record<string, number>;
  parameters?: number[];
  message?: string;
  converged?: boolean;
  gates?: Record<string, number>;
  [key: string]: unknown;
}

export interface OptimizeResponse {
  subnet: Subnet;
  instance: Record<string, unknown>;
  id_map: Record<string, number>;
  objective: { alpha: number; beta: number };
  config: Record<string, unknown>;
  runs: Record<string, RunResult>;
  metrics: FailureMetrics;
  bridge_edges: BridgeEdge[];
  elapsed_seconds: number;
}

export interface BridgeEdge {
  id: string;
  source: string;
  target: string;
  source_name: string;
  target_name: string;
  length_km: number;
  voltage_kv: number | null;
}

export interface FailureMetrics {
  nodes: number;
  edges_configured: number;
  edges_active: number;
  edges_failed: number;
  failed_edge_ids: string[];
  components: number;
  largest_component: number;
  isolated_nodes: number;
  total_length_km_configured: number;
  total_length_km_active: number;
  bridges: string[][];
  articulation_points: string[];
  served_demand: number | null;
  lost_demand: number | null;
  note: string;
  computed_at_utc: string;
}

export interface FailureComparison {
  before: Record<string, number | null>;
  after: Record<string, number | null>;
  delta: Record<string, number | null>;
  note: string;
}

export interface FailureResponse {
  subnet: Subnet;
  failed_subnet: Subnet;
  before: FailureMetrics;
  after: FailureMetrics;
  comparison: FailureComparison;
  failed_edges: SubnetEdge[];
  bridge_edges: BridgeEdge[];
}

export interface SubnetPreview {
  subnet: Subnet;
  metrics: FailureMetrics;
  bridge_edges: BridgeEdge[];
  component: number | null;
}

export interface ExperimentBundle {
  schema_version?: number;
  exported_at_utc?: string;
  source?: Record<string, unknown>;
  network_summary?: Record<string, unknown>;
  subnet?: Subnet;
  instance?: Record<string, unknown>;
  runs?: Record<string, RunResult>;
  metadata?: Record<string, unknown>;
  extra?: {
    experiment?: string;
    command?: string;
    failure_test?: {
      failed_edge_id: string;
      failed_edge: SubnetEdge;
      before: FailureMetrics;
      after: FailureMetrics;
      comparison: FailureComparison;
    };
  };
}

export interface SourceInfo {
  source: SourceBrief;
  quality: QualityBrief;
  processing: Record<string, unknown>;
  labels: { name: string; tone: Tone; description: string }[];
  pipeline: string[];
  validation: Record<string, string>;
  limitations: string[];
}

export interface SyntheticNode {
  id: number;
  name: string;
  demand: number;
  generation: number;
  priority: number;
  type: string;
  position: [number, number];
  operational: boolean;
  [key: string]: unknown;
}

export interface SyntheticEdge {
  source: number;
  target: number;
  cost: number;
  capacity: number;
  vulnerability: number;
  available: boolean;
  failed: boolean;
  [key: string]: unknown;
}

export interface SyntheticNetwork {
  nodes: SyntheticNode[];
  edges: SyntheticEdge[];
}

export interface SyntheticOptimizeResponse {
  network: SyntheticNetwork;
  objective: { alpha: number; beta: number };
  runs: Record<string, RunResult>;
  config: Record<string, unknown>;
}
