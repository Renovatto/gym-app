"""Motor de metas: BMR (Mifflin-St Jeor), TDEE, calorias-alvo, macros e água."""

from datetime import date

from ..models import ActivityLevel, Objective, Profile, Sex
from ..schemas import GoalsOut

ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.sedentary: 1.2,
    ActivityLevel.light: 1.375,
    ActivityLevel.moderate: 1.55,
    ActivityLevel.active: 1.725,
    ActivityLevel.very_active: 1.9,
}

# Ajuste calórico e proteína (g/kg) por objetivo.
KCAL_MULTIPLIER: dict[Objective, float] = {
    Objective.lose_fat: 0.80,
    Objective.maintain: 1.0,
    Objective.gain_muscle: 1.10,
    Objective.recomp: 0.90,
}
PROTEIN_G_PER_KG: dict[Objective, float] = {
    Objective.lose_fat: 2.0,
    Objective.maintain: 1.6,
    Objective.gain_muscle: 2.0,
    Objective.recomp: 2.2,
}

FAT_KCAL_SHARE = 0.25
WATER_ML_PER_KG = 35
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9


def age_from_birthdate(birthdate: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - birthdate.year - (
        (today.month, today.day) < (birthdate.month, birthdate.day)
    )


def compute_goals(profile: Profile, weight_kg: float) -> GoalsOut:
    age = age_from_birthdate(profile.birthdate)
    sex_constant = 5 if profile.sex == Sex.male else -161
    bmr = 10 * weight_kg + 6.25 * profile.height_cm - 5 * age + sex_constant
    tdee = bmr * ACTIVITY_FACTORS[profile.activity_level]
    target_kcal = tdee * KCAL_MULTIPLIER[profile.objective]

    protein_g = PROTEIN_G_PER_KG[profile.objective] * weight_kg
    fat_g = target_kcal * FAT_KCAL_SHARE / KCAL_PER_G_FAT
    carbs_kcal = target_kcal - protein_g * KCAL_PER_G_PROTEIN - fat_g * KCAL_PER_G_FAT
    carbs_g = max(carbs_kcal, 0) / KCAL_PER_G_CARB

    height_m = profile.height_cm / 100
    return GoalsOut(
        age=age,
        bmi=round(weight_kg / (height_m * height_m), 1),
        bmr_kcal=round(bmr),
        tdee_kcal=round(tdee),
        target_kcal=round(target_kcal),
        protein_g=round(protein_g),
        fat_g=round(fat_g),
        carbs_g=round(carbs_g),
        water_ml=round(weight_kg * WATER_ML_PER_KG),
    )
