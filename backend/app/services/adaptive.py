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
espalhadas e varios dias de diario COMPLETOS. Sem isso, retornamos has_enough_data=False.

Duas armadilhas do dado de entrada, que ja custaram uma estimativa errada em producao
(manutencao de 1293 kcal para quem gasta 1690 so em repouso):

  1. O dia de HOJE nunca entra na media. Ele esta sempre pela metade - quem abre a tela
     as 14h tem so o cafe e o almoco lancados - e entraria como um dia inteiro de pouca
     comida. O vies e sistematico (sempre para baixo, toda vez que a tela abre), nao
     ruido que se cancela. Quem monta daily_intakes corta a janela em ontem.
  2. Dia com registro pela metade nao vale como dia. Ver INCOMPLETE_DAY_BMR_SHARE.

Mesmo com as duas, a estimativa pode sair impossivel se o usuario registra so os dias
"comportados" (tipico: fim de semana sem lancar nada). Por isso existe is_below_bmr:
manutencao abaixo do gasto em repouso denuncia o diario, e a estimativa nao vira meta.

Cuidado ao mexer no KCAL_PER_KG_FAT (goals.py): ele e usado nas DUAS pontas - aqui para
LER a balanca (inclinacao -> kcal) e em daily_deficit_for_cut para ESCREVER o deficit
(kcal -> inclinacao desejada). Em malha fechada os dois erros se cancelam, entao trocar
por um valor "mais correto" piora o resultado em vez de melhorar.

Siglas: TDEE (Total Daily Energy Expenditure) = gasto total do dia; aqui tratado como
a manutencao calorica (calorias para manter o peso).
"""

from dataclasses import dataclass

# Janela de analise: 3 semanas, tempo suficiente para a tendencia de peso aparecer
# acima do ruido do dia a dia. Fica aqui (e nao no router) porque quem precisa dela
# tambem precisa dos minimos abaixo - o coach usa as duas para dizer quanto falta.
ADAPTIVE_WINDOW_DAYS = 21

# Minimos para confiar na estimativa. A janela de PESAGEM e inclusiva (do dia -20 ate
# hoje), entao o span entre a primeira e a ultima pesagem chega no maximo a 20. A janela
# do DIARIO termina em ontem (ver item 1 no topo do arquivo).
#
# Os minimos sao altos de proposito. Com poucas pesagens num intervalo curto, a
# oscilacao de agua/glicogenio domina a inclinacao da reta: 1 kg de agua convertido a
# 7700 kcal/kg vira ate ~385 kcal/dia de erro com 3 pesagens, contra ~100 kcal/dia com
# 21. O caso pior e a PRIMEIRA janela de uma dieta, quando a queda de glicogenio ainda
# esta acontecendo e e quase todo o sinal - ali a manutencao saia ate ~1200 kcal
# inflada, e a meta adotada ficava ACIMA da manutencao real (a pessoa engordava
# seguindo o app). Exigir quase a janela inteira deixa a agua sair antes de estimarmos.
MIN_SPAN_DAYS = 18  # dias entre a primeira e a ultima pesagem (a janela permite ate 20)
MIN_WEIGH_INS = 8  # pesagens na janela: ~1 a cada 2-3 dias, o bastante para a reta
MIN_DAYS_LOGGED = 8  # numero minimo de dias COMPLETOS com diario alimentar

# Piso de plausibilidade de um dia, como fracao do BMR. Um dia com menos calorias
# que isso quase nunca e um dia de comer pouco: e um dia em que o usuario registrou
# so o cafe da manha e parou. A diferenca importa porque a media entra direto na
# estimativa - um sabado com 412 kcal registradas pesa igual a uma terca com 1.951 e
# derruba a manutencao estimada, que e justamente o numero que vira meta.
#
# Meio BMR e deliberadamente permissivo: quem faz jejum ou come muito pouco de
# verdade ainda passa. So descarta o que nao tem como ser um dia inteiro de comida.
INCOMPLETE_DAY_BMR_SHARE = 0.5


@dataclass
class AdaptiveEstimate:
    has_enough_data: bool
    span_days: int  # dias entre a primeira e a ultima pesagem analisada
    weigh_ins: int  # pesagens na janela
    days_logged: int  # dias COMPLETOS de diario usados na media
    days_discarded: int  # dias descartados por registro incompleto (ver share acima)
    avg_intake_kcal: int  # media diaria consumida nos dias completos
    weekly_change_kg: float  # variacao de peso por semana (negativo = perdendo)
    estimated_maintenance_kcal: int | None  # manutencao real estimada
    # Manutencao abaixo do BMR e fisiologicamente impossivel: ninguem gasta menos
    # em atividade do que gasta parado. Quando isso aparece, o erro esta no dado de
    # entrada (diario incompleto), nao no metabolismo - a estimativa nao pode virar meta.
    is_below_bmr: bool


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


def complete_days_only(daily_intakes: list[float], bmr_kcal: float) -> list[float]:
    """Separa os dias com registro plausivel de dia inteiro dos dias pela metade.

    Ver INCOMPLETE_DAY_BMR_SHARE: o corte e metade do BMR. Com bmr_kcal = 0 (usuario
    sem peso registrado, logo sem BMR) nao ha como julgar e nada e descartado."""
    if bmr_kcal <= 0:
        return list(daily_intakes)
    floor_kcal = bmr_kcal * INCOMPLETE_DAY_BMR_SHARE
    return [kcal for kcal in daily_intakes if kcal >= floor_kcal]


def estimate_maintenance(
    weigh_ins: list[tuple[float, float]],
    daily_intakes: list[float],
    kcal_per_kg_fat: int,
    bmr_kcal: float,
) -> AdaptiveEstimate:
    """Estima a manutencao real. weigh_ins = [(dia_indice, peso_kg)] ordenados;
    daily_intakes = kcal total de cada dia que teve diario (o dia de hoje NAO entra:
    quem monta a lista corta a janela no dia anterior, ver o router)."""
    complete_days = complete_days_only(daily_intakes, bmr_kcal)
    days_logged = len(complete_days)
    days_discarded = len(daily_intakes) - days_logged
    span_days = int(weigh_ins[-1][0] - weigh_ins[0][0]) if len(weigh_ins) >= 2 else 0

    enough = (
        len(weigh_ins) >= MIN_WEIGH_INS
        and span_days >= MIN_SPAN_DAYS
        and days_logged >= MIN_DAYS_LOGGED
    )
    avg_intake = round(sum(complete_days) / days_logged) if days_logged else 0

    if not enough:
        return AdaptiveEstimate(
            has_enough_data=False,
            span_days=span_days,
            weigh_ins=len(weigh_ins),
            days_logged=days_logged,
            days_discarded=days_discarded,
            avg_intake_kcal=avg_intake,
            weekly_change_kg=0.0,
            estimated_maintenance_kcal=None,
            is_below_bmr=False,
        )

    slope_per_day = weight_slope_kg_per_day(weigh_ins)  # kg/dia
    # balanco diario em kcal: peso subindo => superavit (positivo)
    daily_energy_balance = slope_per_day * kcal_per_kg_fat
    # manutencao real = o que comeu menos o balanco (peso caindo aumenta a manutencao)
    estimated_maintenance = round(avg_intake - daily_energy_balance)

    return AdaptiveEstimate(
        has_enough_data=True,
        span_days=span_days,
        weigh_ins=len(weigh_ins),
        days_logged=days_logged,
        days_discarded=days_discarded,
        avg_intake_kcal=avg_intake,
        weekly_change_kg=round(slope_per_day * 7, 2),
        estimated_maintenance_kcal=estimated_maintenance,
        is_below_bmr=bmr_kcal > 0 and estimated_maintenance < bmr_kcal,
    )
