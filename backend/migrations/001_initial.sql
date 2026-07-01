create schema if not exists extensions;
create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source_path text not null unique,
  checksum text not null,
  branch_id text check (branch_id is null or branch_id in ('taipei', 'taichung')),
  document_type text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  section text not null,
  page_number integer,
  chunk_index integer not null,
  content text not null,
  embedding extensions.vector(1536) not null,
  search_vector tsvector generated always as (to_tsvector('simple', content)) stored,
  unique(document_id, chunk_index)
);

create index if not exists chunks_embedding_hnsw
  on chunks using hnsw (embedding extensions.vector_cosine_ops);
create index if not exists chunks_search_vector_gin on chunks using gin (search_vector);
create index if not exists chunks_content_trgm on chunks using gin (content extensions.gin_trgm_ops);
create index if not exists documents_branch_idx on documents(branch_id);

create table if not exists chat_logs (
  id uuid primary key default gen_random_uuid(),
  question text not null,
  branch_id text not null,
  answer text not null,
  abstained boolean not null,
  reason text,
  citation_chunk_ids uuid[] not null default '{}',
  retrieved_chunk_ids uuid[] not null default '{}',
  latency_ms integer not null,
  retrieval_ms integer not null,
  generation_ms integer not null,
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  model text not null,
  created_at timestamptz not null default now()
);

create index if not exists chat_logs_created_at_idx on chat_logs(created_at desc);
