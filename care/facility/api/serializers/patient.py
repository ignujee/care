import datetime

from django.db import transaction
from django.utils.timezone import make_aware
from rest_framework import serializers

from care.facility.api.serializers.patient_consultation import PatientConsultationSerializer
from care.facility.models import (
    DISEASE_CHOICES,
    Disease,
    FacilityPatientStatsHistory,
    PatientConsultation,
    PatientRegistration,
    PatientTeleConsultation,
)
from care.users.api.serializers.lsg import DistrictSerializer, LocalBodySerializer, StateSerializer
from config.serializers import ChoiceField


class PatientSerializer(serializers.ModelSerializer):
    class MedicalHistorySerializer(serializers.Serializer):
        disease = ChoiceField(choices=DISEASE_CHOICES)
        details = serializers.CharField(required=False, allow_blank=True)

    medical_history = MedicalHistorySerializer(many=True, required=False)
    last_consultation = serializers.SerializerMethodField()

    local_body_object = LocalBodySerializer(source="local_body", read_only=True)
    district_object = DistrictSerializer(source="district", read_only=True)
    state_object = StateSerializer(source="state", read_only=True)

    def get_last_consultation(self, obj):
        last_consultation = PatientConsultation.objects.filter(patient=obj).last()
        if last_consultation:
            return PatientConsultationSerializer(last_consultation).data
        return None

    class Meta:
        model = PatientRegistration
        exclude = ("created_by", "deleted")

    def create(self, validated_data):
        with transaction.atomic():
            medical_history = validated_data.pop("medical_history", [])
            patient = super().create(validated_data)
            diseases = []
            for disease in medical_history:
                diseases.append(Disease(patient=patient, **disease))
            if diseases:
                Disease.objects.bulk_create(diseases)
            return patient

    def update(self, instance, validated_data):
        with transaction.atomic():
            medical_history = validated_data.pop("medical_history", [])
            patient = super().update(instance, validated_data)
            for disease in medical_history:
                patient.medical_history.update_or_create(disease=disease.pop("disease"), defaults=disease)
            return patient


class PatientTeleConsultationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientTeleConsultation
        fields = "__all__"


class PatientDetailSerializer(PatientSerializer):
    tele_consultation_history = serializers.ListSerializer(child=PatientTeleConsultationSerializer(), read_only=True)


class FacilityPatientStatsHistorySerializer(serializers.ModelSerializer):
    entry_date = serializers.DateField(default=make_aware(datetime.datetime.today()).date())

    class Meta:
        model = FacilityPatientStatsHistory
        exclude = ("deleted",)
        read_only_fields = (
            "id",
            "facility",
        )

    def create(self, validated_data):
        instance, _ = FacilityPatientStatsHistory.objects.update_or_create(
            facility=validated_data["facility"],
            entry_date=validated_data["entry_date"],
            defaults={**validated_data, "deleted": False},
        )
        return instance
