from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    ActivityLevel,
    CutIntensity,
    Equipment,
    EntrySource,
    ExerciseKind,
    ExerciseLevel,
    FoodCategory,
    MealType,
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
    cut_intensity: CutIntensity = CutIntensity.moderate
    diet_enabled: bool = False
    scale_mac: str | None = None


class ProfileOut(BaseModel):
    height_cm: float
    weight_kg: float | None
    birthdate: date
    sex: Sex
    activity_level: ActivityLevel
    objective: Objective
    cut_intensity: CutIntensity
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


# Campos de composicao corporal informados pela balanca (todos opcionais).
# Reutilizados na entrada (WeightLogIn) e na saida (WeightLogOut).
class BodyCompositionFields(BaseModel):
    fat_percentage: float | None = Field(default=None, ge=0, le=80)  # gordura em %
    fat_mass_kg: float | None = Field(default=None, ge=0, le=300)  # gordura em kg
    skeletal_muscle_percentage: float | None = Field(default=None, ge=0, le=100)  # musculo esqueletico %
    skeletal_muscle_kg: float | None = Field(default=None, ge=0, le=200)  # musculo esqueletico kg
    muscle_percentage: float | None = Field(default=None, ge=0, le=100)  # musculo total %
    muscle_mass_kg: float | None = Field(default=None, ge=0, le=200)  # musculo total kg
    water_percentage: float | None = Field(default=None, ge=0, le=100)  # agua corporal %
    water_mass_kg: float | None = Field(default=None, ge=0, le=200)  # agua em kg
    visceral_fat_index: float | None = Field(default=None, ge=0, le=60)  # V-fat = gordura visceral
    scale_bmr_kcal: int | None = Field(default=None, ge=0, le=5000)  # BMR estimado pela balanca


class WeightLogIn(BodyCompositionFields):
    weight_kg: float = Field(gt=20, lt=400)
    source: WeightSource = WeightSource.manual
    logged_at: datetime | None = None


class WeightLogOut(BodyCompositionFields):
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
    # ultimo weigh-in que trouxe composicao corporal (para o painel de composicao)
    latest_body_composition: WeightLogOut | None = None


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


class WeekSummaryOut(BaseModel):
    workouts: int
    total_volume_kg: float
    total_sets: int
    avg_kcal: int
    days_logged_diet: int
    avg_water_ml: int
    days_with_water: int


class CoachNote(BaseModel):
    # code = mensagem traduzida no frontend; severity controla a cor (warn/info).
    code: str
    severity: str  # "warn" | "info"


class CoachOut(BaseModel):
    notes: list[CoachNote]
    # dias desde a ultima pesagem (None = nunca pesou). Alimenta o lembrete de pesagem.
    days_since_weigh_in: int | None


class AdaptiveTdeeOut(BaseModel):
    # Resultado do TDEE adaptativo: manutencao real estimada pelos dados do usuario.
    has_enough_data: bool
    span_days: int  # dias entre a primeira e a ultima pesagem analisada
    days_logged: int  # dias com diario alimentar na janela
    avg_intake_kcal: int  # media diaria consumida
    weekly_change_kg: float  # variacao de peso por semana (negativo = perdendo)
    estimated_maintenance_kcal: int | None  # manutencao REAL estimada
    formula_tdee_kcal: int  # manutencao ESTIMADA pela formula (para comparar)
    current_target_kcal: int  # meta atual (baseada na formula)
    suggested_target_kcal: int | None  # meta sugerida com base na manutencao real
    # codigo traduzido no frontend: NOT_ENOUGH_DATA, ON_TRACK, TOO_SLOW, STALLED,
    # TOO_FAST, ESTIMATE_READY
    message_code: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailChange(BaseModel):
    new_email: EmailStr
    current_password: str | None = None  # opcional: a troca de e-mail nao exige senha


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


# --- Dieta ----------------------------------------------------------------


class MacrosOut(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class FoodPortionOut(BaseModel):
    label_key: str
    grams: float


class FoodOut(BaseModel):
    id: int
    slug: str
    name: str
    category: FoodCategory
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    default_portion_g: float
    portions: list[FoodPortionOut]
    is_custom: bool


class FoodIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: FoodCategory = FoodCategory.other
    kcal: float = Field(ge=0, le=1000)
    protein_g: float = Field(ge=0, le=100)
    carbs_g: float = Field(ge=0, le=100)
    fat_g: float = Field(ge=0, le=100)
    default_portion_g: float = Field(default=100, gt=0, le=2000)


class RecipeIngredientIn(BaseModel):
    food_id: int
    grams: float = Field(gt=0, le=5000)


class RecipeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    servings: int = Field(default=1, ge=1, le=50)
    ingredients: list[RecipeIngredientIn]


class RecipeIngredientOut(BaseModel):
    id: int
    food: FoodOut
    grams: float
    macros: MacrosOut


class RecipeOut(BaseModel):
    id: int
    name: str
    servings: int
    ingredients: list[RecipeIngredientOut]
    total: MacrosOut
    per_serving: MacrosOut


class DiaryEntryIn(BaseModel):
    entry_date: date
    meal_type: MealType
    source: EntrySource
    food_id: int | None = None
    recipe_id: int | None = None
    quantity: float = Field(gt=0, le=5000)


class DiaryEntryUpdate(BaseModel):
    quantity: float = Field(gt=0, le=5000)


class DiaryEntryOut(BaseModel):
    id: int
    meal_type: MealType
    source: EntrySource
    food_id: int | None
    recipe_id: int | None
    name: str
    quantity: float
    macros: MacrosOut


class MealGroupOut(BaseModel):
    meal_type: MealType
    entries: list[DiaryEntryOut]
    subtotal: MacrosOut


class DiaryDayOut(BaseModel):
    date: date
    meals: list[MealGroupOut]
    totals: MacrosOut
    goals: MacrosOut | None
