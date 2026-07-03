from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

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


class WeightLogOut(BaseModel):
    id: int
    weight_kg: float
    source: WeightSource
    logged_at: datetime


class LocaleUpdate(BaseModel):
    locale: str = Field(pattern=r"^(pt-BR|en|es)$")
