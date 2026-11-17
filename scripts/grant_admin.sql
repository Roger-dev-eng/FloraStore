-- Substitua o UUID abaixo pelo identificador da conta criada em Authentication > Users.
update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
where id = '00000000-0000-0000-0000-000000000000'::uuid
returning id, email, raw_app_meta_data ->> 'role' as perfil;
