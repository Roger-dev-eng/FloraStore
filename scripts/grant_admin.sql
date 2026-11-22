update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
where id = '12b37019-e385-4a5d-bef9-e545215ad457'::uuid
returning id, email, raw_app_meta_data ->> 'role' as perfil;
