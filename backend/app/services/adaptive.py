"""TDEE adaptativo: estima a manutencao calorica REAL do usuario cruzando o que ele
comeu (diario alimentar) com como o peso mudou (tendencia), corrigindo o erro da
formula de estimativa.

Ideia central (balanco energetico):
  Se em media voce comeu X kcal/dia e o peso caiu, voce estava em deficit. Convertendo:
  - 1 kg de peso corporal ~ 7700 kcal (KCAL_PER_KG_FAT em goals.py).
  - inclinacao da reta de peso (kg por dia) * 7700 = balanco diario em kcal.
  - manutencao real = media comida - balanco diario.
    (peso caindo => balanco negativo => manutencao MAIOR do que voce comeu)

Precisamos de dados suficientes para a estimativa fazer sentido: varias pesagens
espalhadas e varios dias de diario. Sem isso, retornamos has_enough_data=False.

Siglas: TDEE (Total Daily Energy Expenditure) = gasto total do dia; aqui tratado como
a manutencao calorica (calorias para manter o peso).
"""

from dataclasses import dataclass

# Minimos para confiar na estimativa (janela tipica de ~14 dias).
MIN_SPAN_DAYS = 10  # distancia minima entre a primeira e a ultima pesagem
MIN_WEIGH_INS = 3  # numero minimo de pesagens na janela
MIN_DAYS_LOGGED = 8  # numero minimo de dias com diario alimentar


@dataclass
class AdaptiveEstimate:
    has_enough_data: bool
    span_days: int  # dias entre a primeira e a ultima pesagem analisada
    days_logged: int  # dias com diario alimentar na janela
    avg_intake_kcal: int  # media diaria consumida
    weekly_change_kg: float  # variacao de peso por semana (negativo = perdendo)
    estimated_maintenance_kcal: int | None  # manutencao real estimada


def weight_slope_kg_per_day(weigh_ins: list[tuple[float, float]]) -> float:
    """Inclinacao da reta de peso por dia, via minimos quadrados (regressao linear).

    Cada item e (dia_indice, peso_kg). Regressao suaviza o ruido do dia a dia
    (agua, comida) melhor do que comparar so a primeira com a ultima pesagem.

    slope = soma((x - media_x) * (y - media_y)) / soma((x - media_x)^2)
    """
    n = len(weigh_ins)
    mean_x = sum(x for x, _ in weigh_ins) / n
    mean_y = sum(y for _, y in weigh_ins) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in weigh_ins)
    denominator = sum((x - mean_x) ** 2 for x, _ in weigh_ins)
    if denominator == 0:  # todas as pesagens no mesmo dia
        return 0.0
    return numerator / denominator


def estimate_maintenance(
    weigh_ins: list[tuple[float, float]],
    daily_intakes: list[float],
    kcal_per_kg_fat: int,
) -> AdaptiveEstimate:
    """Estima a manutencao real. weigh_ins = [(dia_indice, peso_kg)] ordenados;
    daily_intakes = kcal total de cada dia que teve diario."""
    days_logged = len(daily_intakes)
    span_days = int(weigh_ins[-1][0] - weigh_ins[0][0]) if len(weigh_ins) >= 2 else 0

    enough = (
        len(weigh_ins) >= MIN_WEIGH_INS
        and span_days >= MIN_SPAN_DAYS
        and days_logged >= MIN_DAYS_LOGGED
    )
    avg_intake = round(sum(daily_intakes) / days_logged) if days_logged else 0

    if not enough:
        return AdaptiveEstimate(
            has_enough_data=False,
            span_days=span_days,
            days_logged=days_logged,
            avg_intake_kcal=avg_intake,
            weekly_change_kg=0.0,
            estimated_maintenance_kcal=None,
        )

    slope_per_day = weight_slope_kg_per_day(weigh_ins)  # kg/dia
    # balanco diario em kcal: peso subindo => superavit (positivo)
    daily_energy_balance = slope_per_day * kcal_per_kg_fat
    # manutencao real = o que comeu menos o balanco (peso caindo aumenta a manutencao)
    estimated_maintenance = round(avg_intake - daily_energy_balance)

    return AdaptiveEstimate(
        has_enough_data=True,
        span_days=span_days,
        days_logged=days_logged,
        avg_intake_kcal=avg_intake,
        weekly_change_kg=round(slope_per_day * 7, 2),
        estimated_maintenance_kcal=estimated_maintenance,
    )
