import re

from django.db import connection
from django.utils import timezone
from rest_framework import serializers

from donors.models import Donor
from donors.services import calculate_eligibility

PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9() .-]{6,35}$")


class DonorSerializer(serializers.ModelSerializer):
    """Read/write serializer. Eligibility fields are always server-generated."""

    eligible = serializers.SerializerMethodField()
    has_donation_history = serializers.SerializerMethodField()
    days_since_last_donation = serializers.SerializerMethodField()
    days_until_eligible = serializers.SerializerMethodField()
    eligibility_message = serializers.SerializerMethodField()
    eligibility_badge = serializers.SerializerMethodField()

    class Meta:
        model = Donor
        fields = [
            "id",
            "name",
            "blood_type",
            "phone",
            "last_donation",
            "eligible",
            "has_donation_history",
            "days_since_last_donation",
            "days_until_eligible",
            "eligibility_message",
            "eligibility_badge",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "phone": {"required": True, "allow_blank": False},
            "name": {"required": True, "allow_blank": False},
            "last_donation": {"required": False, "allow_null": True},
        }

    def to_representation(self, instance):
        self._eligibility = calculate_eligibility(instance.last_donation)
        data = super().to_representation(instance)
        user = getattr(self.context.get("request"), "user", None)
        # Privacy rule (D9): hospital staff only receive contact details for donors
        # who pass the registry screen. Administrators always see the phone number.
        if not (user and user.is_admin) and not self._eligibility.eligible:
            data["phone"] = None
        return data

    def get_eligible(self, obj):
        return self._eligibility.eligible

    def get_has_donation_history(self, obj):
        return self._eligibility.has_donation_history

    def get_days_since_last_donation(self, obj):
        return self._eligibility.days_since_last_donation

    def get_days_until_eligible(self, obj):
        return self._eligibility.days_until_eligible

    def get_eligibility_message(self, obj):
        return self._eligibility.eligibility_message

    def get_eligibility_badge(self, obj):
        return self._eligibility.eligibility_badge

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Name must contain at least 2 characters.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not PHONE_PATTERN.fullmatch(value):
            raise serializers.ValidationError(
                "Enter a valid phone number (digits, spaces, +, -, brackets; 7-36 characters)."
            )
        normalized = re.sub(r"[^0-9]", "", value)
        instance = getattr(self, "instance", None)
        with connection.cursor() as cursor:
            if instance and instance.pk:
                cursor.execute(
                    "SELECT 1 FROM donors "
                    "WHERE regexp_replace(phone, '[^0-9]', '', 'g') = %s "
                    "AND id <> %s LIMIT 1",
                    [normalized, str(instance.pk)],
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM donors "
                    "WHERE regexp_replace(phone, '[^0-9]', '', 'g') = %s LIMIT 1",
                    [normalized],
                )
            if cursor.fetchone():
                raise serializers.ValidationError("A donor with this phone number already exists.")
        return value

    def validate_last_donation(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("Last donation date cannot be in the future.")
        return value

    def create(self, validated_data):
        now = timezone.now()
        validated_data["created_at"] = now
        validated_data["updated_at"] = now
        return Donor.objects.create(**validated_data)
