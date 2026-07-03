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
    recomp = "recomp"  # ganhar músculo e perder gordura ao mesmo tempo


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
    diet_enabled: bool = Field(default=False)
    scale_mac: str | None = Field(default=None)

    user: User = Relationship(back_populates="profile")


class WeightLog(SQLModel, table=True):
    __tablename__ = "weight_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    weight_kg: float
    source: WeightSource = Field(default=WeightSource.manual)
    logged_at: datetime = Field(default_factory=utcnow, index=True)

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
    media_url: str | None = Field(default=None)
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
    done: bool = Field(default=True)
    logged_at: datetime = Field(default_factory=utcnow)

    session: WorkoutSession = Relationship(back_populates="sets")
