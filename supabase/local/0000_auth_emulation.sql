-- LOCAL DEVELOPMENT ONLY. Supabase provides auth.users; this minimal stand-in lets
-- the same migrations and seed data run on a plain PostgreSQL cluster for tests.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id                 uuid PRIMARY KEY,
    instance_id        uuid,
    aud                varchar(255),
    role               varchar(255),
    email              varchar(255),
    encrypted_password varchar(255),
    email_confirmed_at timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);
