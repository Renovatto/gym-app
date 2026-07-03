from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import ActivityLevel, Objective, Plan, Sex, WeightSource


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    locale: str = "pt-BR"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    locale: str
    plan: Plan
    has_profile: bool


class ProfileIn(BaseModel):
    height_cm: float = Field(gt=50, lt=280)
    weight_kg: float = Field(gt=20, lt=400)
    birthdate: date
    sex: Sex
    activity_level: ActivityLevel
    objective: Objective
    diet_enabled: bool = False
    scale_mac: str | None = None


class ProfileOut(BaseModel):
    height_cm: float
    weight_kg: float | None
    birthdate: date
    sex: Sex
    activity_level: ActivityLevel
    objective: Objective
    diet_enabled: bool
    scale_mac: str | None


class GoalsOut(BaseModel):
    age: int
    bmi: float
    bmr_kcal: int
    tdee_kcal: int
    target_kcal: int
    protein_g: int
    fat_g: int
    carbs_g: int
    water_ml: int


class WeightLogIn(BaseModel):
    weight_kg: float = Field(gt=20, lt=400)
    source: WeightSource = WeightSource.manual
    logged_at: datetime | None = None


class WeightLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weight_kg: float
    source: WeightSource
    logged_at: datetime


class WeightHistoryOut(BaseModel):
    logs: list[WeightLogOut]
    current_kg: float | None
    start_kg: float | None
    delta_kg: float | None


class WaterLogIn(BaseModel):
    amount_ml: int = Field(gt=0, le=5000)


class WaterLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_ml: int
    logged_at: datetime


class WaterDayOut(BaseModel):
    date: date
    total_ml: int
    goal_ml: int
    logs: list[WaterLogOut]


class LocaleUpdate(BaseModel):
    locale: str = Field(pattern=r"^(pt-BR|en|es)$")
