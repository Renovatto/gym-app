from datetime import date, datetime, timezone
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Sex(str, Enum):
    male = "male"
    female = "female"


class ActivityLevel(str, Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class Objective(str, Enum):
    lose_fat = "lose_fat"
    maintain = "maintain"
    gain_muscle = "gain_muscle"
    recomp = "recomp"  # ganhar musculo e perder gordura ao mesmo tempo


class CutIntensity(str, Enum):
    """Intensidade do deficit no objetivo de perder gordura. Cada nivel e uma taxa
    alvo de perda por semana, em % do peso corporal (ver goals.py)."""

    light = "light"  # perda lenta, mais confortavel e melhor para preservar musculo
    moderate = "moderate"  # equilibrio padrao
    aggressive = "aggressive"  # perda rapida, exige disciplina e mais risco de perder musculo


class Plan(str, Enum):
    free = "free"
    premium = "premium"


class WeightSource(str, Enum):
    manual = "manual"
    ble = "ble"


class MuscleGroup(str, Enum):
    chest = "chest"
    back = "back"
    shoulders = "shoulders"
    biceps = "biceps"
    triceps = "triceps"
    legs = "legs"
    glutes = "glutes"
    abs = "abs"
    calves = "calves"
    cardio = "cardio"


class ExerciseKind(str, Enum):
    strength = "strength"
    cardio = "cardio"


class ExerciseLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    expert = "expert"


class Equipment(str, Enum):
    barbell = "barbell"
    dumbbell = "dumbbell"
    machine = "machine"
    cable = "cable"
    bodyweight = "bodyweight"
    kettlebell = "kettlebell"
    band = "band"
    other = "other"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    locale: str = Field(default="pt-BR")
    plan: Plan = Field(default=Plan.free)
    created_at: datetime = Field(default_factory=utcnow)

    profile: "Profile" = Relationship(back_populates="user", cascade_delete=True)
    weight_logs: list["WeightLog"] = Relationship(back_populates="user", cascade_delete=True)
    water_logs: list["WaterLog"] = Relationship(back_populates="user", cascade_delete=True)


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, ondelete="CASCADE")
    height_cm: float
    birthdate: date
    sex: Sex
    activity_level: ActivityLevel
    objective: Objective
    # Intensidade do deficit; so tem efeito quando objective == lose_fat.
    cut_intensity: CutIntensity = Field(default=CutIntensity.moderate)
    diet_enabled: bool = Field(default=False)
    scale_mac: str | None = Field(default=None)

    user: User = Relationship(back_populates="profile")


class WeightLog(SQLModel, table=True):
    """Um registro de pesagem (weigh-in). Alem do peso, guarda opcionalmente a
    composicao corporal informada pela balanca de bioimpedancia (BIA)."""

    __tablename__ = "weight_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    weight_kg: float
    source: WeightSource = Field(default=WeightSource.manual)
    logged_at: datetime = Field(default_factory=utcnow, index=True)

    # Composicao corporal (opcional). Todos vem da balanca; ficam nulos quando o
    # usuario informa so o peso. BIA = bioimpedancia (impreciso no absoluto, bom na tendencia).
    fat_percentage: float | None = Field(default=None)  # gordura corporal em %
    fat_mass_kg: float | None = Field(default=None)  # peso da gordura em kg
    skeletal_muscle_percentage: float | None = Field(default=None)  # massa muscular esqueletica em %
    skeletal_muscle_kg: float | None = Field(default=None)  # massa muscular esqueletica em kg
    muscle_percentage: float | None = Field(default=None)  # musculo total em %
    muscle_mass_kg: float | None = Field(default=None)  # musculo total em kg
    water_percentage: float | None = Field(default=None)  # agua corporal em %
    water_mass_kg: float | None = Field(default=None)  # peso da agua em kg
    visceral_fat_index: float | None = Field(default=None)  # V-fat = gordura visceral (indice da balanca)
    scale_bmr_kcal: int | None = Field(default=None)  # BMR estimado pela balanca (kcal/dia)

    user: User = Relationship(back_populates="weight_logs")


class WaterLog(SQLModel, table=True):
    __tablename__ = "water_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    amount_ml: int
    logged_at: datetime = Field(default_factory=utcnow, index=True)

    user: User = Relationship(back_populates="water_logs")


class Exercise(SQLModel, table=True):
    __tablename__ = "exercises"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    muscle_group: MuscleGroup = Field(index=True)
    equipment: Equipment
    kind: ExerciseKind = Field(default=ExerciseKind.strength, index=True)
    level: ExerciseLevel | None = Field(default=None, index=True)
    media_url: str | None = Field(default=None)
    media_url2: str | None = Field(default=None)
    # None = exercício global (catálogo); preenchido = exercício criado pelo usuário.
    user_id: int | None = Field(default=None, foreign_key="users.id", ondelete="CASCADE")

    translations: list["ExerciseTranslation"] = Relationship(
        back_populates="exercise", cascade_delete=True
    )


class ExerciseTranslation(SQLModel, table=True):
    __tablename__ = "exercise_translations"

    id: int | None = Field(default=None, primary_key=True)
    exercise_id: int = Field(foreign_key="exercises.id", index=True, ondelete="CASCADE")
    locale: str = Field(index=True)
    name: str

    exercise: Exercise = Relationship(back_populates="translations")


class Routine(SQLModel, table=True):
    __tablename__ = "routines"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    name: str
    position: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)

    items: list["RoutineExercise"] = Relationship(back_populates="routine", cascade_delete=True)


class RoutineExercise(SQLModel, table=True):
    __tablename__ = "routine_exercises"

    id: int | None = Field(default=None, primary_key=True)
    routine_id: int = Field(foreign_key="routines.id", index=True, ondelete="CASCADE")
    exercise_id: int = Field(foreign_key="exercises.id")
    position: int = Field(default=0)
    target_sets: int = Field(default=3)
    target_reps: int = Field(default=10)
    target_weight_kg: float | None = Field(default=None)
    target_duration_min: int | None = Field(default=None)  # cardio
    rest_seconds: int = Field(default=90)

    routine: Routine = Relationship(back_populates="items")


class WorkoutSession(SQLModel, table=True):
    __tablename__ = "workout_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    routine_id: int | None = Field(default=None, foreign_key="routines.id")
    routine_name: str | None = Field(default=None)
    started_at: datetime = Field(default_factory=utcnow, index=True)
    finished_at: datetime | None = Field(default=None)

    sets: list["SetLog"] = Relationship(back_populates="session", cascade_delete=True)


class SetLog(SQLModel, table=True):
    __tablename__ = "set_logs"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="workout_sessions.id", index=True, ondelete="CASCADE")
    exercise_id: int = Field(foreign_key="exercises.id", index=True)
    set_number: int
    reps: int
    weight_kg: float
    duration_min: float | None = Field(default=None)  # cardio
    done: bool = Field(default=True)
    logged_at: datetime = Field(default_factory=utcnow)

    session: WorkoutSession = Relationship(back_populates="sets")


class FoodCategory(str, Enum):
    protein = "protein"
    carb = "carb"
    fruit = "fruit"
    vegetable = "vegetable"
    dairy = "dairy"
    legume = "legume"
    fat = "fat"
    beverage = "beverage"
    sweet = "sweet"
    other = "other"


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    snack = "snack"
    dinner = "dinner"
    other = "other"


class EntrySource(str, Enum):
    food = "food"
    recipe = "recipe"


class Food(SQLModel, table=True):
    __tablename__ = "foods"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    category: FoodCategory = Field(index=True)
    # Valores nutricionais por 100 g (ou 100 ml para líquidos).
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    default_portion_g: float = Field(default=100)
    # None = alimento global (catálogo); preenchido = criado pelo usuário.
    user_id: int | None = Field(default=None, foreign_key="users.id", ondelete="CASCADE")

    translations: list["FoodTranslation"] = Relationship(
        back_populates="food", cascade_delete=True
    )
    portions: list["FoodPortion"] = Relationship(back_populates="food", cascade_delete=True)


class FoodTranslation(SQLModel, table=True):
    __tablename__ = "food_translations"

    id: int | None = Field(default=None, primary_key=True)
    food_id: int = Field(foreign_key="foods.id", index=True, ondelete="CASCADE")
    locale: str = Field(index=True)
    name: str = Field(index=True)

    food: Food = Relationship(back_populates="translations")


class FoodPortion(SQLModel, table=True):
    __tablename__ = "food_portions"

    id: int | None = Field(default=None, primary_key=True)
    food_id: int = Field(foreign_key="foods.id", index=True, ondelete="CASCADE")
    # chave traduzível: unit, slice, tbsp, tsp, cup, glass, scoop, filet, handful, portion
    label_key: str
    grams: float

    food: Food = Relationship(back_populates="portions")


class Recipe(SQLModel, table=True):
    __tablename__ = "recipes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    name: str
    servings: int = Field(default=1)  # quantas porções a receita rende
    created_at: datetime = Field(default_factory=utcnow)

    ingredients: list["RecipeIngredient"] = Relationship(
        back_populates="recipe", cascade_delete=True
    )


class RecipeIngredient(SQLModel, table=True):
    __tablename__ = "recipe_ingredients"

    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipes.id", index=True, ondelete="CASCADE")
    food_id: int = Field(foreign_key="foods.id")
    grams: float

    recipe: Recipe = Relationship(back_populates="ingredients")


class DiaryEntry(SQLModel, table=True):
    __tablename__ = "diary_entries"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    entry_date: date = Field(index=True)  # dia local do usuário
    meal_type: MealType
    source: EntrySource
    food_id: int | None = Field(default=None, foreign_key="foods.id")
    recipe_id: int | None = Field(default=None, foreign_key="recipes.id")
    quantity: float  # gramas (alimento) ou porções (receita)
    # snapshot para preservar o histórico mesmo se o alimento/receita mudar
    name_snapshot: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    logged_at: datetime = Field(default_factory=utcnow)
