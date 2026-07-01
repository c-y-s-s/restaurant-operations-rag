create table if not exists chat_citations (
  id uuid primary key default gen_random_uuid(),
  chat_log_id uuid not null references chat_logs(id) on delete cascade,
  citation_number integer not null check (citation_number > 0),
  chunk_id uuid references chunks(id) on delete set null,
  document_title text not null,
  section text not null,
  page_number integer,
  branch_id text,
  excerpt text not null,
  statement text,
  created_at timestamptz not null default now(),
  unique (chat_log_id, citation_number)
);

create index if not exists chat_citations_chunk_id_idx on chat_citations(chunk_id);

insert into chat_citations (
  chat_log_id,
  citation_number,
  chunk_id,
  document_title,
  section,
  page_number,
  branch_id,
  excerpt,
  statement,
  created_at
)
select
  l.id,
  cited.ordinality::integer,
  c.id,
  d.title,
  c.section,
  c.page_number,
  d.branch_id,
  left(c.content, 500),
  null,
  l.created_at
from chat_logs l
cross join lateral unnest(l.citation_chunk_ids)
  with ordinality as cited(chunk_id, ordinality)
join chunks c on c.id = cited.chunk_id
join documents d on d.id = c.document_id
on conflict (chat_log_id, citation_number) do nothing;
