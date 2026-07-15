-- Bank statements are financial evidence: backend service-role access only.
UPDATE storage.buckets SET public = FALSE WHERE id = 'bank-statements';
DROP POLICY IF EXISTS "Allow public select" ON storage.objects;
