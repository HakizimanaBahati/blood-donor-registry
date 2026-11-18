from django.utils import timezone
from rest_framework import serializers

from hospitals.models import Hospital


class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = ["id", "name", "location", "phone", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "location": {"required": False, "allow_blank": True, "allow_null": True},
            "phone": {"required": False, "allow_blank": True, "allow_null": True},
        }

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Hospital name must contain at least 2 characters.")
        return value

    def create(self, validated_data):
        validated_data["created_at"] = timezone.now()
        return Hospital.objects.create(**validated_data)
