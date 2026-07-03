from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    ActivityLevel,
    Equipment,
    ExerciseKind,
    ExerciseLevel,
    MuscleGroup,
    Objective,
    Plan,
    Sex,
    WeightSource,
)


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


# --- Treino ---------------------------------------------------------------


class ExerciseOut(BaseModel):
    id: int
    slug: str
    name: str
    muscle_group: MuscleGroup
    equipment: Equipment
    kind: ExerciseKind
    level: ExerciseLevel | None
    media_urls: list[str]
    is_custom: bool


class RoutineItemIn(BaseModel):
    exercise_id: int
    target_sets: int = Field(default=3, ge=1, le=20)
    target_reps: int = Field(default=10, ge=0, le=100)
    target_weight_kg: float | None = Field(default=None, ge=0, le=1000)
    target_duration_min: int | None = Field(default=None, ge=1, le=300)
    rest_seconds: int = Field(default=90, ge=0, le=600)


class RoutineIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    items: list[RoutineItemIn]


class RoutineItemOut(BaseModel):
    id: int
    exercise: ExerciseOut
    position: int
    target_sets: int
    target_reps: int
    target_weight_kg: float | None
    target_duration_min: int | None
    rest_seconds: int
    last_weight_kg: float | None = None


class RoutineOut(BaseModel):
    id: int
    name: str
    position: int
    items: list[RoutineItemOut]


class SetLogIn(BaseModel):
    exercise_id: int
    set_number: int = Field(ge=1, le=50)
    reps: int = Field(default=0, ge=0, le=100)
    weight_kg: float = Field(default=0, ge=0, le=1000)
    duration_min: float | None = Field(default=None, ge=0, le=600)
    done: bool = True


class SetLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    set_number: int
    reps: int
    weight_kg: float
    duration_min: float | None
    done: bool


class SessionStartIn(BaseModel):
    routine_id: int | None = None


class SessionOut(BaseModel):
    id: int
    routine_id: int | None
    routine_name: str | None
    started_at: datetime
    finished_at: datetime | None
    sets: list[SetLogOut]


class SessionSummaryOut(BaseModel):
    id: int
    routine_name: str | None
    started_at: datetime
    finished_at: datetime | None
    total_sets: int
    total_volume_kg: float
