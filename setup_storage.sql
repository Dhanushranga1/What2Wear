-- 1) Create a PRIVATE bucket for wardrobe images (10 MB limit per object)
-- Note: You may need to create the bucket manually via Supabase Dashboard if this fails
-- Go to Storage → Buckets → Create bucket named 'wardrobe' (set to private)
insert into storage.buckets (id, name, public, file_size_limit)
values ('wardrobe', 'wardrobe', false, 10485760)
on conflict (id) do nothing;

-- 2) Storage policies: allow each authenticated user to manage ONLY their own folder "<uid>/..."
-- NOTE: Storage policies live on storage.objects
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
