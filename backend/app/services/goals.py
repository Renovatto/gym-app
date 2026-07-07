"""Motor de metas (fonte unica das formulas).

Siglas:
  BMR  (Basal Metabolic Rate)         = taxa metabolica basal, gasto em repouso.
  TDEE (Total Daily Energy Expenditure) = gasto energetico total do dia.
  BMI  (Body Mass Index)              = IMC, indice de massa corporal.
"""

from datetime import date

from ..models import ActivityLevel, CutIntensity, Objective, Profile, Sex
from ..schemas import GoalsOut

# Fator de atividade multiplica o BMR para chegar ao TDEE. Ja embute o exercicio
# de forma media (por isso nao somamos calorias de treino por cima).
ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.sedentary: 1.2,
    ActivityLevel.light: 1.375,
    ActivityLevel.moderate: 1.55,
    ActivityLevel.active: 1.725,
    ActivityLevel.very_active: 1.9,
}

# Multiplicador aplicado ao TDEE por objetivo. O lose_fat NAO usa esta tabela: o
# deficit dele vem da taxa de perda escolhida (ver WEEKLY_LOSS_RATE_PCT abaixo).
KCAL_MULTIPLIER: dict[Objective, float] = {
    Objective.lose_fat: 0.80,  # fallback; na pratica usamos a taxa de perda
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

# Taxa alvo de perda de peso por semana, em % do peso corporal, por intensidade.
# Ex.: moderate = 0.5% => quem pesa 80 kg mira ~0.4 kg/semana.
WEEKLY_LOSS_RATE_PCT: dict[CutIntensity, float] = {
    CutIntensity.light: 0.25,
    CutIntensity.moderate: 0.5,
    CutIntensity.aggressive: 0.75,
}

# Energia por kg de gordura corporal. Valor classico usado para converter deficit
# calorico em perda de peso (1 kg de gordura ~ 7700 kcal).
KCAL_PER_KG_FAT = 7700

FAT_KCAL_SHARE = 0.25  # gordura da dieta = 25% das calorias-alvo
WATER_ML_PER_KG = 35  # meta de agua = 35 ml por kg de peso
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9


def water_goal_ml(weight_kg: float) -> int:
    return round(weight_kg * WATER_ML_PER_KG)


def age_from_birthdate(birthdate: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - birthdate.year - (
        (today.month, today.day) < (birthdate.month, birthdate.day)
    )


def basal_metabolic_rate(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """BMR pela formula de Mifflin-St Jeor (kcal/dia)."""
    sex_constant = 5 if sex == Sex.male else -161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + sex_constant


def daily_deficit_for_cut(weight_kg: float, intensity: CutIntensity) -> float:
    """Deficit calorico diario para atingir a taxa de perda escolhida.

    Passos:
      1. taxa semanal (kg) = peso * (taxa% / 100)
      2. deficit semanal (kcal) = taxa semanal * 7700 kcal/kg
      3. deficit diario (kcal) = deficit semanal / 7
    """
    weekly_loss_kg = weight_kg * (WEEKLY_LOSS_RATE_PCT[intensity] / 100)
    weekly_deficit_kcal = weekly_loss_kg * KCAL_PER_KG_FAT
    return weekly_deficit_kcal / 7


def compute_goals(profile: Profile, weight_kg: float) -> GoalsOut:
    age = age_from_birthdate(profile.birthdate)
    bmr = basal_metabolic_rate(weight_kg, profile.height_cm, age, profile.sex)
    tdee = bmr * ACTIVITY_FACTORS[profile.activity_level]

    # Calorias-alvo por objetivo. Perder gordura usa a taxa de perda; os demais
    # objetivos usam o multiplicador simples sobre o TDEE.
    if profile.objective == Objective.lose_fat:
        target_kcal = tdee - daily_deficit_for_cut(weight_kg, profile.cut_intensity)
    else:
        target_kcal = tdee * KCAL_MULTIPLIER[profile.objective]

    # Piso de seguranca: a meta nunca fica abaixo do BMR (comer abaixo do gasto de
    # repouso e insustentavel e acelera a perda de musculo).
    target_kcal = max(target_kcal, bmr)

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
        water_ml=water_goal_ml(weight_kg),
    )
