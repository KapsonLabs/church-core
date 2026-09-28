from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import (
    AgeGroup, Child, ChildAttendance, Event, Facilitator, FacilitatorAttendance,
    ServiceFacilitator, ServiceSession,
)


class CleanModelSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        model = self.Meta.model
        values = {field.name: getattr(self.instance, field.name) for field in model._meta.fields if self.instance and hasattr(self.instance, field.name)}
        values.update(attrs)
        candidate = model(**{key: value for key, value in values.items() if key != "id"})
        try:
            candidate.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class AgeGroupSerializer(CleanModelSerializer):
    class Meta:
        model = AgeGroup
        fields = ["id", "organization", "branch", "name", "minimum_age", "maximum_age", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "organization", "branch", "created_at", "updated_at"]


class ChildSerializer(CleanModelSerializer):
    age = serializers.IntegerField(read_only=True)
    age_group_name = serializers.CharField(source="age_group.name", read_only=True)

    class Meta:
        model = Child
        fields = ["id", "organization", "branch", "first_name", "last_name", "other_names", "date_of_birth", "age", "age_group", "age_group_name", "guardian_name", "guardian_contact", "location", "registration_date", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "organization", "branch", "created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        date_of_birth = attrs.get("date_of_birth", getattr(self.instance, "date_of_birth", None))
        if date_of_birth is None:
            raise serializers.ValidationError({"date_of_birth": "Date of birth is required."})
        return attrs

    def create(self, validated_data):
        validated_data["is_active"] = True
        return super().create(validated_data)


class FacilitatorSerializer(CleanModelSerializer):
    name = serializers.SerializerMethodField()
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    default_age_group_name = serializers.CharField(source="default_age_group.name", read_only=True)

    class Meta:
        model = Facilitator
        fields = ["id", "organization", "branch", "user", "name", "first_name", "last_name", "email", "phone_number", "default_age_group", "default_age_group_name", "is_active", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "organization", "branch", "created_at", "updated_at"]

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update({
            "first_name": instance.user.first_name,
            "last_name": instance.user.last_name,
            "email": instance.user.email,
            "phone_number": instance.user.phone_number,
        })
        return data

    def validate(self, attrs):
        identity = {key: attrs.pop(key) for key in ["first_name", "last_name", "email", "phone_number"] if key in attrs}
        attrs = super().validate(attrs)
        attrs.update(identity)
        user = attrs.get("user") or (self.instance.user if self.instance else None)
        if self.instance and "user" in attrs and attrs["user"].pk != self.instance.user_id:
            raise serializers.ValidationError({"user": "A facilitator cannot be moved to another user account."})
        email = attrs.get("email")
        if email and get_user_model().objects.exclude(pk=getattr(user, "pk", None)).filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})
        return attrs

    def _update_user(self, user, identity):
        for field, value in identity.items():
            setattr(user, field, value)
        if identity:
            user.full_clean(exclude=["password", "username"])
            user.save(update_fields=[*identity, "updated_at"])

    @transaction.atomic
    def create(self, validated_data):
        identity = {key: validated_data.pop(key) for key in ["first_name", "last_name", "email", "phone_number"] if key in validated_data}
        user = validated_data["user"]
        self._update_user(user, identity)
        instance = Facilitator(**validated_data)
        instance.full_clean()
        instance.save()
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        identity = {key: validated_data.pop(key) for key in ["first_name", "last_name", "email", "phone_number"] if key in validated_data}
        validated_data.pop("user", None)
        self._update_user(instance.user, identity)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.full_clean()
        instance.save()
        return instance


class ServiceSessionSerializer(CleanModelSerializer):
    event_name = serializers.CharField(source="event.name", read_only=True)
    event_date = serializers.DateField(source="event.event_date", read_only=True)
    attendance_summary = serializers.SerializerMethodField()
    facilitators_assigned = serializers.IntegerField(source="facilitator_assignments.count", read_only=True)
    facilitators_present = serializers.SerializerMethodField()

    class Meta:
        model = ServiceSession
        fields = ["id", "event", "event_name", "event_date", "service_order", "name", "start_time", "end_time", "location", "notes", "status", "attendance_summary", "facilitators_assigned", "facilitators_present", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_attendance_summary(self, obj):
        counts = {key: 0 for key in ["present", "late", "absent", "excused"]}
        for value in obj.child_attendance.values_list("attendance_status", flat=True):
            counts[value] += 1
        return counts

    def get_facilitators_present(self, obj):
        return obj.facilitator_attendance.filter(attendance_status__in=["present", "late"]).count()


class EventSerializer(CleanModelSerializer):
    sessions = ServiceSessionSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = ["id", "organization", "branch", "name", "event_type", "description", "event_date", "start_time", "end_time", "location", "status", "created_by", "attendance_finalized_at", "attendance_finalized_by", "sessions", "created_at", "updated_at"]
        read_only_fields = ["id", "organization", "branch", "created_by", "attendance_finalized_at", "attendance_finalized_by", "created_at", "updated_at"]


class ChildAttendanceSerializer(CleanModelSerializer):
    child_name = serializers.CharField(source="child.__str__", read_only=True)
    age_group_name = serializers.CharField(source="age_group.name", read_only=True)
    service_name = serializers.CharField(source="service_session.name", read_only=True)
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ChildAttendance
        fields = ["id", "child", "child_name", "event", "service_session", "service_name", "age_group", "age_group_name", "attendance_status", "checked_in_at", "recorded_by", "recorded_by_name", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "age_group", "recorded_by", "created_at", "updated_at"]

    def get_recorded_by_name(self, obj):
        if not obj.recorded_by:
            return None
        return obj.recorded_by.get_full_name() or obj.recorded_by.email


class ServiceFacilitatorSerializer(CleanModelSerializer):
    facilitator_name = serializers.SerializerMethodField()
    facilitator_user = serializers.UUIDField(source="facilitator.user_id", read_only=True)
    service_name = serializers.CharField(source="service_session.name", read_only=True)
    service_date = serializers.DateField(source="service_session.event.event_date", read_only=True)

    class Meta:
        model = ServiceFacilitator
        fields = ["id", "service_session", "service_name", "service_date", "facilitator", "facilitator_name", "facilitator_user", "role", "assigned_by", "created_at"]
        read_only_fields = ["id", "assigned_by", "created_at"]

    def get_facilitator_name(self, obj):
        return str(obj.facilitator)


class FacilitatorAttendanceSerializer(CleanModelSerializer):
    facilitator_name = serializers.SerializerMethodField()

    class Meta:
        model = FacilitatorAttendance
        fields = ["id", "service_session", "facilitator", "facilitator_name", "attendance_status", "checked_in_at", "recorded_by", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "recorded_by", "created_at", "updated_at"]

    def get_facilitator_name(self, obj):
        return str(obj.facilitator)


class SundaySessionInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    service_order = serializers.IntegerField(min_value=1)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField(required=False, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class SundayCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    sunday_date = serializers.DateField()
    name = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    sessions = SundaySessionInputSerializer(many=True, min_length=1)

    def validate(self, attrs):
        if attrs["sunday_date"].weekday() != 6:
            raise serializers.ValidationError({"sunday_date": "Date must be a Sunday."})
        orders = [item["service_order"] for item in attrs["sessions"]]
        names = [item["name"].casefold() for item in attrs["sessions"]]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError({"sessions": "Service orders must be unique."})
        if len(names) != len(set(names)):
            raise serializers.ValidationError({"sessions": "Service names must be unique."})
        for item in attrs["sessions"]:
            if item.get("end_time") and item["end_time"] < item["start_time"]:
                raise serializers.ValidationError({"sessions": f"End time for {item['name']} cannot precede start time."})
        return attrs


class BulkAttendanceRowSerializer(serializers.Serializer):
    child_id = serializers.UUIDField()
    attendance_status = serializers.ChoiceField(choices=ChildAttendance._meta.get_field("attendance_status").choices)
    notes = serializers.CharField(required=False, allow_blank=True)


class BulkAttendanceSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    rows = BulkAttendanceRowSerializer(many=True, required=False, default=list)
    mark_all_present = serializers.BooleanField(required=False, default=False)
    visible_child_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class BulkAssignmentRowSerializer(serializers.Serializer):
    facilitator_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=ServiceFacilitator.Role.choices)


class BulkAssignmentSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    assignments = BulkAssignmentRowSerializer(many=True)


class BulkFacilitatorAttendanceRowSerializer(serializers.Serializer):
    facilitator_id = serializers.UUIDField()
    attendance_status = serializers.ChoiceField(choices=FacilitatorAttendance._meta.get_field("attendance_status").choices)
    notes = serializers.CharField(required=False, allow_blank=True)


class BulkFacilitatorAttendanceSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    rows = BulkFacilitatorAttendanceRowSerializer(many=True)
