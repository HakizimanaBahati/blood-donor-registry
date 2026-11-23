"""B-05B7-T local-only identity alignment for the isolated PostgreSQL test DB.

Commands (both writes require --yes):
    python b05b7_r.py align --yes
    python b05b7_r.py rollback --yes

Safety contract:
- Target is TEST_DATABASE_URL only, on loopback port 55432.
- Hosted Supabase is never contacted.
- Admin/hospital UUIDs are read only from the approved local input file.
- The resolved hospital id is written only to the approved local side file.
- No UUID, DSN, credential, or raw psycopg exception is printed.

F8 fail-closed precondition: the rollback path requires exactly
EXPECTED_REQUESTS (6) request rows, matching the audited pre-alignment state.
If application data changes, rollback refuses instead of guessing.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse
from uuid import UUID

import psycopg
from dotenv import dotenv_values

BASE = Path(__file__).resolve().parent
IDS_FILE = Path(r"C:\Users\user\AppData\Local\Temp\opencode\b05b4-ids.txt")
HID_FILE = Path(r"C:\Users\user\AppData\Local\Temp\opencode\b05b7-hospital-id.txt")

EXPECTED_PORT = 55432
EXPECTED_AUTH_PRE = 3          # audited pre-alignment auth.users count
EXPECTED_PROFILE_PRE = 3       # audited pre-alignment profiles count
EXPECTED_REQUESTS = 6          # F8: fail-closed request-row precondition
ADMIN_MARKER = "[LIVE] Hosted Admin"
HOSPITAL_MARKER = "[LIVE] Hosted Hospital"
SEED_ADMIN_MARKER = "[TEST] Admin User"
SEED_HOSP1_MARKER = "[TEST] Hospital One User"
SEED_HOSP2_MARKER = "[TEST] Hospital Two User"
SEED_EMAIL_DOMAIN = "@example.invalid"
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
ALLOWED_ROLES = ("admin", "hospital")
ALLOWED_EXECUTORS = ("postgres", "service_role")
SQLSTATE_RE = re.compile(r"^[0-9A-Z]{5}$")

LOCK_SQL = (
    "LOCK TABLE public.hospitals, auth.users, public.profiles "
    "IN SHARE ROW EXCLUSIVE MODE NOWAIT"
)

INSERT_AUTH_SQL = """
INSERT INTO auth.users
    (id, instance_id, aud, role, email, email_confirmed_at, created_at, updated_at)
VALUES
    (%s, '00000000-0000-0000-0000-000000000000',
     'authenticated', 'authenticated', NULL, now(), now(), now()),
    (%s, '00000000-0000-0000-0000-000000000000',
     'authenticated', 'authenticated', NULL, now(), now(), now())
"""

ASSIGN_ADMIN_SQL = "SELECT public.assign_role(%s, 'admin', %s, NULL)"
ASSIGN_HOSPITAL_SQL = "SELECT public.assign_role(%s, 'hospital', %s, %s)"

ALIGN_PRECHECK_SQL = r"""
DO $$
DECLARE
    v_admin uuid := current_setting('app.admin_subject')::uuid;
    v_hosp  uuid := current_setting('app.hospital_subject')::uuid;
    v_hid   uuid := current_setting('app.hospital_id')::uuid;
    v_db    text := current_setting('app.expected_db');
    v_auth0 integer := current_setting('app.expected_auth_pre')::integer;
    v_prof0 integer := current_setting('app.expected_profile_pre')::integer;
    v_req0  integer := current_setting('app.expected_requests')::integer;
BEGIN
    -- F2/F4: NULL-safe target verification, rechecked after locks.
    IF (SELECT inet_server_addr() IN ('127.0.0.1','::1')
          AND inet_server_port() = 55432) IS NOT TRUE THEN
        RAISE EXCEPTION 'B05B7T: target is not loopback:55432';
    END IF;
    IF (current_database() = v_db) IS NOT TRUE THEN
        RAISE EXCEPTION 'B05B7T: unexpected database name';
    END IF;
    -- F9: executor role rechecked inside the transaction.
    IF (current_user IN ('postgres','service_role')) IS NOT TRUE THEN
        RAISE EXCEPTION 'B05B7T: unexpected executor role';
    END IF;

    IF v_admin = v_hosp THEN
        RAISE EXCEPTION 'B05B7T: subjects are not distinct';
    END IF;

    IF (SELECT count(*) FROM auth.users) <> v_auth0 THEN
        RAISE EXCEPTION 'B05B7T: auth.users count drifted';
    END IF;
    IF (SELECT count(*) FROM public.profiles) <> v_prof0 THEN
        RAISE EXCEPTION 'B05B7T: profiles count drifted';
    END IF;
    IF (SELECT count(*) FROM public.requests) <> v_req0 THEN
        RAISE EXCEPTION 'B05B7T: requests count drifted (F8 precondition)';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE role = 'admin') <> 1 THEN
        RAISE EXCEPTION 'B05B7T: pre admin count is not 1';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE role = 'hospital') <> 2 THEN
        RAISE EXCEPTION 'B05B7T: pre hospital count is not 2';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE role NOT IN ('admin','hospital')) <> 0 THEN
        RAISE EXCEPTION 'B05B7T: pre invalid role present';
    END IF;

    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Admin User'
           AND role = 'admin' AND hospital_id IS NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: seed admin marker missing or changed';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital One User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: seed hospital one marker missing or changed';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital Two User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: seed hospital two marker missing or changed';
    END IF;
    IF (SELECT count(*) FROM auth.users
         WHERE right(lower(email), 16) = '@example.invalid') <> 3 THEN
        RAISE EXCEPTION 'B05B7T: seed auth rows missing or changed';
    END IF;
    IF (SELECT count(*) FROM public.profiles p
          JOIN auth.users u ON u.id = p.id) <> v_prof0 THEN
        RAISE EXCEPTION 'B05B7T: pre-existing orphan profile';
    END IF;

    IF EXISTS (SELECT 1 FROM auth.users WHERE id IN (v_admin, v_hosp)) THEN
        RAISE EXCEPTION 'B05B7T: subject already present in auth.users';
    END IF;
    IF EXISTS (SELECT 1 FROM public.profiles WHERE id IN (v_admin, v_hosp)) THEN
        RAISE EXCEPTION 'B05B7T: subject already present in profiles';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.hospitals WHERE id = v_hid) THEN
        RAISE EXCEPTION 'B05B7T: hospital not found';
    END IF;
    IF EXISTS (SELECT 1 FROM public.profiles WHERE hospital_id = v_hid) THEN
        RAISE EXCEPTION 'B05B7T: hospital already referenced';
    END IF;
    IF (SELECT count(*) FROM public.hospitals h
         WHERE NOT EXISTS (SELECT 1 FROM public.profiles p
                            WHERE p.hospital_id = h.id)) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: unreferenced hospital is not unique';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.hospitals h
                    WHERE h.id = v_hid
                      AND NOT EXISTS (SELECT 1 FROM public.profiles p
                                       WHERE p.hospital_id = h.id)) THEN
        RAISE EXCEPTION 'B05B7T: chosen hospital is not the unreferenced one';
    END IF;
END $$;
"""

ALIGN_POSTCHECK_SQL = r"""
DO $$
DECLARE
    v_admin uuid := current_setting('app.admin_subject')::uuid;
    v_hosp  uuid := current_setting('app.hospital_subject')::uuid;
    v_hid   uuid := current_setting('app.hospital_id')::uuid;
    v_auth0 integer := current_setting('app.expected_auth_pre')::integer;
    v_prof0 integer := current_setting('app.expected_profile_pre')::integer;
    v_req0  integer := current_setting('app.expected_requests')::integer;
BEGIN
    IF (SELECT count(*) FROM auth.users) <> 5 THEN
        RAISE EXCEPTION 'B05B7T: post auth.users count is not 5';
    END IF;
    IF (SELECT count(*) FROM public.profiles) <> 5 THEN
        RAISE EXCEPTION 'B05B7T: post profiles count is not 5';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE role = 'admin') <> 2 THEN
        RAISE EXCEPTION 'B05B7T: post admin count is not 2';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE role = 'hospital') <> 3 THEN
        RAISE EXCEPTION 'B05B7T: post hospital count is not 3';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE role NOT IN ('admin','hospital')) <> 0 THEN
        RAISE EXCEPTION 'B05B7T: post invalid role present';
    END IF;
    IF (SELECT count(*) FROM public.profiles p
          LEFT JOIN auth.users u ON u.id = p.id
         WHERE u.id IS NULL) <> 0 THEN
        RAISE EXCEPTION 'B05B7T: post orphan profile';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE id NOT IN (v_admin, v_hosp)) <> v_prof0 THEN
        RAISE EXCEPTION 'B05B7T: pre-existing profiles disturbed';
    END IF;
    IF (SELECT count(*) FROM auth.users
         WHERE id NOT IN (v_admin, v_hosp)) <> v_auth0 THEN
        RAISE EXCEPTION 'B05B7T: pre-existing auth rows disturbed';
    END IF;

    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Admin User'
           AND role = 'admin' AND hospital_id IS NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: seed admin marker changed';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital One User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: seed hospital one marker changed';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital Two User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: seed hospital two marker changed';
    END IF;
    IF (SELECT count(*) FROM auth.users
         WHERE right(lower(email), 16) = '@example.invalid') <> 3 THEN
        RAISE EXCEPTION 'B05B7T: seed auth rows changed';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.profiles
                    WHERE id = v_admin
                      AND full_name = '[LIVE] Hosted Admin'
                      AND role = 'admin'
                      AND hospital_id IS NULL) THEN
        RAISE EXCEPTION 'B05B7T: admin profile shape wrong';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.profiles
                    WHERE id = v_hosp
                      AND full_name = '[LIVE] Hosted Hospital'
                      AND role = 'hospital'
                      AND hospital_id = v_hid) THEN
        RAISE EXCEPTION 'B05B7T: hospital profile shape wrong';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE hospital_id = v_hid) <> 1 THEN
        RAISE EXCEPTION 'B05B7T: hospital association wrong';
    END IF;
    IF (SELECT count(*) FROM public.hospitals) <> 3 THEN
        RAISE EXCEPTION 'B05B7T: hospital count changed';
    END IF;
    IF (SELECT count(*) FROM public.hospitals h
         WHERE NOT EXISTS (SELECT 1 FROM public.profiles p
                            WHERE p.hospital_id = h.id)) <> 0 THEN
        RAISE EXCEPTION 'B05B7T: unreferenced hospital remains';
    END IF;
    IF (SELECT count(*) FROM public.requests) <> v_req0 THEN
        RAISE EXCEPTION 'B05B7T: requests count changed';
    END IF;
    IF (SELECT count(*) FROM auth.users
         WHERE id IN (v_admin, v_hosp)
           AND aud = 'authenticated'
           AND role = 'authenticated'
           AND email IS NULL
           AND instance_id = '00000000-0000-0000-0000-000000000000') <> 2 THEN
        RAISE EXCEPTION 'B05B7T: aligned auth rows shape wrong';
    END IF;
END $$;
"""

ROLLBACK_PRECHECK_SQL = r"""
DO $$
DECLARE
    v_admin uuid := current_setting('app.admin_subject')::uuid;
    v_hosp  uuid := current_setting('app.hospital_subject')::uuid;
    v_hid   uuid := current_setting('app.hospital_id')::uuid;
    v_db    text := current_setting('app.expected_db');
    v_req0  integer := current_setting('app.expected_requests')::integer;
BEGIN
    -- F2/F4/F9: NULL-safe target and executor checks.
    IF (SELECT inet_server_addr() IN ('127.0.0.1','::1')
          AND inet_server_port() = 55432) IS NOT TRUE THEN
        RAISE EXCEPTION 'B05B7T rollback: target is not loopback:55432';
    END IF;
    IF (current_database() = v_db) IS NOT TRUE THEN
        RAISE EXCEPTION 'B05B7T rollback: unexpected database name';
    END IF;
    IF (current_user IN ('postgres','service_role')) IS NOT TRUE THEN
        RAISE EXCEPTION 'B05B7T rollback: unexpected executor role';
    END IF;
    IF v_admin = v_hosp THEN
        RAISE EXCEPTION 'B05B7T rollback: subjects are not distinct';
    END IF;

    IF (SELECT count(*) FROM auth.users) <> 5 THEN
        RAISE EXCEPTION 'B05B7T rollback: auth.users count is not 5';
    END IF;
    IF (SELECT count(*) FROM public.profiles) <> 5 THEN
        RAISE EXCEPTION 'B05B7T rollback: profiles count is not 5';
    END IF;
    IF (SELECT count(*) FROM public.requests) <> v_req0 THEN
        RAISE EXCEPTION 'B05B7T rollback: requests count drifted (F8 precondition)';
    END IF;

    -- Exact aligned auth rows; NULL email distinguishes them from seeds.
    IF (SELECT count(*) FROM auth.users
         WHERE id IN (v_admin, v_hosp)
           AND aud = 'authenticated'
           AND role = 'authenticated'
           AND email IS NULL
           AND instance_id = '00000000-0000-0000-0000-000000000000') <> 2 THEN
        RAISE EXCEPTION 'B05B7T rollback: aligned auth rows missing or changed';
    END IF;
    IF EXISTS (SELECT 1 FROM auth.users
                WHERE id IN (v_admin, v_hosp) AND email IS NOT NULL) THEN
        RAISE EXCEPTION 'B05B7T rollback: refusing seed-like auth row';
    END IF;

    IF (SELECT count(*) FROM public.profiles
         WHERE id = v_admin
           AND full_name = '[LIVE] Hosted Admin'
           AND role = 'admin'
           AND hospital_id IS NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: admin profile modified';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE id = v_hosp
           AND full_name = '[LIVE] Hosted Hospital'
           AND role = 'hospital'
           AND hospital_id = v_hid) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: hospital profile or association modified';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.hospitals WHERE id = v_hid) THEN
        RAISE EXCEPTION 'B05B7T rollback: hospital missing';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE hospital_id = v_hid) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: hospital association not unique';
    END IF;

    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Admin User'
           AND role = 'admin' AND hospital_id IS NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed admin changed';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital One User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed hospital one changed';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital Two User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed hospital two changed';
    END IF;
    IF (SELECT count(*) FROM auth.users
         WHERE right(lower(email), 16) = '@example.invalid') <> 3 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed auth rows changed';
    END IF;

    IF (SELECT count(*) FROM public.profiles p
          LEFT JOIN auth.users u ON u.id = p.id
         WHERE u.id IS NULL) <> 0 THEN
        RAISE EXCEPTION 'B05B7T rollback: orphan profile present';
    END IF;
    IF (SELECT count(*) FROM public.hospitals) <> 3 THEN
        RAISE EXCEPTION 'B05B7T rollback: hospital count changed';
    END IF;
END $$;
"""

ROLLBACK_DELETE_SQL = r"""
DO $$
DECLARE
    v_admin uuid := current_setting('app.admin_subject')::uuid;
    v_hosp  uuid := current_setting('app.hospital_subject')::uuid;
    n integer;
BEGIN
    -- Delete only the two aligned profiles, identified by id AND marker.
    DELETE FROM public.profiles
     WHERE id IN (v_admin, v_hosp)
       AND full_name IN ('[LIVE] Hosted Admin', '[LIVE] Hosted Hospital');
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 2 THEN
        RAISE EXCEPTION 'B05B7T rollback: profile delete count is not 2';
    END IF;

    -- Delete only the two aligned auth rows; seeds have non-null email.
    DELETE FROM auth.users
     WHERE id IN (v_admin, v_hosp)
       AND email IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 2 THEN
        RAISE EXCEPTION 'B05B7T rollback: auth delete count is not 2';
    END IF;
END $$;
"""

ROLLBACK_POSTCHECK_SQL = r"""
DO $$
DECLARE
    v_admin uuid := current_setting('app.admin_subject')::uuid;
    v_hosp  uuid := current_setting('app.hospital_subject')::uuid;
    v_hid   uuid := current_setting('app.hospital_id')::uuid;
    v_req0  integer := current_setting('app.expected_requests')::integer;
BEGIN
    IF (SELECT count(*) FROM auth.users) <> 3 THEN
        RAISE EXCEPTION 'B05B7T rollback: auth.users count not restored';
    END IF;
    IF (SELECT count(*) FROM public.profiles) <> 3 THEN
        RAISE EXCEPTION 'B05B7T rollback: profiles count not restored';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE role = 'admin') <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: admin count not restored';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE role = 'hospital') <> 2 THEN
        RAISE EXCEPTION 'B05B7T rollback: hospital count not restored';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE role NOT IN ('admin','hospital')) <> 0 THEN
        RAISE EXCEPTION 'B05B7T rollback: invalid role present';
    END IF;
    IF EXISTS (SELECT 1 FROM auth.users WHERE id IN (v_admin, v_hosp)) THEN
        RAISE EXCEPTION 'B05B7T rollback: aligned auth rows remain';
    END IF;
    IF EXISTS (SELECT 1 FROM public.profiles WHERE id IN (v_admin, v_hosp)) THEN
        RAISE EXCEPTION 'B05B7T rollback: aligned profiles remain';
    END IF;
    IF (SELECT count(*) FROM public.profiles WHERE hospital_id = v_hid) <> 0 THEN
        RAISE EXCEPTION 'B05B7T rollback: hospital still referenced';
    END IF;
    IF (SELECT count(*) FROM public.hospitals h
         WHERE NOT EXISTS (SELECT 1 FROM public.profiles p
                            WHERE p.hospital_id = h.id)) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: unreferenced hospital not restored';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Admin User'
           AND role = 'admin' AND hospital_id IS NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed admin missing';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital One User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed hospital one missing';
    END IF;
    IF (SELECT count(*) FROM public.profiles
         WHERE full_name = '[TEST] Hospital Two User'
           AND role = 'hospital' AND hospital_id IS NOT NULL) <> 1 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed hospital two missing';
    END IF;
    IF (SELECT count(*) FROM auth.users
         WHERE right(lower(email), 16) = '@example.invalid') <> 3 THEN
        RAISE EXCEPTION 'B05B7T rollback: seed auth rows missing';
    END IF;
    IF (SELECT count(*) FROM public.profiles p
          LEFT JOIN auth.users u ON u.id = p.id
         WHERE u.id IS NULL) <> 0 THEN
        RAISE EXCEPTION 'B05B7T rollback: orphan profile present';
    END IF;
    IF (SELECT count(*) FROM public.hospitals) <> 3 THEN
        RAISE EXCEPTION 'B05B7T rollback: hospital count changed';
    END IF;
    IF (SELECT count(*) FROM public.requests) <> v_req0 THEN
        RAISE EXCEPTION 'B05B7T rollback: requests count changed';
    END IF;
END $$;
"""


def fail(message: str) -> NoReturn:
    """Raise a sanitized, fail-closed error (static message only)."""
    raise SystemExit("BLOCKED: " + message)


def db_fail(exc: BaseException) -> NoReturn:
    """F1: suppress raw psycopg text; expose only a validated SQLSTATE."""
    state = getattr(exc, "sqlstate", None)
    suffix = ""
    if isinstance(state, str) and SQLSTATE_RE.fullmatch(state):
        suffix = " [sqlstate=" + state + "]"
    raise SystemExit(
        "BLOCKED: database operation failed (details suppressed)" + suffix
    ) from None


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _close_quietly(conn) -> None:
    """F1: never surface raw errors from session cleanup."""
    try:
        conn.close()
    except Exception:
        pass


def load_ids() -> tuple[str, str]:
    """F6: exactly two distinct UUIDs, keys admin/hospital, no duplicates."""
    try:
        text = IDS_FILE.read_text(encoding="utf-8-sig")
    except OSError:
        fail("approved input file is missing or unreadable")

    ids: dict[str, str] = {}
    entries = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        entries += 1
        if "=" not in line:
            fail("approved input file is malformed")
        key, value = line.split("=", 1)
        key = key.strip().lower()
        value = value.strip().strip('"').strip("'")
        if key not in {"admin", "hospital"}:
            fail("approved input file has an unexpected key")
        if key in ids:
            fail("approved input file has a duplicate key")
        if not value:
            fail("approved input file has an empty value")
        try:
            UUID(value)
        except ValueError:
            fail("approved input file has an invalid UUID")
        ids[key] = value

    if entries != 2 or set(ids) != {"admin", "hospital"}:
        fail("approved input file must contain exactly admin and hospital")
    if ids["admin"] == ids["hospital"]:
        fail("admin and hospital subjects must be distinct")
    return ids["admin"], ids["hospital"]


def load_url() -> tuple[str, str]:
    """F5: no silent .env fallback; loopback/port/database validation inputs."""
    if "TEST_DATABASE_URL" in os.environ:
        raw = os.environ["TEST_DATABASE_URL"]
        if not raw or not raw.strip():
            fail("TEST_DATABASE_URL is present but empty")
    else:
        values = dotenv_values(BASE / ".env")
        raw = values.get("TEST_DATABASE_URL")
        if not raw or not str(raw).strip():
            fail("TEST_DATABASE_URL is missing from local .env")
        raw = str(raw)

    parsed = urlparse(raw)
    try:
        port = parsed.port
    except ValueError:
        fail("TEST_DATABASE_URL has an invalid port")

    host = (parsed.hostname or "").lower()
    if port != EXPECTED_PORT:
        fail("TEST_DATABASE_URL is not port 55432")
    if host not in {"localhost", "127.0.0.1", "::1"}:
        fail("TEST_DATABASE_URL is not loopback")
    if "supabase" in host or host.endswith(".supabase.com"):
        fail("TEST_DATABASE_URL points at hosted Supabase")

    expected_db = (parsed.path or "").lstrip("/")
    if not expected_db:
        fail("TEST_DATABASE_URL has no database name")
    return raw, expected_db


def assert_target(cur, expected_db: str) -> None:
    """F2/F4: loopback, port, and exact database name (NULL-safe SQL)."""
    try:
        cur.execute(
            "SELECT (inet_server_addr() IN ('127.0.0.1','::1')) IS TRUE, "
            "(inet_server_port() = %s) IS TRUE, "
            "(current_database() = %s) IS TRUE",
            (EXPECTED_PORT, expected_db),
        )
        loopback, port_ok, db_ok = cur.fetchone()
    except psycopg.Error as exc:
        db_fail(exc)
    if not (loopback and port_ok and db_ok):
        fail("target verification failed (loopback, port, or database)")


def assert_privileges(cur) -> None:
    """F9: require the expected executor role and write privileges."""
    try:
        cur.execute(
            "SELECT (current_user IN ('postgres','service_role')) IS TRUE, "
            "has_table_privilege(current_user, 'auth.users', 'INSERT') IS TRUE, "
            "has_function_privilege(current_user, "
            "'public.assign_role(uuid,varchar,varchar,uuid)', 'EXECUTE') IS TRUE"
        )
        role_ok, insert_ok, exec_ok = cur.fetchone()
    except psycopg.Error as exc:
        db_fail(exc)
    if not (role_ok and insert_ok and exec_ok):
        fail("executor role or privileges are not permitted")


def connect_checked(url: str, expected_db: str):
    """F1/F2/F9: connect once and verify target/privileges before any write."""
    try:
        conn = psycopg.connect(url, connect_timeout=5)
    except psycopg.Error as exc:
        db_fail(exc)

    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            assert_target(cur, expected_db)
            assert_privileges(cur)
    except BaseException:
        _close_quietly(conn)
        raise
    try:
        conn.rollback()
    except Exception as exc:
        _close_quietly(conn)
        if isinstance(exc, psycopg.Error):
            db_fail(exc)
        fail("database session cleanup failed")
    return conn


def read_summary(conn) -> dict[str, int]:
    """Read-only aggregate summary; prints counts only, never identifiers."""
    with conn.cursor() as cur:
        def count(sql: str) -> int:
            cur.execute(sql)
            return int(cur.fetchone()[0])

        return {
            "auth_users": count("SELECT count(*) FROM auth.users"),
            "profiles": count("SELECT count(*) FROM public.profiles"),
            "admin_profiles": count(
                "SELECT count(*) FROM public.profiles WHERE role = 'admin'"
            ),
            "hospital_profiles": count(
                "SELECT count(*) FROM public.profiles WHERE role = 'hospital'"
            ),
            "invalid_role_profiles": count(
                "SELECT count(*) FROM public.profiles "
                "WHERE role NOT IN ('admin','hospital')"
            ),
            "orphan_profiles": count(
                "SELECT count(*) FROM public.profiles p "
                "LEFT JOIN auth.users u ON u.id = p.id WHERE u.id IS NULL"
            ),
            "unreferenced_hospitals": count(
                "SELECT count(*) FROM public.hospitals h "
                "WHERE NOT EXISTS (SELECT 1 FROM public.profiles p "
                "WHERE p.hospital_id = h.id)"
            ),
            "requests": count("SELECT count(*) FROM public.requests"),
        }


def print_summary(summary: dict[str, int] | None) -> None:
    if summary is None:
        print("summary: unavailable")
        return
    print("summary: " + " ".join(f"{k}={v}" for k, v in summary.items()))


def align() -> None:
    """Insert two aligned identities; single locked transaction; F3 cleanup."""
    admin, hospital = load_ids()
    url, expected_db = load_url()

    hid_existed = HID_FILE.exists()
    old_hid: str | None = None
    if hid_existed:
        try:
            old_hid = HID_FILE.read_text(encoding="utf-8")
        except OSError:
            fail("hospital id side file is unreadable")

    wrote_hid = False
    committed = False
    summary: dict[str, int] | None = None
    conn = connect_checked(url, expected_db)
    try:
        with conn.transaction():
            cur = conn.cursor()
            assert_target(cur, expected_db)
            assert_privileges(cur)
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '60s'")

            cur.execute(
                "SELECT set_config('app.admin_subject', %s, true)", (admin,)
            )
            cur.execute(
                "SELECT set_config('app.hospital_subject', %s, true)", (hospital,)
            )
            cur.execute(
                "SELECT set_config('app.expected_db', %s, true)", (expected_db,)
            )
            cur.execute(
                "SELECT set_config('app.expected_auth_pre', %s, true)",
                (str(EXPECTED_AUTH_PRE),),
            )
            cur.execute(
                "SELECT set_config('app.expected_profile_pre', %s, true)",
                (str(EXPECTED_PROFILE_PRE),),
            )
            cur.execute(
                "SELECT set_config('app.expected_requests', %s, true)",
                (str(EXPECTED_REQUESTS),),
            )

            cur.execute(LOCK_SQL)

            cur.execute(
                "SELECT count(*) FROM public.hospitals h "
                "WHERE NOT EXISTS (SELECT 1 FROM public.profiles p "
                "WHERE p.hospital_id = h.id)"
            )
            if cur.fetchone()[0] != 1:
                fail("unreferenced hospital is not unique under lock")

            cur.execute(
                "SELECT h.id FROM public.hospitals h "
                "WHERE NOT EXISTS (SELECT 1 FROM public.profiles p "
                "WHERE p.hospital_id = h.id) "
                "ORDER BY h.created_at, h.id LIMIT 1"
            )
            hospital_id = cur.fetchone()[0]

            wrote_hid = True
            HID_FILE.write_text(str(hospital_id), encoding="utf-8")
            cur.execute(
                "SELECT set_config('app.hospital_id', %s, true)",
                (str(hospital_id),),
            )

            cur.execute(ALIGN_PRECHECK_SQL)
            cur.execute(INSERT_AUTH_SQL, (admin, hospital))
            cur.execute(ASSIGN_ADMIN_SQL, (admin, ADMIN_MARKER))
            cur.execute(
                ASSIGN_HOSPITAL_SQL, (hospital, HOSPITAL_MARKER, hospital_id)
            )
            cur.execute(ALIGN_POSTCHECK_SQL)

        committed = True
        try:
            summary = read_summary(conn)
        except Exception:
            summary = None
    except BaseException as exc:
        # F3: only unwind the side file when this run created it and did not commit.
        if not committed and wrote_hid:
            if hid_existed and old_hid is not None:
                try:
                    HID_FILE.write_text(old_hid, encoding="utf-8")
                except OSError:
                    pass
            elif not hid_existed:
                _unlink_quietly(HID_FILE)
        if isinstance(exc, psycopg.Error):
            db_fail(exc)
        raise
    finally:
        _close_quietly(conn)

    print("ALIGN COMMITTED")
    print_summary(summary)


def rollback() -> None:
    """Remove only the two aligned identities; fail closed on any drift."""
    admin, hospital = load_ids()
    url, expected_db = load_url()

    if not HID_FILE.is_file():
        fail("hospital id side file is missing")
    try:
        hospital_id = UUID(HID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        fail("hospital id side file is unreadable or malformed")

    committed = False
    summary: dict[str, int] | None = None
    conn = connect_checked(url, expected_db)
    try:
        with conn.transaction():
            cur = conn.cursor()
            assert_target(cur, expected_db)
            assert_privileges(cur)
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '60s'")

            cur.execute(
                "SELECT set_config('app.admin_subject', %s, true)", (admin,)
            )
            cur.execute(
                "SELECT set_config('app.hospital_subject', %s, true)", (hospital,)
            )
            cur.execute(
                "SELECT set_config('app.expected_db', %s, true)", (expected_db,)
            )
            cur.execute(
                "SELECT set_config('app.hospital_id', %s, true)",
                (str(hospital_id),),
            )
            cur.execute(
                "SELECT set_config('app.expected_requests', %s, true)",
                (str(EXPECTED_REQUESTS),),
            )

            cur.execute(LOCK_SQL)
            cur.execute(ROLLBACK_PRECHECK_SQL)
            cur.execute(ROLLBACK_DELETE_SQL)
            cur.execute(ROLLBACK_POSTCHECK_SQL)

        committed = True
        try:
            summary = read_summary(conn)
        except Exception:
            summary = None
    except BaseException as exc:
        if isinstance(exc, psycopg.Error):
            db_fail(exc)
        raise
    finally:
        _close_quietly(conn)

    print("ROLLBACK COMMITTED")
    print_summary(summary)


def main(argv: list[str]) -> None:
    if len(argv) < 2 or argv[1] not in {"align", "rollback"}:
        print("usage: python b05b7_r.py [align|rollback] --yes")
        raise SystemExit(2)
    if "--yes" not in argv[2:]:
        fail("writes require --yes")
    if argv[1] == "align":
        align()
    else:
        rollback()


if __name__ == "__main__":
    main(sys.argv)
