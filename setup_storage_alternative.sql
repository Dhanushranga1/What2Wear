-- Alternative Storage Setup (if the other version fails)
-- =======================================================

-- Method 1: Try to create bucket via SQL (newer Supabase versions)
insert into storage.buckets (id, name, public, file_size_limit)
values ('wardrobe', 'wardrobe', false, 10485760)
on conflict (id) do nothing;

-- Method 2: If SQL fails, create manually:
-- Go to Supabase Dashboard → Storage → Buckets
-- Click "Create bucket"
-- Name: wardrobe  
-- Public: OFF (keep private)
-- File size limit: 10 MB

-- Storage Policies (run this after bucket exists)
-- ===============================================

-- Read (list/get) own files
create policy "wardrobe_read_own"
on storage.objects for select
to authenticated
using (
  bucket_id = 'wardrobe'
  and name like auth.uid()::text || '/%'
);

-- Upload (insert) to own folder
create policy "wardrobe_insert_own"
on storage.objects for insert
to authenticated
with check (
  bucket_id = 'wardrobe'
  and name like auth.uid()::text || '/%'
);

-- Update own files (rarely needed, but harmless for MVP)
create policy "wardrobe_update_own"
on storage.objects for update
to authenticated
using (
  bucket_id = 'wardrobe'
  and name like auth.uid()::text || '/%'
);

-- Delete own files (optional; keep if you want users to remove items later)
create policy "wardrobe_delete_own"
on storage.objects for delete
to authenticated
using (
  bucket_id = 'wardrobe'
  and name like auth.uid()::text || '/%'
);
