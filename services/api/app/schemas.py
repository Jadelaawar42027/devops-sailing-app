"""Request/response models with validation (R2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

Name = Field(min_length=1, max_length=100)


class BoatIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Name
    max_wind_kn: float = Field(gt=0, le=80, description="Max sustained wind, knots")
    max_gust_kn: float | None = Field(default=None, gt=0, le=100, description="Max gust, knots")
    max_wave_m: float = Field(gt=0, le=15, description="Max significant wave height, metres")

    @model_validator(mode="after")
    def gust_not_below_wind(self) -> "BoatIn":
        if self.max_gust_kn is not None and self.max_gust_kn < self.max_wind_kn:
            raise ValueError("max_gust_kn must be greater than or equal to max_wind_kn")
        return self


class BoatOut(BoatIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PassageIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Name
    boat_id: int = Field(gt=0)
    start_lat: float = Field(ge=-90, le=90)
    start_lon: float = Field(ge=-180, le=180)
    end_lat: float = Field(ge=-90, le=90)
    end_lon: float = Field(ge=-180, le=180)
    speed_kn: float = Field(gt=0, le=40, description="Planned average speed, knots")


class PassageOut(PassageIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
