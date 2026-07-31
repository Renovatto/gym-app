"""Leitura da composicao corporal medida pela balanca (BIA = bioimpedancia).

Legenda das siglas usadas aqui:
- BIA (Bioelectrical Impedance Analysis) = bioimpedancia, metodo da balanca para
  estimar composicao corporal. Impreciso no valor absoluto, bom na TENDENCIA.
- BMI/IMC = indice de massa corporal (peso / altura^2). Nao distingue musculo de
  gordura - e justamente por isso que esta tela existe.

Uma decisao de projeto vale registrar: a classificacao de peso do app segue a OMS
(corte de IMC 25, ver BMI_NORMAL_MAX em goals.py). As faixas de gordura abaixo sao
uma leitura DIFERENTE e complementar, nunca um segundo veredicto sobre o mesmo
numero - o app nao pode dizer "peso saudavel" num lugar e "obesidade" no outro.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from math import log10

from ..models import Sex, WeightLog

# Faixas de referencia de gordura corporal em %, por sexo (referencia: ACE, American
# Council on Exercise - a mais usada em material de treino). Sao faixas de orientacao,
# nao diagnostico: variam por fonte, idade e etnia.
# essential = gordura essencial (minimo fisiologico), athlete = atleta,
# fitness = em forma, acceptable = aceitavel/media, high = acima do recomendado.
_BANDS_BY_SEX: dict[Sex, list[tuple[str, float, float]]] = {
    Sex.male: [
        ("essential", 2.0, 6.0),
        ("athlete", 6.0, 14.0),
        ("fitness", 14.0, 18.0),
        ("acceptable", 18.0, 25.0),
        ("high", 25.0, 40.0),
    ],
    Sex.female: [
        ("essential", 10.0, 14.0),
        ("athlete", 14.0, 21.0),
        ("fitness", 21.0, 25.0),
        ("acceptable", 25.0, 32.0),
        ("high", 32.0, 45.0),
    ],
}

# Extremos da regua desenhada na tela. Cortamos a gordura essencial: ninguem tem meta
# ali e mostrar a faixa toda espremeria a parte que importa.
_GAUGE_BY_SEX: dict[Sex, tuple[float, float]] = {
    Sex.male: (5.0, 35.0),
    Sex.female: (12.0, 42.0),
}

# Duas pesagens muito proximas nao dizem nada sobre tendencia: a variacao do dia a dia
# da bioimpedancia (hidratacao, horario, comida) e maior que a mudanca real.
_TREND_MIN_DAYS = 14

# O alvo vira FAIXA e nao numero unico: a bioimpedancia nao tem precisao para cravar
# um peso em kg, e um numero unico prometeria uma exatidao que a medicao nao tem.
_TARGET_SPREAD_PCT = 1.5


def reference_bands(sex: Sex) -> list[tuple[str, float, float]]:
    return _BANDS_BY_SEX[sex]


def gauge_range(sex: Sex) -> tuple[float, float]:
    return _GAUGE_BY_SEX[sex]


def classify_body_fat(fat_percentage: float, sex: Sex) -> str:
    """Em qual faixa de referencia essa porcentagem cai."""
    bands = _BANDS_BY_SEX[sex]
    for key, start, end in bands:
        if fat_percentage < end:
            return key
    return bands[-1][0]


def fat_mass_kg(log: WeightLog) -> float | None:
    """Gordura em kg. A balanca as vezes manda so a porcentagem: nesse caso
    calculamos, gordura_kg = peso * porcentagem / 100."""
    if log.fat_mass_kg is not None:
        return round(log.fat_mass_kg, 1)
    if log.fat_percentage is not None:
        return round(log.weight_kg * log.fat_percentage / 100.0, 1)
    return None


def lean_mass_kg(log: WeightLog) -> float | None:
    """Massa magra = tudo que nao e gordura (musculo, osso, agua, orgaos).

    E o numero que se PROTEGE: em qualquer objetivo, perder massa magra junto e o
    que separa "emagreci bem" de "emagreci mal"."""
    fat_kg = fat_mass_kg(log)
    if fat_kg is None:
        return None
    return round(log.weight_kg - fat_kg, 1)


def target_weight_range(lean_kg: float, target_fat_percentage: float) -> tuple[float, float]:
    """Peso correspondente a um alvo de gordura, MANTIDA a massa magra atual.

    Da identidade peso = magra + gordura, com gordura = peso * alvo:
        peso = magra / (1 - alvo)
    Devolvemos os extremos de uma janela de +-1.5 ponto percentual em volta do alvo,
    porque o alvo e uma escolha aproximada e o metodo de medicao tambem e."""
    lower_pct = max(1.0, target_fat_percentage - _TARGET_SPREAD_PCT)
    upper_pct = min(60.0, target_fat_percentage + _TARGET_SPREAD_PCT)
    # mais gordura no alvo = peso maior, entao o alvo "de cima" gera o peso maior
    lightest = lean_kg / (1.0 - lower_pct / 100.0)
    heaviest = lean_kg / (1.0 - upper_pct / 100.0)
    return round(lightest, 1), round(heaviest, 1)


def previous_for_trend(
    logs: list[WeightLog],
    latest: WeightLog,
    has_value: "Callable[[WeightLog], bool] | None" = None,
) -> WeightLog | None:
    """Pesagem mais recente que ainda esta longe o bastante da ultima para a
    comparacao significar alguma coisa.

    `has_value` diz o que conta como "tem o dado": a tendencia PRECISA comparar a
    mesma fonte nas duas pontas (balanca com balanca, fita com fita) - misturar
    inventaria uma variacao que nunca existiu."""
    if has_value is None:
        has_value = lambda log: log.fat_percentage is not None  # noqa: E731
    cutoff = latest.logged_at - timedelta(days=_TREND_MIN_DAYS)
    candidates = [
        log
        for log in logs
        if log.id != latest.id
        and has_value(log)
        and _naive(log.logged_at) <= _naive(cutoff)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda log: _naive(log.logged_at))


def _naive(value: datetime) -> datetime:
    """Compara datas sem tropecar em uma ter fuso e a outra nao (o SQLite devolve
    datetime ingenuo; o Postgres, com fuso)."""
    return value.replace(tzinfo=None)


# --- Gordura estimada por fita metrica ------------------------------------
# Formula de Hodgdon-Beckett, adotada pela Marinha americana. Versao metrica (cm).
#
# Por que ela vale a pena, mesmo o app ja tendo a balanca: contra o DEXA (padrao de
# referencia), a fita erra ~3 a 4 pontos percentuais e a bioimpedancia de balanca
# domestica erra ~4 a 8. Ou seja, a fita nao e o dado pobre - e o MAIS preciso dos
# dois que o app consegue coletar. E funciona para quem nao tem balanca nenhuma.
#
# O que ela NAO faz: braco, coxa e peito nao entram aqui. Circunferencia de membro
# nao isola musculo (pega gordura, liquido e osso junto), entao esses campos ficam
# como acompanhamento de tendencia e nunca viram estimativa.

# Fora desta faixa o resultado nao e plausivel para um ser humano medido direito -
# quase sempre e fita no lugar errado. Melhor nao mostrar nada do que mostrar errado.
_NAVY_MIN_PCT = 3.0
_NAVY_MAX_PCT = 70.0


def navy_body_fat_pct(
    sex: Sex,
    height_cm: float,
    waist_cm: float | None,
    neck_cm: float | None,
    hip_cm: float | None = None,
) -> float | None:
    """Gordura corporal em % pela fita. None quando faltam medidas ou o resultado
    nao e plausivel.

    Homem  : 495 / (1.0324  - 0.19077*log10(cintura - pescoco)           + 0.15456*log10(altura)) - 450
    Mulher : 495 / (1.29579 - 0.35004*log10(cintura + quadril - pescoco) + 0.22100*log10(altura)) - 450
    """
    if not waist_cm or not neck_cm or not height_cm:
        return None
    if sex == Sex.female and not hip_cm:
        return None  # a formula feminina depende do quadril

    # O termo dentro do log10 precisa ser positivo. Cintura menor que o pescoco e
    # medida trocada, nao um corpo - e sem esta guarda o log10 estoura.
    girth = (waist_cm + (hip_cm or 0.0) - neck_cm) if sex == Sex.female else (waist_cm - neck_cm)
    if girth <= 0:
        return None

    if sex == Sex.female:
        denominator = 1.29579 - 0.35004 * log10(girth) + 0.22100 * log10(height_cm)
    else:
        denominator = 1.0324 - 0.19077 * log10(girth) + 0.15456 * log10(height_cm)
    if denominator <= 0:
        return None

    percentage = 495.0 / denominator - 450.0
    if not _NAVY_MIN_PCT <= percentage <= _NAVY_MAX_PCT:
        return None
    return round(percentage, 1)


def navy_body_fat_from_log(log: WeightLog, sex: Sex, height_cm: float) -> float | None:
    """Atalho: le as medidas de fita do proprio registro de pesagem."""
    return navy_body_fat_pct(sex, height_cm, log.waist_cm, log.neck_cm, log.hip_cm)


# --- Cintura como marcador de risco ---------------------------------------
# Cortes da OMS. A cintura e a unica medida da lista com significado clinico
# SOZINHA: preve gordura visceral e risco cardiometabolico de forma independente do
# IMC, porque captura DISTRIBUICAO de gordura, que peso e IMC nao capturam.
_WAIST_RISK_CUTOFFS: dict[Sex, tuple[float, float]] = {
    Sex.male: (94.0, 102.0),
    Sex.female: (80.0, 88.0),
}


def waist_risk_band(waist_cm: float | None, sex: Sex) -> str | None:
    """ok | increased | high. None quando nao ha medida."""
    if not waist_cm:
        return None
    increased, high = _WAIST_RISK_CUTOFFS[sex]
    if waist_cm >= high:
        return "high"
    if waist_cm >= increased:
        return "increased"
    return "ok"


def waist_risk_cutoffs(sex: Sex) -> tuple[float, float]:
    return _WAIST_RISK_CUTOFFS[sex]


# --- Qual fonte manda no painel -------------------------------------------
SOURCE_AUTO = "auto"
SOURCE_SCALE = "scale"
SOURCE_TAPE = "tape"
VALID_SOURCES = (SOURCE_AUTO, SOURCE_SCALE, SOURCE_TAPE)


def resolve_fat_percentage(
    log: WeightLog, sex: Sex, height_cm: float, preference: str
) -> tuple[float | None, str | None]:
    """Devolve (gordura em %, fonte usada) conforme a preferencia da pessoa.

    No modo automatico a fita ganha quando esta completa, porque erra menos que a
    bioimpedancia. Quem quiser fixar uma das duas escolhe na tela - importante para
    nao trocar de fonte no meio da serie historica e estragar a tendencia."""
    tape = navy_body_fat_from_log(log, sex, height_cm)
    scale = log.fat_percentage

    if preference == SOURCE_SCALE:
        return (scale, SOURCE_SCALE) if scale is not None else (None, None)
    if preference == SOURCE_TAPE:
        return (tape, SOURCE_TAPE) if tape is not None else (None, None)
    if tape is not None:
        return tape, SOURCE_TAPE
    if scale is not None:
        return scale, SOURCE_SCALE
    return None, None


def has_source_data(log: WeightLog, sex: Sex, height_cm: float, source: str) -> bool:
    """A pesagem tem o dado da fonte indicada? Usado para a tendencia comparar
    sempre a MESMA fonte - misturar balanca com fita inventaria uma variacao que
    nunca existiu."""
    value, _ = resolve_fat_percentage(log, sex, height_cm, source)
    return value is not None
