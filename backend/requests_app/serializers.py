from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from donors.models import Donor
from donors.services import calculate_eligibility, ensure_donor_selectable
from hospitals.models import Hospital
from requests_app.models import BloodRequest


class BloodRequestSerializer(serializers.ModelSerializer):
    """Blood request write/read serializer with server-side eligibility enforcement."""

    hospital_id = serializers.PrimaryKeyRelatedField(
        source="hospital",
        queryset=Hospital.objects.all(),
        required=False,
        pk_field=serializers.UUIDField(),
    )
    donor_id = serializers.PrimaryKeyRelatedField(
        source="donor",
        queryset=Donor.objects.all(),
        required=False,
        allow_null=True,
        pk_field=serializers.UUIDField(),
    )
    hospital_name = serializers.CharField(source="hospital.name", read_only=True)
    requester_profile_id = serializers.UUIDField(read_only=True)
    donor_name = serializers.SerializerMethodField()
    donor_blood_type = serializers.SerializerMethodField()
    donor_eligible = serializers.SerializerMethodField()

    class Meta:
        model = BloodRequest
        fields = [
            "id",
            "hospital_id",
            "hospital_name",
            "blood_type",
            "units",
            "status",
            "notes",
            "donor_id",
            "donor_name",
            "donor_blood_type",
            "donor_eligible",
            "requester_profile_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "hospital_name",
            "donor_name",
            "donor_blood_type",
            "donor_eligible",
            "requester_profile_id",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "notes": {"required": False, "allow_blank": True, "allow_null": True},
            "status": {"required": False},
            "units": {"min_value": 1, "max_value": 10000},
        }

    def get_donor_name(self, obj):
        return obj.donor.name if obj.donor_id else None

    def get_donor_blood_type(self, obj):
        return obj.donor.blood_type if obj.donor_id else None

    def get_donor_eligible(self, obj):
        return calculate_eligibility(obj.donor.last_donation).eligible if obj.donor_id else None

    def validate_donor_id(self, donor):
        # A hospital cannot attach an ineligible donor to a request. Django decides.
        if donor is not None:
            ensure_donor_selectable(donor)
        return donor

    def validate_units(self, value):
        if value <= 0:
            raise ValidationError("Units must be greater than zero.")
        return value

    def _assert_hospital_allowed(self, hospital, user):
        if hospital is not None and user.is_hospital and hospital.pk != user.hospital_id:
            raise PermissionDenied(
                "Hospital accounts may only create or modify requests for their own hospital."
            )

    def create(self, validated_data):
        user = self.context["request"].user
        hospital = validated_data.get("hospital")
        if hospital is None:
            if user.is_hospital:
                hospital = Hospital.objects.get(pk=user.hospital_id)
            else:
                raise ValidationError(
                    {"hospital_id": "Administrators must specify a hospital_id."}
                )
        else:
            self._assert_hospital_allowed(hospital, user)
        validated_data["hospital"] = hospital

        now = timezone.now()
        validated_data["created_at"] = now
        validated_data["updated_at"] = now
        validated_data["requester_profile_id"] = user.id
        return BloodRequest.objects.create(**validated_data)

    def update(self, instance, validated_data):
        user = self.context["request"].user
        if "hospital" in validated_data:
            self._assert_hospital_allowed(validated_data["hospital"], user)
        validated_data["updated_at"] = timezone.now()
        return super().update(instance, validated_data)
