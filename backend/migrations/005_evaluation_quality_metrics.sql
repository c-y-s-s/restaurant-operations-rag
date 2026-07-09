alter table evaluation_runs
  add column if not exists answer_correctness_rate double precision,
  add column if not exists p50_latency_ms double precision,
  add column if not exists p95_latency_ms double precision,
  add column if not exists total_input_tokens integer,
  add column if not exists total_output_tokens integer,
  add column if not exists estimated_cost_usd double precision;

alter table evaluation_case_results
  add column if not exists answer_correctness_passed boolean,
  add column if not exists matched_keywords text[] not null default '{}',
  add column if not exists missing_keywords text[] not null default '{}';
