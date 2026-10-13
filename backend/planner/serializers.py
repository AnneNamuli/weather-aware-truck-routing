from datetime import UTC, datetime, timedelta

from rest_framework import serializers

MAX_DEPARTURE_AHEAD = timedelta(days=7)
DEPARTURE_GRACE = timedelta(hours=1)


class PointSerializer(serializers.Serializer):
    """A place as latitude/longitude, with an optional display label."""

    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(required=False, allow_blank=True, max_length=200)


def validate_departure(value: datetime) -> datetime:
    """Allow departures from an hour ago up to 7 days ahead (the forecast range); return UTC."""
    now = datetime.now(UTC)
    if value < now - DEPARTURE_GRACE:
        raise serializers.ValidationError("Departure must not be in the past.")
    if value > now + MAX_DEPARTURE_AHEAD:
        raise serializers.ValidationError(
            "Departure must be within the next 7 days (forecast range)."
        )
    return value.astimezone(UTC)


class PlanRequestSerializer(serializers.Serializer):
    """Request body for POST /api/plan."""

    origin = PointSerializer()
    destination = PointSerializer()
    departure = serializers.DateTimeField()
    load_lbs = serializers.FloatField(min_value=0, max_value=100_000)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)

    def validate_departure(self, value):
        """See validate_departure()."""
        return validate_departure(value)

    def validate(self, attrs):
        """Reject trips whose origin and destination are the same place."""
        o, d = attrs["origin"], attrs["destination"]
        if abs(o["lat"] - d["lat"]) < 1e-4 and abs(o["lon"] - d["lon"]) < 1e-4:
            raise serializers.ValidationError("Origin and destination must be different places.")
        return attrs


class HeatmapRequestSerializer(serializers.Serializer):
    """Request body for POST /api/heatmap: up to three simplified route lines."""

    corridor = serializers.ListField(
        child=serializers.ListField(
            child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
            min_length=2,
            max_length=2000,
        ),
        min_length=1,
        max_length=3,
    )
    departure = serializers.DateTimeField()
    load_lbs = serializers.FloatField(min_value=0, max_value=100_000)

    def validate_departure(self, value):
        """See validate_departure()."""
        return validate_departure(value)
