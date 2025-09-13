-- Table for all garments
create table if not exists public.garments (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,
  category    text not null check (category in ('top','bottom','one_piece')),
  subtype     text,
  image_path  text not null,                   -- e.g. 'wardrobe/<uid>/<uuid>.webp'
  image_url   text,                            -- last used signed URL (optional)
  color_bins  text[] not null default '{}',    -- e.g. {'blue','neutral'}
  meta_tags   text[] not null default '{}',    -- e.g. {'casual','summer'}
  created_at  timestamptz default now()
);

-- RLS (row-level security): only owner can read/write
alter table public.garments enable row level security;

-- Select
create policy if not exists "garments_select_owner"
  on public.garments for select
  to authenticated
  using (auth.uid() = user_id);

-- Insert
create policy if not exists "garments_insert_owner"
  on public.garments for insert
  to authenticated
  with check (auth.uid() = user_id);

-- Update
create policy if not exists "garments_update_owner"
  on public.garments for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Helpful indexes for speed
create index if not exists idx_garments_user on public.garments(user_id);
create index if not exists idx_garments_user_category on public.garments(user_id, category);
create index if not exists idx_garments_color_bins on public.garments using gin (color_bins);
