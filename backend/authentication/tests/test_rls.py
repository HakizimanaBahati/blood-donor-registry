"""Database-level permission tests that complement the DRF permission tests."""
from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from common.test_helpers import HOSPITAL_ONE_ID


class RowLevelSecurityTests(TestCase):
    def test_hospital_cannot_promote_its_own_profile_via_sql(self):
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE authenticated")
                    cursor.execute(
                        "SELECT set_config('request.jwt.claim.sub', %s, true)",
                        [str(HOSPITAL_ONE_ID)],
                    )
                with self.assertRaises(DatabaseError):
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "UPDATE public.profiles SET role = 'admin' WHERE id = %s",
                                [str(HOSPITAL_ONE_ID)],
                            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute("SELECT set_config('request.jwt.claim.sub', '', false)")

    def test_anonymous_sql_user_cannot_read_donors(self):
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE authenticated")
                    cursor.execute("SELECT set_config('request.jwt.claim.sub', '', true)")
                    cursor.execute("SELECT count(*) FROM public.donors")
                    self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute("SELECT set_config('request.jwt.claim.sub', '', false)")
