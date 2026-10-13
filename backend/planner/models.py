import uuid

from django.db import models


class TripPlan(models.Model):
    """A planned trip: the request and the full result, so it can be reloaded by id."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    origin = models.JSONField()  # {"lat", "lon", "label"?}
    destination = models.JSONField()
    departure = models.DateTimeField()
    load_lbs = models.FloatField()
    interval_miles = models.PositiveSmallIntegerField()
    recommended_route_id = models.CharField(max_length=1)
    result = models.JSONField()  # the /api/plan response body

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        origin = self.origin.get("label", "origin")
        destination = self.destination.get("label", "destination")
        return f"{origin} → {destination} @ {self.departure:%Y-%m-%d %H:%M}"
