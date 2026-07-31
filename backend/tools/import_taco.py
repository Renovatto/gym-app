"""Importa alimentos da TACO (UNICAMP) para o catalogo do app.

TACO = Tabela Brasileira de Composicao de Alimentos, 4a edicao, do NEPA/UNICAMP.
Dados medidos em laboratorio, com preparo brasileiro ("feijao carioca cozido", e nao
"black beans, cooked"). Licenca na propria publicacao, pagina 4:

    "E permitida a reproducao parcial ou total desta obra, desde que citada a fonte."

Por isso o app credita NEPA/UNICAMP na tela do Guia - a citacao e condicao de uso,
nao cortesia.

POR QUE UMA LISTA ESCOLHIDA A MAO, E NAO A TABELA INTEIRA
A TACO tem 597 alimentos, com 7 tipos de arroz, 16 de feijao e 8 de banana. Importar
tudo pioraria a busca: quem digita "arroz" acharia sete linhas quase iguais. O
catalogo ja tem 197 alimentos e cobre o basico, entao aqui entra so o que FALTA.

Uso:
    python tools/import_taco.py              # relatorio, nao grava
    python tools/import_taco.py --write      # grava em app/seed_foods.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent.parent
SEED_FILE = BASE_DIR / "app" / "seed_foods.json"
TACO_URL = "https://www.nepa.unicamp.br/arquivo/uploads/taco-4a-edicao/taco-4a-edicao-2/"
TACO_CACHE = Path(__file__).resolve().parent / ".cache" / "taco-4a-edicao.xlsx"
SHEET = "CMVCol taco3"

# Colunas da planilha (0-based): numero, descricao, umidade, kcal, kJ, proteina,
# lipideos, colesterol, carboidrato, fibra
COL_CODE, COL_DESC, COL_KCAL, COL_PROTEIN, COL_FAT, COL_CARBS, COL_FIBER = 0, 1, 3, 5, 6, 8, 9

# Alimentos a importar: numero na TACO -> como entra no catalogo.
# O numero e a chave porque e estavel: o nome da TACO tem virgulas e varia de edicao.
# portion = porcao caseira em gramas que vira o padrao ao lancar no diario.
ALLOWLIST: dict[int, dict] = {
    # --- Vegetais: versao COZIDA do que o catalogo so tinha cru ---------------
    109: dict(slug="carrot-cooked", category="vegetable", portion=80,
              pt="Cenoura cozida", en="Cooked carrot", es="Zanahoria cocida"),
    97: dict(slug="beetroot-cooked", category="vegetable", portion=80,
             pt="Beterraba cozida", en="Cooked beetroot", es="Remolacha cocida"),
    100: dict(slug="broccoli-cooked", category="vegetable", portion=80,
              pt="Brócolis cozido", en="Cooked broccoli", es="Brócoli cocido"),
    118: dict(slug="cauliflower-cooked", category="vegetable", portion=80,
              pt="Couve-flor cozida", en="Cooked cauliflower", es="Coliflor cocida"),
    72: dict(slug="zucchini-sauteed", category="vegetable", portion=80,
             pt="Abobrinha refogada", en="Sauteed zucchini", es="Calabacín salteado"),
    151: dict(slug="red-cabbage-sauteed", category="vegetable", portion=80,
              pt="Repolho roxo refogado", en="Sauteed red cabbage", es="Col lombarda salteada"),
    # --- Vegetais brasileiros que faltavam ------------------------------------
    112: dict(slug="chayote-cooked", category="vegetable", portion=80,
              pt="Chuchu cozido", en="Cooked chayote", es="Chayote cocido"),
    113: dict(slug="chayote-raw", category="vegetable", portion=80,
              pt="Chuchu cru", en="Raw chayote", es="Chayote crudo"),
    64: dict(slug="kabocha-cooked", category="vegetable", portion=80,
             pt="Abóbora cabotiá cozida", en="Cooked kabocha squash", es="Calabaza cocida"),
    65: dict(slug="kabocha-raw", category="vegetable", portion=80,
             pt="Abóbora cabotiá crua", en="Raw kabocha squash", es="Calabaza cruda"),
    127: dict(slug="scarlet-eggplant", category="vegetable", portion=60,
              pt="Jiló cru", en="Raw scarlet eggplant", es="Berenjena escarlata cruda"),
    134: dict(slug="gherkin-raw", category="vegetable", portion=60,
              pt="Maxixe cru", en="Raw West Indian gherkin", es="Pepinillo crudo"),
    84: dict(slug="chicory-raw", category="vegetable", portion=50,
             pt="Almeirão cru", en="Raw chicory greens", es="Achicoria cruda"),
    85: dict(slug="chicory-sauteed", category="vegetable", portion=80,
             pt="Almeirão refogado", en="Sauteed chicory greens", es="Achicoria salteada"),
    106: dict(slug="catalonha-sauteed", category="vegetable", portion=80,
              pt="Catalonha refogada", en="Sauteed catalogna chicory", es="Achicoria catalogna salteada"),
    135: dict(slug="mustard-greens-raw", category="vegetable", portion=50,
              pt="Folha de mostarda crua", en="Raw mustard greens", es="Hojas de mostaza crudas"),
    # --- Raizes e tuberculos: CRU (para receita) e preparado ------------------
    92: dict(slug="potato-raw", category="carb", portion=150,
             pt="Batata inglesa crua", en="Raw potato", es="Patata cruda"),
    93: dict(slug="potato-fried", category="carb", portion=100,
             pt="Batata frita", en="French fries", es="Patatas fritas"),
    86: dict(slug="arracacha-cooked", category="carb", portion=100,
             pt="Batata baroa cozida", en="Cooked arracacha", es="Arracacha cocida"),
    89: dict(slug="sweet-potato-raw", category="carb", portion=150,
             pt="Batata-doce crua", en="Raw sweet potato", es="Batata cruda"),
    130: dict(slug="cassava-raw", category="carb", portion=150,
              pt="Mandioca crua", en="Raw cassava", es="Yuca cruda"),
    132: dict(slug="cassava-fried", category="carb", portion=100,
              pt="Mandioca frita", en="Fried cassava", es="Yuca frita"),
    126: dict(slug="yam-raw", category="carb", portion=150,
              pt="Inhame cru", en="Raw yam", es="Ñame crudo"),
    102: dict(slug="taro-cooked", category="carb", portion=100,
              pt="Cará cozido", en="Cooked taro", es="Taro cocido"),
    # --- Farinhas e derivados de mandioca -------------------------------------
    122: dict(slug="cassava-flour-toasted", category="carb", portion=20,
              pt="Farinha de mandioca torrada", en="Toasted cassava flour", es="Harina de yuca tostada"),
    131: dict(slug="seasoned-farofa", category="carb", portion=25,
              pt="Farofa temperada", en="Seasoned cassava flour (farofa)", es="Farofa condimentada"),
    62: dict(slug="polenta-precooked", category="carb", portion=120,
             pt="Polenta pré-cozida", en="Precooked polenta", es="Polenta precocida"),
    61: dict(slug="popcorn-oil", category="carb", portion=30,
             pt="Pipoca com óleo", en="Popcorn with oil", es="Palomitas con aceite"),
    136: dict(slug="potato-gnocchi", category="carb", portion=150,
              pt="Nhoque de batata cozido", en="Cooked potato gnocchi", es="Ñoquis de patata cocidos"),
    # --- Massa crua (para receita) --------------------------------------------
    38: dict(slug="fresh-lasagna-raw", category="carb", portion=100,
             pt="Massa de lasanha fresca crua", en="Raw fresh lasagna sheets", es="Placas de lasaña frescas crudas"),
    # --- Frutas brasileiras ----------------------------------------------------
    168: dict(slug="acai-pulp", category="fruit", portion=100,
              pt="Açaí polpa congelada", en="Frozen açaí pulp", es="Pulpa de açaí congelada"),
    169: dict(slug="acerola", category="fruit", portion=100,
              pt="Acerola crua", en="Raw acerola", es="Acerola cruda"),
    186: dict(slug="cashew-fruit", category="fruit", portion=100,
              pt="Caju cru", en="Raw cashew apple", es="Marañón crudo"),
    192: dict(slug="cupuacu", category="fruit", portion=100,
              pt="Cupuaçu cru", en="Raw cupuaçu", es="Cupuazú crudo"),
    201: dict(slug="soursop", category="fruit", portion=100,
              pt="Graviola crua", en="Raw soursop", es="Guanábana cruda"),
    204: dict(slug="jackfruit", category="fruit", portion=100,
              pt="Jaca crua", en="Raw jackfruit", es="Yaca cruda"),
    247: dict(slug="surinam-cherry", category="fruit", portion=100,
              pt="Pitanga crua", en="Raw Surinam cherry", es="Pitanga cruda"),
    189: dict(slug="persimmon", category="fruit", portion=120,
              pt="Caqui cru", en="Raw persimmon", es="Caqui crudo"),
    190: dict(slug="starfruit", category="fruit", portion=100,
              pt="Carambola crua", en="Raw starfruit", es="Carambola cruda"),
    254: dict(slug="umbu", category="fruit", portion=100,
              pt="Umbu cru", en="Raw umbu", es="Umbú crudo"),
    206: dict(slug="jambolan", category="fruit", portion=100,
              pt="Jamelão cru", en="Raw jambolan", es="Jambolán crudo"),
    # --- Pratos e doces brasileiros --------------------------------------------
    20: dict(slug="hominy-with-milk", category="prepared", portion=200,
             pt="Canjica com leite", en="Hominy with milk (canjica)", es="Canjica con leche"),
    29: dict(slug="green-corn-curau", category="prepared", portion=150,
             pt="Curau de milho verde", en="Green corn pudding (curau)", es="Curau de maíz"),
    440: dict(slug="baked-kibbeh", category="prepared", portion=120,
              pt="Quibe assado", en="Baked kibbeh", es="Kibbe al horno"),
    55: dict(slug="raw-meat-pastel", category="prepared", portion=80,
             pt="Pastel de carne cru", en="Raw meat pastel", es="Empanada de carne cruda"),
    56: dict(slug="fried-meat-pastel", category="prepared", portion=80,
             pt="Pastel de carne frito", en="Fried meat pastel", es="Empanada de carne frita"),
    # --- Laticinios e outros ----------------------------------------------------
    449: dict(slug="skim-plain-yogurt", category="dairy", portion=170,
              pt="Iogurte natural desnatado", en="Skim plain yogurt", es="Yogur natural desnatado"),
    508: dict(slug="molasses", category="sweet", portion=20,
              pt="Melado de cana", en="Sugarcane molasses", es="Melaza de caña"),
}


def download_taco() -> Path:
    """Baixa a planilha uma vez e guarda em cache local (fora do repositorio)."""
    if TACO_CACHE.exists():
        return TACO_CACHE
    TACO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"baixando a TACO de {TACO_URL} ...")
    request = Request(TACO_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        TACO_CACHE.write_bytes(response.read())
    return TACO_CACHE


def cell_number(value: object) -> float | None:
    """Celula numerica da TACO. 'NA' = nao analisado, 'Tr' = traco (zero pratico)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in ("NA", "*", ""):
        return None
    if text == "Tr":
        return 0.0
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def read_taco(path: Path) -> dict[int, tuple[str, float, float, float, float, float]]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook[SHEET]
    foods: dict[int, tuple] = {}
    for row in sheet.iter_rows(min_row=4, values_only=True):
        code, description = row[COL_CODE], row[COL_DESC]
        if code is None or description is None:
            continue
        if not str(code).strip().replace(".", "").isdigit():
            continue  # linha de grupo ("Cereais e derivados")
        values = [
            cell_number(row[i])
            for i in (COL_KCAL, COL_PROTEIN, COL_CARBS, COL_FAT, COL_FIBER)
        ]
        if any(v is None for v in values[:4]):
            continue
        kcal, protein, carbs, fat, fiber = *values[:4], values[4] or 0.0
        foods[int(float(code))] = (str(description).strip(), kcal, protein, carbs, fat, fiber)
    return foods


def macros_reconcile(kcal: float, protein: float, carbs: float, fat: float, fiber: float) -> bool:
    """Confere se as calorias fecham com os macros (Atwater), com a fibra rendendo
    ~2 kcal/g em vez de 4. Uma linha que nao fecha foi lida errado ou tem dado ruim -
    em qualquer dos casos nao pode entrar no catalogo sem alguem olhar.

    A tolerancia e dupla porque so a relativa nao serve: em alface, 2 kcal de
    diferenca ja seriam 12%."""
    computed = 4 * protein + 9 * fat + 4 * max(0.0, carbs - fiber) + 2 * fiber
    difference = abs(computed - kcal)
    return difference <= 12 or (kcal > 0 and difference / kcal <= 0.15)


def build_entries(taco: dict) -> tuple[list[dict], list[str]]:
    entries: list[dict] = []
    problems: list[str] = []
    for code, spec in sorted(ALLOWLIST.items()):
        if code not in taco:
            problems.append(f"TACO {code} ({spec['slug']}): nao encontrado na planilha")
            continue
        description, kcal, protein, carbs, fat, fiber = taco[code]
        if not macros_reconcile(kcal, protein, carbs, fat, fiber):
            problems.append(
                f"TACO {code} ({spec['slug']}): macros nao fecham - {description}"
            )
            continue
        entries.append(
            {
                "slug": spec["slug"],
                "category": spec["category"],
                "kcal": round(kcal, 1),
                "protein_g": round(protein, 1),
                "carbs_g": round(carbs, 1),
                "fat_g": round(fat, 1),
                "default_portion_g": spec["portion"],
                "portions": [{"label_key": "portion", "grams": spec["portion"]}],
                "names": {"pt-BR": spec["pt"], "en": spec["en"], "es": spec["es"]},
            }
        )
    return entries, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="grava em seed_foods.json")
    args = parser.parse_args()

    taco = read_taco(download_taco())
    print(f"TACO lida: {len(taco)} alimentos")

    entries, problems = build_entries(taco)
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    existing_slugs = {food["slug"] for food in seed}
    existing_names = {food["names"]["pt-BR"].lower() for food in seed}

    novos, duplicados = [], []
    for entry in entries:
        if entry["slug"] in existing_slugs:
            duplicados.append(f"{entry['slug']} (slug ja existe)")
        elif entry["names"]["pt-BR"].lower() in existing_names:
            duplicados.append(f"{entry['slug']} (nome '{entry['names']['pt-BR']}' ja existe)")
        else:
            novos.append(entry)
            existing_slugs.add(entry["slug"])
            existing_names.add(entry["names"]["pt-BR"].lower())

    print(f"na lista de importacao: {len(ALLOWLIST)}")
    print(f"  entram novos          : {len(novos)}")
    print(f"  ja existiam (ignorados): {len(duplicados)}")
    print(f"  com problema           : {len(problems)}")
    for problem in problems:
        print(f"    ! {problem}")
    for duplicate in duplicados:
        print(f"    = {duplicate}")

    if not args.write:
        print("\n(nada gravado - rode com --write)")
        return 1 if problems else 0

    seed.extend(novos)
    SEED_FILE.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\ngravado: {SEED_FILE} agora tem {len(seed)} alimentos")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
