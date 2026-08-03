"""Ciclo menstrual (Fase A): estimativa de fase e preferencia alimentar suave.

O que este servico FAZ: dado o acompanhamento configurado, resolve a fase atual
(marcada a mao ou estimada pela data do ultimo periodo) e devolve os alimentos do
catalogo associados a fase, para o motor de recomendacao usar como desempate.

O que ele NAO faz, de proposito: nao toca na meta calorica, nao le o sexo do perfil
(opt-in explicito, nunca presumido), nao restringe nada ("coma menos na TPM" e
exatamente o que o app recusa fazer). "Cycle syncing" como prescricao nao tem
validacao clinica robusta - por isso a fase entra como preferencia no ranking, nunca
como filtro, e so quando o alimento tambem responde a lacuna do dia (ver
PHASE_MIN_COVERAGE).
"""

from datetime import date

from sqlmodel import Session, select

from ..models import CycleMode, CyclePhase, CycleTracking, Food

# Peso da fase no ranking de sugestoes.
#
# Comecou em 0.15 e nao funcionava: medindo num dia real (faltando 50 g de proteina),
# o melhor alimento da fase ficava em 8o e a tela mostra 4. A fase existia no codigo e
# nao existia para quem usa.
#
# 0.9 poe o alimento da fase no topo quando ele serve, vence um favorito (0.5) e ainda
# fica ABAIXO de "eu como isso nesse horario" (1.5) - o sinal mais pessoal continua
# mandando mais que a fase.
PHASE_BONUS = 0.9

# O freio que torna o bonus alto seguro: a porcao precisa cobrir ao menos esta fatia
# da lacuna para o bonus valer. Sem ele, num dia de proteina a couve (cobre 2%)
# passaria na frente do peito de frango - a fase mandaria mais que o macro, que e
# exatamente o que o escopo proibe.
#
# 0.15 saiu de medicao, nao de gosto: num dia comum (124 g de proteina faltando) a
# melhor cobertura de cada fase e patinho 0.25, salmao 0.27, iogurte grego 0.09 e
# quinoa 0.04. O corte em 0.15 deixa passar carne magra, leguminosa e peixe gordo -
# que realmente fecham proteina - e barra folha, fruta e semente, que nao fecham.
# Consequencia aceita: num dia de proteina, folicular e ovulatoria podem nao aparecer
# nestas listas. E o certo - o card do ciclo continua mostrando os alimentos da fase
# sempre, e nas refeicoes a lacuna e menor, entao elas voltam a caber.
PHASE_MIN_COVERAGE = 0.15

# Alimentos do catalogo global associados a cada fase (slugs, como _STAPLE_SLUGS no
# recommend.py). Curadoria conservadora - associacoes nutricionais bem aceitas, nao
# prescricao: menstrual repoe ferro (com vitamina C junto), lutea foca magnesio e
# fibras (TPM), folicular/ovulatoria ficam em proteina magra e vegetais/antioxidantes.
_PHASE_FOOD_SLUGS: dict[CyclePhase, set[str]] = {
    CyclePhase.menstrual: {
        # ferro (leguminosas e carne magra) + vitamina C que ajuda a absorver
        "black-beans", "beans", "pinto-beans", "white-beans", "lentils",
        "stewed-lentils", "chickpeas", "lean-beef", "ground-beef",
        "collard-greens", "spinach", "beetroot", "beetroot-cooked",
        "orange", "acerola", "strawberry",
    },
    CyclePhase.follicular: {
        # energia em alta: proteina magra, iogurtes e frescos
        "egg", "boiled-egg", "greek-yogurt", "plain-yogurt", "skim-plain-yogurt",
        "quinoa", "broccoli-cooked", "spinach", "strawberry", "banana",
    },
    CyclePhase.ovulatory: {
        # fibras e antioxidantes
        "broccoli-cooked", "spinach", "collard-greens", "strawberry",
        "avocado", "chia", "flaxseed", "quinoa", "green-beans",
    },
    CyclePhase.luteal: {
        # magnesio, fibras e carboidrato complexo (a fase da TPM)
        "banana", "banana-silver", "banana-plantain", "oats", "dark-chocolate",
        "brazil-nut", "walnuts", "peanut", "peanut-butter", "sweet-potato",
        "chickpeas", "avocado", "salmon", "salmon-grilled", "sardine",
    },
}

# Fase menstrual tipica: dias 1-5 do ciclo.
_MENSTRUAL_DAYS = 5
# A fase lutea dura ~14 dias independente do tamanho do ciclo (e o que a literatura
# descreve como estavel); e o folicular que estica ou encolhe. Por isso a ovulacao
# e estimada como (duracao - 14), e nao como "metade do ciclo".
_LUTEAL_DAYS = 14


def estimate_phase(day_in_cycle: int, cycle_length: int) -> CyclePhase:
    """Fase estimada a partir do dia do ciclo (1-based) e da duracao tipica.

    Janelas: menstrual = dias 1-5; ovulatoria = ovulacao +/- 1 dia (ovulacao =
    duracao - 14); folicular entre as duas; lutea da ovulacao ate o fim. Em ciclos
    muito curtos a janela ovulatoria pode encostar na menstrual - a ordem dos "if"
    resolve (menstrual ganha)."""
    ovulation_day = cycle_length - _LUTEAL_DAYS
    if day_in_cycle <= _MENSTRUAL_DAYS:
        return CyclePhase.menstrual
    if abs(day_in_cycle - ovulation_day) <= 1:
        return CyclePhase.ovulatory
    if day_in_cycle < ovulation_day:
        return CyclePhase.follicular
    return CyclePhase.luteal


def resolve_phase(
    tracking: CycleTracking | None, day: date
) -> tuple[CyclePhase | None, str | None, int | None, bool]:
    """Resolve (fase, origem, dia_do_ciclo, estimativa_vencida) para o dia local.

    origem: "manual" (fase marcada) ou "estimated" (pela data). estimativa_vencida
    fica True quando a data do ultimo periodo ja passou de um ciclo inteiro - a
    fase continua sendo estimada (modulo), mas a tela avisa que e hora de atualizar
    a data, em vez de fingir precisao que nao existe (ciclo irregular e comum)."""
    if tracking is None or not tracking.enabled:
        return None, None, None, False
    if tracking.mode == CycleMode.manual:
        if tracking.phase is None:
            return None, None, None, False
        return tracking.phase, "manual", None, False
    if tracking.last_period_date is None:
        return None, None, None, False
    days_since = (day - tracking.last_period_date).days
    if days_since < 0:
        # data no futuro (fuso, erro de digitacao): sem estimativa honesta possivel
        return None, None, None, False
    length = tracking.cycle_length_days
    day_in_cycle = days_since % length + 1
    stale = days_since >= length
    return estimate_phase(day_in_cycle, length), "estimated", day_in_cycle, stale


def phase_boost_food_ids(session: Session, user_id: int, day: date) -> set[int]:
    """Ids dos alimentos globais associados a fase atual do usuario.

    Vazio quando o acompanhamento esta desligado ou a fase e desconhecida - o motor
    de recomendacao soma bonus zero e nada muda. Uma consulta na linha do ciclo +
    uma nos slugs (espelho de _staple_food_ids)."""
    tracking = session.exec(
        select(CycleTracking).where(CycleTracking.user_id == user_id)
    ).first()
    phase, _, _, _ = resolve_phase(tracking, day)
    if phase is None:
        return set()
    slugs = _PHASE_FOOD_SLUGS[phase]
    rows = session.exec(
        select(Food.id).where(Food.user_id.is_(None)).where(Food.slug.in_(slugs))
    ).all()
    return set(rows)
