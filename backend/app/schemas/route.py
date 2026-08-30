import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_ROUTE_COORDINATES = 2
MAX_ROUTE_COORDINATES = 5000  # generous ceiling against an accidentally-enormous polyline


class RouteCreate(BaseModel):
    """POST /trips/{trip_id}/route body. `coordinates` is GeoJSON-order
    [longitude, latitude] pairs — see app/route/matcher.py's module
    docstring for why that's the deliberate convention here, the opposite
    of most of the rest of this API."""

    name: Optional[str] = Field(None, max_length=255)
    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    coordinates: List[List[float]] = Field(..., min_length=MIN_ROUTE_COORDINATES, max_length=MAX_ROUTE_COORDINATES)
    estimated_duration_seconds: Optional[int] = Field(None, gt=0)

    @field_validator("coordinates")
    @classmethod
    def _validate_coordinate_pairs(cls, value: List[List[float]]) -> List[List[float]]:
        for pair in value:
            if len(pair) != 2:
                raise ValueError("Each coordinate must be a [longitude, latitude] pair.")
            lon, lat = pair
            if not (-180.0 <= lon <= 180.0):
                raise ValueError(f"Invalid longitude: {lon!r}")
            if not (-90.0 <= lat <= 90.0):
                raise ValueError(f"Invalid latitude: {lat!r}")
        return value


class RouteResponse(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    name: Optional[str] = None
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    coordinates: List[List[float]]
    distance_meters: float
    estimated_duration_seconds: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("status", mode="before")
    @classmethod
    def _status_value(cls, value):
        return value.value if hasattr(value, "value") else value


class RouteMemberProgress(BaseModel):
    user_id: uuid.UUID
    name: Optional[str] = None
    role: str
    route_state: Optional[str] = None
    route_fraction: Optional[float] = None
    distance_traveled_meters: Optional[float] = None
    distance_remaining_meters: Optional[float] = None
    distance_from_route_meters: Optional[float] = None
    eta_seconds: Optional[float] = None
    eta_source: Optional[str] = None
    location_age_seconds: Optional[float] = None
    presence: str


class RouteProgressResponse(BaseModel):
    trip_id: uuid.UUID
    route_id: uuid.UUID
    group_route_fraction: Optional[float] = None
    trip_arrived: bool
    leader: Optional[RouteMemberProgress] = None
    members: List[RouteMemberProgress]
