from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TripPlan
from .serializers import HeatmapRequestSerializer, PlanRequestSerializer
from .services import geocoding
from .services.heatmap import build_heatmap
from .services.planner import plan_trip
from .services.upstream import UpstreamError


class PlannerView(APIView):
    """Base view: an external API failure becomes a JSON `{"detail": ...}` response."""

    def handle_exception(self, exc):
        if isinstance(exc, UpstreamError):
            return Response({"detail": str(exc)}, status=exc.status)
        return super().handle_exception(exc)


class HealthView(PlannerView):
    """Liveness check."""

    def get(self, request):
        return Response({"status": "ok"})


class GeocodeView(PlannerView):
    """Place suggestions for `?q=`."""

    min_query_length = 2

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < self.min_query_length:
            return Response({"results": []})
        return Response({"results": geocoding.search(query)})


class PlanView(PlannerView):
    """Plan a trip, save it, and return the plan with its id."""

    def post(self, request):
        serializer = PlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = plan_trip(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(data["destination"]["lat"], data["destination"]["lon"]),
            departure=data["departure"],
            load_lbs=data["load_lbs"],
            interval_miles=int(data["interval_miles"]),
        )
        saved = TripPlan.objects.create(
            origin=dict(data["origin"]),
            destination=dict(data["destination"]),
            departure=data["departure"],
            load_lbs=data["load_lbs"],
            interval_miles=int(data["interval_miles"]),
            recommended_route_id=result["recommended_route_id"],
            result=result,
        )
        return Response({"id": str(saved.id), **result})


class SavedPlanView(PlannerView):
    """A previously planned trip, by id."""

    def get(self, request, plan_id):
        saved = get_object_or_404(TripPlan, pk=plan_id)
        return Response(
            {"id": str(saved.id), "created_at": saved.created_at.isoformat(), **saved.result}
        )


class HeatmapView(PlannerView):
    """0-48 h weather grid along the trip corridor."""

    def post(self, request):
        serializer = HeatmapRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        lines = [[(lat, lon) for lat, lon in line] for line in data["corridor"]]
        return Response(build_heatmap(lines, data["departure"], data["load_lbs"]))
