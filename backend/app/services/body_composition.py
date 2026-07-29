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

from datetime import datetime, timedelta

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


def previous_for_trend(logs: list[WeightLog], latest: WeightLog) -> WeightLog | None:
    """Pesagem com composicao mais recente que ainda esta longe o bastante da ultima
    para a comparacao significar alguma coisa."""
    cutoff = latest.logged_at - timedelta(days=_TREND_MIN_DAYS)
    candidates = [
        log
        for log in logs
        if log.id != latest.id
        and log.fat_percentage is not None
        and _naive(log.logged_at) <= _naive(cutoff)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda log: _naive(log.logged_at))


def _naive(value: datetime) -> datetime:
    """Compara datas sem tropecar em uma ter fuso e a outra nao (o SQLite devolve
    datetime ingenuo; o Postgres, com fuso)."""
    return value.replace(tzinfo=None)
