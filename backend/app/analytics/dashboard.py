"""
The primary frontend dashboard endpoint — GET /trips/{trip_id}/dashboard.
Composes existing services (never re-implements their logic):

    TripService (via the `trip` argument already resolved by the router)
    RouteService     (app/route/service.py)
    LiveStateService / IntelligenceService (app/intelligence/engine.py)
    AlertService / SOSService (app/alerts/, app/sos/)
    AnalyticsService (app/analytics/route_analytics.py, queries.py)
    RiskService      (app/risk/service.py)
    EtaService       (app/route/eta.py — group ETA)
    WeatherService   (app/weather/service.py)
    NotificationService (app/notifications/service.py)

ACTIVE trips ("live" mode) combine Redis live state with route progress
computed against that live state, plus DB-backed alert/SOS counts.
Any other trip status ("historical" mode) uses PostgreSQL exclusively —
no Redis call is ever made for a non-ACTIVE trip, so historical dashboards
keep working even with Redis completely down. Risk and notifications are
DB-only either way; weather and group ETA are live-only (both need a
current location/speed a finished trip no longer has).
"""

import uuid
from typing import List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.alerts import service as alerts_service
from app.analytics import queries, route_analytics
from app.intelligence import engine as intelligence_engine
from app.intelligence.thresholds import current_thresholds
from app.models.enums import RouteStatus, TripStatus
from app.models.trip import Trip
from app.notifications import service as notification_service
from app.risk.service import calculate_trip_risk
from app.route import progress as route_progress
from app.route import service as route_service
from app.route.eta import EtaService
from app.route.service import MemberRouteProgress
from app.schemas.analytics import (
    DashboardEta,
    DashboardGroup,
    DashboardMember,
    DashboardNotifications,
    DashboardResponse,
    DashboardRisk,
    DashboardRoute,
    DashboardSafety,
    DashboardTrip,
    DashboardWeather,
    DashboardWeatherWarning,
)
from app.schemas.risk import RiskScore
from app.sos import service as sos_service
from app.weather.service import WeatherInfo, WeatherService


def _pick_representative_progress(
    members: List[MemberRouteProgress], leader_id: Optional[uuid.UUID]
) -> Optional[MemberRouteProgress]:
    """Same "leader, else median" representative rule as
    queries.pick_representative_value(), applied to a whole
    MemberRouteProgress object at once so progress_percent/
    distance_remaining_meters/eta_seconds on the dashboard's `route`
    section always come from one consistent member, never mixed."""
    leader_key = str(leader_id) if leader_id is not None else None
    if leader_key is not None:
        for member in members:
            if member.user_id == leader_key and member.match is not None:
                return member

    candidates = [m for m in members if m.match is not None]
    if not candidates:
        return None
    candidates.sort(key=lambda m: m.match.route_fraction)
    return candidates[len(candidates) // 2]


def _weather_to_dashboard(weather: WeatherInfo) -> DashboardWeather:
    return DashboardWeather(
        weather_available=weather.weather_available,
        temperature_celsius=weather.temperature_celsius,
        condition=weather.condition,
        wind_speed_mps=weather.wind_speed_mps,
        precipitation_probability_percent=weather.precipitation_probability_percent,
        visibility_meters=weather.visibility_meters,
        warnings=[DashboardWeatherWarning(type=w.type, severity=w.severity, reason=w.reason) for w in weather.warnings],
    )


def _risk_to_dashboard(risk: RiskScore) -> DashboardRisk:
    return DashboardRisk(score=risk.score, level=risk.level)


async def build_dashboard(db: Session, redis: Optional[Redis], trip: Trip, viewer_user_id: uuid.UUID) -> DashboardResponse:
    if trip.status == TripStatus.ACTIVE:
        return await _build_live_dashboard(db, redis, trip, viewer_user_id)
    return _build_historical_dashboard(db, trip, viewer_user_id)


async def _build_live_dashboard(db: Session, redis: Optional[Redis], trip: Trip, viewer_user_id: uuid.UUID) -> DashboardResponse:
    route = route_service.get_route_by_trip(db, trip.id)
    leader_id = queries.get_group_leader_id(db, trip.group_id)

    # Redis being unreachable degrades this to whatever PostgreSQL alone
    # can answer, rather than failing the whole dashboard — every
    # Redis-only field below simply becomes None instead.
    computed = None
    if redis is not None:
        computed = await intelligence_engine.compute_current_state(db, redis, trip.id, trip.group_id)

    route_progress_members: List[MemberRouteProgress] = []
    if redis is not None and route is not None and route.status == RouteStatus.ACTIVE:
        route_progress_members, _group_fraction, _trip_arrived = await route_service.get_live_route_progress(
            db, redis, trip, route
        )
    route_state_by_user = {m.user_id: m.route_state for m in route_progress_members}
    fraction_by_user = {m.user_id: m.match.route_fraction for m in route_progress_members if m.match}

    representative = _pick_representative_progress(route_progress_members, leader_id)
    dashboard_route = DashboardRoute(
        route_available=route is not None,
        distance_meters=round(route.distance_meters) if route is not None else None,
        progress_percent=(
            round(representative.match.route_fraction * 100, 1) if representative and representative.match else None
        ),
        distance_remaining_meters=(
            round(representative.match.distance_remaining_meters) if representative and representative.match else None
        ),
        eta_seconds=representative.eta.eta_seconds if representative and representative.eta else None,
    )

    active_alerts = alerts_service.list_active_alerts(db, trip.id)
    active_sos = sos_service.list_active_sos(db, trip.id)
    critical_alerts = sum(1 for a in active_alerts if a.severity.value == "CRITICAL")

    members: List[DashboardMember] = []
    speed_by_user = {}
    if computed is not None:
        for cm in computed.members:
            speed_by_user[cm.user_id] = cm.speed
            fraction = fraction_by_user.get(cm.user_id)
            members.append(
                DashboardMember(
                    user_id=uuid.UUID(cm.user_id),
                    name=cm.name,
                    movement_state=cm.movement_state,
                    route_state=route_state_by_user.get(cm.user_id),
                    progress_percent=round(fraction * 100, 1) if fraction is not None else None,
                    distance_from_group_center_meters=cm.distance_from_group_center_meters,
                )
            )
        member_count = len(computed.members)
        online_count = sum(1 for m in computed.members if m.presence == "ONLINE")
        moving_count = sum(1 for m in computed.members if m.movement_state == "MOVING")
        stopped_count = sum(1 for m in computed.members if m.movement_state == "STOPPED")
    else:
        group_members = queries.list_active_group_members(db, trip.group_id)
        members = [DashboardMember(user_id=m["user_id"], name=m["name"]) for m in group_members]
        member_count = len(group_members)
        online_count = moving_count = stopped_count = None

    # --- Risk (Phase 12) — DB-only, plus the live online/member ratio
    # when we actually have it (never fabricated otherwise). ---
    risk = calculate_trip_risk(db, trip, online_count=online_count, member_count=member_count)

    # --- Group ETA (Phase 12) — median remaining distance / median
    # moving-member speed, from the same route_progress_members this
    # function already computed; never re-queries anything. ---
    dashboard_eta = _build_dashboard_eta(representative, route_progress_members, speed_by_user, route)

    # --- Weather (Phase 12) — the representative member's live
    # location, if any; entirely optional, never blocks the dashboard. ---
    dashboard_weather = await _build_dashboard_weather(redis, computed, leader_id)

    unread_count = notification_service.get_unread_count(db, viewer_user_id)

    return DashboardResponse(
        mode="live",
        trip=DashboardTrip(id=trip.id, name=trip.destination_name, status=trip.status.value, started_at=trip.started_at),
        route=dashboard_route,
        group=DashboardGroup(
            member_count=member_count, online_count=online_count, moving_count=moving_count, stopped_count=stopped_count
        ),
        safety=DashboardSafety(
            active_alerts=len(active_alerts), critical_alerts=critical_alerts, active_sos=len(active_sos)
        ),
        members=members,
        risk=_risk_to_dashboard(risk),
        eta=dashboard_eta,
        weather=dashboard_weather,
        notifications=DashboardNotifications(unread_count=unread_count),
    )


def _build_dashboard_eta(
    representative: Optional[MemberRouteProgress],
    route_progress_members: List[MemberRouteProgress],
    speed_by_user: dict,
    route,
) -> DashboardEta:
    individual_eta = representative.eta if representative else None
    thresholds = current_thresholds()

    group_inputs: List[Tuple[float, Optional[float]]] = [
        (m.match.distance_remaining_meters, speed_by_user.get(m.user_id))
        for m in route_progress_members
        if m.match is not None
    ]
    group_result = None
    if route is not None and group_inputs:
        group_result = EtaService.calculate_group_eta(
            members=group_inputs,
            route_distance_meters=route.distance_meters,
            route_estimated_duration_seconds=route.estimated_duration_seconds,
            thresholds=thresholds,
        )

    return DashboardEta(
        eta_available=bool(individual_eta and individual_eta.eta_available),
        eta_seconds=individual_eta.eta_seconds if individual_eta else None,
        group_eta_available=bool(group_result and group_result.eta_available),
        group_eta_seconds=group_result.eta_seconds if group_result else None,
        source=individual_eta.source if individual_eta else None,
    )


async def _build_dashboard_weather(redis: Optional[Redis], computed, leader_id: Optional[uuid.UUID]) -> DashboardWeather:
    if redis is None or computed is None:
        return DashboardWeather(weather_available=False)

    location = None
    leader_key = str(leader_id) if leader_id is not None else None
    for cm in computed.members:
        if leader_key is not None and cm.user_id == leader_key and cm.latitude is not None:
            location = (cm.latitude, cm.longitude)
            break
    if location is None:
        for cm in computed.members:
            if cm.latitude is not None and cm.longitude is not None:
                location = (cm.latitude, cm.longitude)
                break

    if location is None:
        return DashboardWeather(weather_available=False)

    weather = await WeatherService.get_weather(redis, location[0], location[1])
    return _weather_to_dashboard(weather)


def _build_historical_dashboard(db: Session, trip: Trip, viewer_user_id: uuid.UUID) -> DashboardResponse:
    group_members = queries.list_active_group_members(db, trip.group_id)
    points_by_user = queries.fetch_location_points(db, trip.id)
    movement_by_user = queries.fetch_movement_intervals_by_user(db, trip.id)
    leader_id = queries.get_group_leader_id(db, trip.group_id)
    route = route_service.get_route_by_trip(db, trip.id)

    completion_percent = distance_remaining = None
    if route is not None:
        completion_percent, distance_remaining, _arrived = route_analytics.compute_route_completion(
            route, points_by_user, leader_id
        )

    dashboard_route = DashboardRoute(
        route_available=route is not None,
        distance_meters=round(route.distance_meters) if route is not None else None,
        progress_percent=completion_percent,
        distance_remaining_meters=round(distance_remaining) if distance_remaining is not None else None,
        # A finished trip has no ETA left to reach — always None here,
        # never a stale leftover number.
        eta_seconds=None,
    )

    active_alerts = alerts_service.list_active_alerts(db, trip.id)
    active_sos = sos_service.list_active_sos(db, trip.id)
    critical_alerts = sum(1 for a in active_alerts if a.severity.value == "CRITICAL")

    thresholds = current_thresholds()
    members: List[DashboardMember] = []
    for member in group_members:
        uid_str = str(member["user_id"])
        points = points_by_user.get(uid_str, [])
        intervals = movement_by_user.get(uid_str, [])
        last_movement_state = intervals[-1][0] if intervals else None

        route_state = None
        progress_percent = None
        if route is not None:
            match = route_analytics.match_last_point(route, points)
            if match is not None:
                confirmed_arrived = match.distance_remaining_meters <= thresholds.arrival_threshold_meters
                route_state = route_progress.classify_route_state(
                    distance_from_route_meters=match.distance_from_route_meters,
                    distance_remaining_meters=match.distance_remaining_meters,
                    confirmed_arrived=confirmed_arrived,
                    thresholds=thresholds,
                )
                progress_percent = round(match.route_fraction * 100, 1)

        members.append(
            DashboardMember(
                user_id=member["user_id"],
                name=member["name"],
                movement_state=last_movement_state,
                route_state=route_state,
                progress_percent=progress_percent,
                # Group-center distance is a live-only Phase 7 computation
                # (never persisted) — unavailable once a trip is over.
                distance_from_group_center_meters=None,
            )
        )

    risk = calculate_trip_risk(db, trip)
    unread_count = notification_service.get_unread_count(db, viewer_user_id)

    return DashboardResponse(
        mode="historical",
        trip=DashboardTrip(id=trip.id, name=trip.destination_name, status=trip.status.value, started_at=trip.started_at),
        route=dashboard_route,
        group=DashboardGroup(
            member_count=len(group_members), online_count=None, moving_count=None, stopped_count=None
        ),
        safety=DashboardSafety(
            active_alerts=len(active_alerts), critical_alerts=critical_alerts, active_sos=len(active_sos)
        ),
        members=members,
        risk=_risk_to_dashboard(risk),
        # A finished trip has no ETA, and no current location to fetch
        # weather for — both are live-only concepts.
        eta=DashboardEta(eta_available=False, eta_seconds=None, group_eta_available=False, group_eta_seconds=None, source=None),
        weather=DashboardWeather(weather_available=False),
        notifications=DashboardNotifications(unread_count=unread_count),
    )
