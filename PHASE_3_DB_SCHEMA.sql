# Phase 3 Database Schema

Run this SQL in your Supabase SQL Editor to create the garments table with proper RLS and indexes.

```sql
-- 3.1 Table
create table if not exists public.garments (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,
  category    text not null check (category in ('top','bottom','one_piece')),
  subtype     text,
  image_path  text not null,                   -- e.g., 'wardrobe/<uid>/<uuid>.webp'
  image_url   text,                            -- optional: last used signed URL (for convenience)
  color_bins  text[] not null default '{}',    -- e.g., {'blue','neutral'}
  meta_tags   text[] not null default '{}',    -- e.g., {'casual','summer'}
  created_at  timestamptz default now()
);

-- 3.2 RLS
alter table public.garments enable row level security;

create policy "garments_select_owner"
  on public.garments for select
  using (auth.uid() = user_id);

create policy "garments_insert_owner"
  on public.garments for insert
  with check (auth.uid() = user_id);

create policy "garments_update_owner"
  on public.garments for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- 3.3 Indexes
create index if not exists idx_garments_user on public.garments(user_id);
create index if not exists idx_garments_user_category on public.garments(user_id, category);
create index if not exists idx_garments_color_bins on public.garments using gin (color_bins);
```

## Instructions

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Copy and paste the above SQL
4. Run the query to create the table, RLS policies, and indexes
5. Verify the table appears in the Table Editor with proper permissions
