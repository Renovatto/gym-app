"""Preenche muscle_region em seed_exercises.json por regras de palavra no slug.

O slug em ingles (ex.: "lying-leg-curl", "incline-dumbbell-press") e mais confiavel
que o nome traduzido para regra de palavra-chave: e sempre o mesmo idioma e segue
convencao consistente ("incline"/"decline" para peito, "rear"/"lateral" para ombro
etc). Isso e o "passe 2" do documento de desenho da subdivisao muscular - o "passe
1" (musculo primario da fonte free-exercise-db) nao se aplica aqui porque
seed_exercises.json ja veio sem esse campo.

Regra de ouro: na duvida, fica None. Levantamento de pernos, saltos, arremessos e
variantes olimpicas (clean/snatch/jerk/jump/sprint) sao movimentos de corpo
inteiro - forcar uma subdivisao neles seria a classificacao errada que o proprio
documento pede para evitar. Ficam para curadoria manual no admin (passe 3).

Uso:
    python tools/fill_muscle_regions.py            # relatorio, nao grava
    python tools/fill_muscle_regions.py --write     # grava em app/seed_exercises.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SEED_FILE = BASE_DIR / "app" / "seed_exercises.json"


def classify_chest(slug: str) -> str | None:
    if "incline" in slug:
        return "chest_upper"
    if "decline" in slug:
        return "chest_lower"
    return "chest_mid"


def classify_back(slug: str) -> str | None:
    if "shrug" in slug:
        return "traps"
    if any(k in slug for k in ("deadlift", "good-morning", "hyperextension", "rack-pull")):
        return "lower_back"
    if slug == "back-extension":
        return "lower_back"
    if any(k in slug for k in ("pulldown", "pull-up", "pullup", "chin", "muscle-up", "rope-climb", "pullover")):
        return "lats"
    if "row" in slug:
        return "upper_back"
    return None


def classify_shoulders(slug: str) -> str | None:
    if any(k in slug for k in ("rear-delt", "reverse-fly", "reverse-flye", "face-pull", "rear-lateral", "rear-raise")):
        return "delt_rear"
    if "rear" not in slug and any(k in slug for k in ("lateral-raise", "side-lateral", "side-raise", "deltoid-raise")):
        return "delt_side"
    if any(
        k in slug
        for k in (
            "overhead-press", "military-press", "shoulder-press", "push-press",
            "arnold-press", "front-raise", "upright-row", "front-plate-raise",
            "front-cable-raise", "front-incline", "scaption",
        )
    ):
        return "delt_front"
    return None


def classify_biceps(slug: str) -> str | None:
    if any(k in slug for k in ("wrist", "forearm", "finger-curl", "plate-pinch", "wrist-roller", "wrist-rotation")):
        return "forearms"
    if "curl" in slug:
        return "biceps"
    return None


def classify_triceps(slug: str) -> str | None:
    if any(k in slug for k in ("overhead", "skullcrusher", "skull-crusher")):
        return "triceps_long"
    if any(k in slug for k in ("pushdown", "kickback", "press", "dip")):
        return "triceps_lateral"
    return None


def classify_legs(slug: str) -> str | None:
    if "adduct" in slug:
        return "adductors"
    if "abduct" in slug:
        return "abductors"
    if any(k in slug for k in ("leg-curl", "romanian-deadlift", "stiff", "glute-ham", "hamstring")):
        return "hamstrings"
    if any(k in slug for k in ("squat", "leg-press", "leg-extension", "lunge", "step-up")):
        return "quads"
    return None


def classify_abs(slug: str) -> str | None:
    if any(k in slug for k in ("oblique", "twist", "side-bend", "wood-chop")):
        return "obliques"
    if any(k in slug for k in ("leg-raise", "reverse-crunch", "pike", "leg-pull-in", "leg-tuck", "hip-raise", "knee-hip-raise")):
        return "abs_lower"
    if any(k in slug for k in ("crunch", "sit-up")):
        return "abs_upper"
    if any(k in slug for k in ("plank", "pallof", "dead-bug", "rollout", "side-bridge")):
        return "core"
    return None


def classify_glutes(slug: str) -> str | None:
    if any(
        k in slug
        for k in ("kickback", "hip-thrust", "glute-bridge", "bridge", "pull-through", "hip-extension", "hip-lift", "leg-lift")
    ):
        return "glute_max"
    return None


def classify_calves(slug: str) -> str | None:
    if "seated" in slug:
        return "soleus"
    if "standing" in slug or "calf" in slug:
        return "gastrocnemius"
    return None


CLASSIFIERS = {
    "chest": classify_chest,
    "back": classify_back,
    "shoulders": classify_shoulders,
    "biceps": classify_biceps,
    "triceps": classify_triceps,
    "legs": classify_legs,
    "abs": classify_abs,
    "glutes": classify_glutes,
    "calves": classify_calves,
    "cardio": lambda slug: None,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="grava o resultado em seed_exercises.json")
    args = parser.parse_args()

    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))

    classified = Counter()
    unclassified = Counter()
    for item in data:
        classify = CLASSIFIERS[item["muscle_group"]]
        region = classify(item["slug"])
        if region:
            item["muscle_region"] = region
            classified[item["muscle_group"]] += 1
        else:
            item.pop("muscle_region", None)
            unclassified[item["muscle_group"]] += 1

    print("Classificados por grupo:")
    for group, count in sorted(classified.items()):
        total = count + unclassified.get(group, 0)
        print(f"  {group:12s} {count:3d}/{total:3d}")
    print("Sem subdivisao (ficam NULL para curadoria no admin):")
    for group, count in sorted(unclassified.items()):
        print(f"  {group:12s} {count:3d}")
    print(f"Total: {sum(classified.values())} classificados, {sum(unclassified.values())} sem subdivisao")

    if args.write:
        SEED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[fill_muscle_regions] gravado em {SEED_FILE}")
    else:
        print("(modo relatorio - use --write para gravar)")


if __name__ == "__main__":
    main()
