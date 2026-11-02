// Shapes of the JSON exported by scripts/site_export.py and scripts/site_research.py.

export type Step = { op: string; args: unknown; response: string; ok: boolean };

export type SessionResult = {
  cause: string | null;
  scope: string | null;
  exact: boolean;
  family_correct: boolean;
  abstained: boolean;
  path_f1: number;
  confidence: number | null;
  recommendation: string | null;
  recommendation_diff_bad: number | null;
  unresolved_between: string[] | null;
  used: { queries: number; experiments: number; units: number };
};

export type Session = {
  kind: "deterministic" | "recorded";
  label: string;
  run?: string;
  steps: Step[];
  report: Record<string, unknown> | null;
  meta?: { model?: string; turns?: number; tool_errors?: number; forced_submit?: boolean };
};

export type WorldOrder = {
  id: string; r: string; z: number; rx: number; ry: number; dest: [number, number] | null;
  created: number; rejected?: number; assigned?: number; c?: string; from?: [number, number] | null;
  at_rest?: number; ready?: number; picked?: number; delivered?: number; cancelled?: number;
};

export type LabArm = {
  key: string; kind: string; params: Record<string, unknown>; cost: number;
  diff_bad: number; ci_bad: [number, number]; diff_time: number; ci_time: [number, number];
  treatment_bad: number; treatment_rejected: number; replica_diffs: number[];
  all_zero: boolean; series_bad: (number | null)[];
};

export type Lab = {
  mode: "A" | "B"; twin_delta: number | null; t0: number; cohort_minutes: number;
  follow_up_minutes: number; replicas: number; replica_ids: [number, number];
  control_bad: number; control_time: number; control_n: number;
  control_series_bad: (number | null)[]; bin_minutes: number; arms: LabArm[];
};

export type Scenario = {
  id: string; level: string; index: number; seed: number; dataset_id: string;
  level_spec: { families: string[]; profile: string };
  observe: string;
  alert: { t: number; series: string; metric: string; score: number };
  world: {
    label: string; grid: number; zones: number; t_end: number; zone_tokens: string[];
    restaurants: { token: string; x: number; y: number; zone: number }[];
    couriers: number; orders: WorldOrder[];
  };
  telemetry: {
    label: string; profile: string; bin_minutes: number; promise: number; observed_until: number;
    t: number[]; created: number[]; resolved: number[]; bad: number[];
    zones: Record<string, { created: number[]; bad: number[] }>;
    gauges: Record<string, [number, number][]>;
  };
  sessions: Record<string, Session>;
  lab: { A: Lab; B: Lab };
  provenance: { commit: string; seed: number; replica_ids: string; command: string; generator: string };
};

// Fetched separately, only after the reveal (DESIGN_SYSTEM §1.6: hidden truth is another route).
export type Truth = {
  id: string;
  reveal: {
    label: string; family: string; fault: Record<string, unknown>; extra_faults: unknown[];
    restaurant_token: string | null; causal_dag: [string, string][];
    impact: Record<string, number | null>; identifiability: string;
  };
  evaluations: Record<string, SessionResult>;
};

export type ScenarioIndex = {
  commit: string; seed: number;
  scenarios: { id: string; level: string; index: number; dataset_id: string; profile: string;
    alert: Scenario["alert"]; agents: string[] }[];
};

export type Acc = { n: number; k: number; acc: number; ci: [number, number]; abstain: number; experiments: number };

export type Research = {
  seed: string; n_per_level: number; sources: Record<string, string>;
  levels: Record<string, { name: string; kind: string; run: string; L0: Acc; L1: Acc; L2: Acc }>;
  l2_pairs: Record<string, { n: number; only_first: number; only_second: number; p: number }>;
  experiment_ablation: {
    with: { n: number; exact: number; ci: [number, number] };
    without: { n: number; exact: number; ci: [number, number] };
    paired: { only_first: number; only_second: number; mcnemar_p: number };
    label: string; source: string;
  };
  matched_ladder: Record<string, Record<string, { exact: number; ci: [number, number]; abstained: number; experiments_mean: number }> | string>;
  ladder: Record<string, Record<string, { exact: number; ci: [number, number]; experiments_mean: number }> | string>;
  twin_sweep: Record<string, { exact: number; ci: [number, number]; rec_diff_bad: number; vs_A_p: number | null }>;
  interventions: {
    n_incidents: number; replicas: number; placebo_all_exactly_zero: boolean;
    variance_ratio: Record<string, { n: number; median: number; q25: number; q75: number; share_below_1: number }>;
    regret_common_oracle: Record<string, { n: number; mean: number; median: number; "share_within_0.02": number }>;
    infeasible: Record<string, number>;
    best_action_counts_by_family: Record<string, Record<string, number>>;
    mean_pareto_size: number;
  };
  gsm8k: { n: number; base_strict: number; sft_strict: number; base_last_number: number; sft_last_number: number };
  names_only: Record<string, { acc: number; majority: number }>;
  receipt: { groups: Record<string, { agent: string; n: number }[]>; total: number; note: string };
};
