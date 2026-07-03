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


class Plan(str, Enum):
    free = "free"
    premium = "premium"


class WeightSource(str, Enum):
    manual = "manual"
    ble = "ble"


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
