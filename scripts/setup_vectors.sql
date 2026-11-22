create schema if not exists extensions;
create extension if not exists vector with schema extensions;
set search_path = public, extensions;
grant usage on schema public, extensions to service_role;

create table if not exists public.flora_knowledge (
    id text primary key,
    title text not null,
    content text not null,
    source_url text not null default '',
    product_id text,
    content_hash text not null,
    embedding_model text not null,
    embedding vector(384) not null,
    updated_at timestamptz not null default now()
);

alter table public.flora_knowledge enable row level security;
revoke all on public.flora_knowledge from anon, authenticated;
grant select, insert, update, delete on public.flora_knowledge to service_role;

create index if not exists flora_knowledge_embedding_idx
on public.flora_knowledge using hnsw (embedding vector_cosine_ops);

create or replace function public.match_flora_knowledge(
    query_embedding vector(384),
    model_name text,
    match_count integer default 6,
    min_similarity double precision default 0.25
)
returns table (
    id text,
    title text,
    content text,
    source_url text,
    product_id text,
    similarity double precision
)
language sql stable security invoker
set search_path = public, extensions
as $$
    select k.id, k.title, k.content, k.source_url, k.product_id,
           1 - (k.embedding <=> query_embedding) as similarity
    from public.flora_knowledge k
    where k.embedding_model = model_name
      and 1 - (k.embedding <=> query_embedding) >= min_similarity
    order by k.embedding <=> query_embedding
    limit greatest(1, least(match_count, 10));
$$;

revoke all on function public.match_flora_knowledge(vector, text, integer, double precision)
from public, anon, authenticated;
grant execute on function public.match_flora_knowledge(vector, text, integer, double precision)
to service_role;

notify pgrst, 'reload schema';
