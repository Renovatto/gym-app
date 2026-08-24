from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Column
from sqlalchemy.types import JSON
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
    recomp = "recomp"  # ganhar musculo e perder gordura ao mesmo tempo


class CutIntensity(str, Enum):
    """Intensidade do deficit no objetivo de perder gordura. Cada nivel e uma taxa
    alvo de perda por semana, em % do peso corporal (ver goals.py)."""

    light = "light"  # perda lenta, mais confortavel e melhor para preservar musculo
    moderate = "moderate"  # equilibrio padrao
    aggressive = "aggressive"  # perda rapida, exige disciplina e mais risco de perder musculo


class Plan(str, Enum):
    free = "free"
    premium = "premium"


class WeightSource(str, Enum):
    manual = "manual"
    ble = "ble"


class MuscleGroup(str, Enum):
    chest = "chest"
    back = "back"
    shoulders = "shoulders"
    biceps = "biceps"
    triceps = "triceps"
    legs = "legs"
    glutes = "glutes"
    abs = "abs"
    calves = "calves"
    cardio = "cardio"


class MuscleRegion(str, Enum):
    """Subdivisao dentro de um MuscleGroup (ex.: legs -> hamstrings). Sempre
    opcional: hierarquia completa em services/exercises.py:REGIONS_BY_GROUP."""

    chest_upper = "chest_upper"
    chest_mid = "chest_mid"
    chest_lower = "chest_lower"
    lats = "lats"
    upper_back = "upper_back"
    traps = "traps"
    lower_back = "lower_back"
    delt_front = "delt_front"
    delt_side = "delt_side"
    delt_rear = "delt_rear"
    biceps = "biceps"
    forearms = "forearms"
    triceps_long = "triceps_long"
    triceps_lateral = "triceps_lateral"
    quads = "quads"
    hamstrings = "hamstrings"
    adductors = "adductors"
    abductors = "abductors"
    glute_max = "glute_max"
    glute_med = "glute_med"
    abs_upper = "abs_upper"
    abs_lower = "abs_lower"
    obliques = "obliques"
    core = "core"
    gastrocnemius = "gastrocnemius"
    soleus = "soleus"


class ExerciseKind(str, Enum):
    strength = "strength"
    cardio = "cardio"


class ExerciseLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    expert = "expert"


class Equipment(str, Enum):
    barbell = "barbell"
    dumbbell = "dumbbell"
    machine = "machine"
    cable = "cable"
    bodyweight = "bodyweight"
    kettlebell = "kettlebell"
    band = "band"
    other = "other"


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
    water_logs: list["WaterLog"] = Relationship(back_populates="user", cascade_delete=True)


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, ondelete="CASCADE")
    first_name: str | None = Field(default=None)  # nome
    last_name: str | None = Field(default=None)  # sobrenome
    height_cm: float
    birthdate: date
    sex: Sex
    activity_level: ActivityLevel
    objective: Objective
    # Intensidade do deficit; so tem efeito quando objective == lose_fat.
    cut_intensity: CutIntensity = Field(default=CutIntensity.moderate)
    diet_enabled: bool = Field(default=False)
    scale_mac: str | None = Field(default=None)
    # Alvo de gordura corporal em % escolhido pela pessoa. So serve para calcular
    # a faixa de peso correspondente - o app nunca sugere um alvo sozinho.
    body_fat_target_pct: float | None = Field(default=None)
    # Qual fonte manda no painel de composicao corporal: "auto" | "scale" | "tape".
    # Existe porque quem nao tem balanca de bioimpedancia so tem a fita - e ate agora o
    # painel inteiro dependia da balanca e ficava vazio para essas pessoas.
    body_comp_source: str = Field(default="auto")
    # Tutorial guiado (os baloes que apontam onde fica cada coisa na primeira visita
    # de cada aba). Mora aqui, e nao numa tabela propria, porque e preferencia de uso
    # como diet_enabled - e assim ja chega no bootstrap, sem request extra.
    tutorial_enabled: bool = Field(default=True)
    # Passos ja vistos por aba: {"home": 5, "workout": 2}. Um tour so reaparece
    # enquanto vistos < total de passos daquele tour; passo novo acrescentado depois
    # aparece sozinho, sem repetir o que a pessoa ja viu.
    tutorial_progress: dict[str, int] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False, server_default="{}")
    )

    user: User = Relationship(back_populates="profile")


class WeightLog(SQLModel, table=True):
    """Um registro de pesagem (weigh-in). Alem do peso, guarda opcionalmente a
    composicao corporal informada pela balanca de bioimpedancia (BIA)."""

    __tablename__ = "weight_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    weight_kg: float
    source: WeightSource = Field(default=WeightSource.manual)
    logged_at: datetime = Field(default_factory=utcnow, index=True)

    # Composicao corporal (opcional). Todos vem da balanca; ficam nulos quando o
    # usuario informa so o peso. BIA = bioimpedancia (impreciso no absoluto, bom na tendencia).
    fat_percentage: float | None = Field(default=None)  # gordura corporal em %
    fat_mass_kg: float | None = Field(default=None)  # peso da gordura em kg
    skeletal_muscle_percentage: float | None = Field(default=None)  # massa muscular esqueletica em %
    skeletal_muscle_kg: float | None = Field(default=None)  # massa muscular esqueletica em kg
    muscle_percentage: float | None = Field(default=None)  # musculo total em %
    muscle_mass_kg: float | None = Field(default=None)  # musculo total em kg
    water_percentage: float | None = Field(default=None)  # agua corporal em %
    water_mass_kg: float | None = Field(default=None)  # peso da agua em kg
    visceral_fat_index: float | None = Field(default=None)  # V-fat = gordura visceral (indice da balanca)
    scale_bmr_kcal: int | None = Field(default=None)  # BMR estimado pela balanca (kcal/dia)

    # Medidas de fita metrica (opcionais). NAO vem da balanca: sao tiradas a mao, e por
    # isso vivem em bloco proprio. Cintura, pescoco e quadril alimentam a estimativa de
    # gordura (formula da Marinha); braco, coxa e peito sao so acompanhamento - nenhum
    # estudo liga circunferencia de membro a tamanho de musculo, entao nao entram em
    # formula nenhuma.
    waist_cm: float | None = Field(default=None)  # cintura (na altura do umbigo)
    neck_cm: float | None = Field(default=None)  # pescoco (abaixo do pomo de adao)
    hip_cm: float | None = Field(default=None)  # quadril (parte mais larga)
    arm_cm: float | None = Field(default=None)  # braco relaxado
    thigh_cm: float | None = Field(default=None)  # coxa (meio)
    chest_cm: float | None = Field(default=None)  # peito

    user: User = Relationship(back_populates="weight_logs")


class WaterLog(SQLModel, table=True):
    __tablename__ = "water_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    amount_ml: int
    logged_at: datetime = Field(default_factory=utcnow, index=True)

    user: User = Relationship(back_populates="water_logs")


class Exercise(SQLModel, table=True):
    __tablename__ = "exercises"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    muscle_group: MuscleGroup = Field(index=True)
    muscle_region: MuscleRegion | None = Field(default=None, index=True)
    equipment: Equipment
    kind: ExerciseKind = Field(default=ExerciseKind.strength, index=True)
    level: ExerciseLevel | None = Field(default=None, index=True)
    media_url: str | None = Field(default=None)
    media_url2: str | None = Field(default=None)
    # None = exercício global (catálogo); preenchido = exercício criado pelo usuário.
    user_id: int | None = Field(default=None, foreign_key="users.id", ondelete="CASCADE")

    translations: list["ExerciseTranslation"] = Relationship(
        back_populates="exercise", cascade_delete=True
    )


class ExerciseTranslation(SQLModel, table=True):
    __tablename__ = "exercise_translations"

    id: int | None = Field(default=None, primary_key=True)
    exercise_id: int = Field(foreign_key="exercises.id", index=True, ondelete="CASCADE")
    locale: str = Field(index=True)
    name: str

    exercise: Exercise = Relationship(back_populates="translations")


class Routine(SQLModel, table=True):
    __tablename__ = "routines"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    name: str
    position: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)
    # NULL = rotina ativa (no ciclo). Preenchido = arquivada: sai do ciclo e da
    # periodizacao, mas mantem exercicios, alvos e o vinculo com o historico.
    archived_at: datetime | None = Field(default=None)

    items: list["RoutineExercise"] = Relationship(back_populates="routine", cascade_delete=True)


class RoutineExercise(SQLModel, table=True):
    __tablename__ = "routine_exercises"

    id: int | None = Field(default=None, primary_key=True)
    routine_id: int = Field(foreign_key="routines.id", index=True, ondelete="CASCADE")
    exercise_id: int = Field(foreign_key="exercises.id")
    position: int = Field(default=0)
    target_sets: int = Field(default=3)
    target_reps: int = Field(default=10)
    target_weight_kg: float | None = Field(default=None)
    target_duration_min: int | None = Field(default=None)  # cardio
    rest_seconds: int = Field(default=90)

    routine: Routine = Relationship(back_populates="items")


class WorkoutSession(SQLModel, table=True):
    __tablename__ = "workout_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    routine_id: int | None = Field(default=None, foreign_key="routines.id")
    routine_name: str | None = Field(default=None)
    started_at: datetime = Field(default_factory=utcnow, index=True)
    finished_at: datetime | None = Field(default=None)

    sets: list["SetLog"] = Relationship(back_populates="session", cascade_delete=True)


class SetLog(SQLModel, table=True):
    __tablename__ = "set_logs"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="workout_sessions.id", index=True, ondelete="CASCADE")
    exercise_id: int = Field(foreign_key="exercises.id", index=True)
    set_number: int
    reps: int
    weight_kg: float
    duration_min: float | None = Field(default=None)  # cardio
    done: bool = Field(default=True)
    logged_at: datetime = Field(default_factory=utcnow)

    session: WorkoutSession = Relationship(back_populates="sets")


class StandaloneActivityKind(str, Enum):
    """Atividade avulsa fora do treino de academia (sem rotina/exercicios cadastrados)."""

    running = "running"
    cycling = "cycling"
    walking = "walking"
    yoga = "yoga"
    pilates = "pilates"
    boxing = "boxing"
    swimming = "swimming"
    dance = "dance"
    other = "other"


class ActivityIntensity(str, Enum):
    light = "light"
    moderate = "moderate"
    hard = "hard"


class StandaloneActivity(SQLModel, table=True):
    __tablename__ = "standalone_activities"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    entry_date: date = Field(index=True)  # dia local informado pelo cliente, mesmo padrao do diario
    time_of_day: str  # "HH:MM" local, so para exibicao
    kind: StandaloneActivityKind
    duration_min: int
    intensity: ActivityIntensity
    distance_km: float | None = Field(default=None)
    kcal: float  # estimado por MET (services/activities.py) ou ajustado a mao
    kcal_is_manual: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)


class FoodCategory(str, Enum):
    """Grupos de alimento no padrao da TACO (tabela brasileira), adaptados ao app.

    A categoria nao e so rotulo: ela e o grupo de troca do recommend.py, onde cada
    categoria tem um macro-ancora que a substituicao equivalente mantem igual. Por
    isso os grupos sao ao mesmo tempo reconheciveis (pao esta em "panificados", nao
    em "carboidrato") e coerentes no macro dominante.
    """

    bakery = "bakery"  # pao, torrada, tapioca pronta: ancora = carbo
    cereal_grain = "cereal_grain"  # arroz, macarrao, aveia, farinhas: ancora = carbo
    tuber = "tuber"  # batata, mandioca, inhame: ancora = carbo
    legume = "legume"  # feijao, lentilha, grao-de-bico: ancora = proteina
    meat = "meat"  # boi, frango, porco e embutidos: ancora = proteina
    seafood = "seafood"  # peixes e frutos do mar: ancora = proteina
    egg = "egg"  # ovo inteiro, clara, gema: ancora = proteina
    dairy = "dairy"  # leite, iogurte, queijos: ancora = proteina
    vegetable = "vegetable"  # verduras e legumes: ancora = carbo
    fruit = "fruit"  # frutas: ancora = carbo
    nuts_seeds = "nuts_seeds"  # castanhas, pastas, sementes, abacate: ancora = gordura
    fat = "fat"  # oleos e gorduras puras (azeite, manteiga): ancora = gordura
    sweet = "sweet"  # acucar, chocolate, bolo, doce: ancora = carbo
    sauce_condiment = "sauce_condiment"  # molho, maionese, sal, tempero: ancora = kcal
    beverage = "beverage"  # refrigerante, suco, cafe, cerveja: ancora = kcal
    prepared = "prepared"  # prato pronto (pizza, feijoada...): macros mistos, ancora = kcal
    supplement = "supplement"  # whey, creatina, etc. (whey conta macro; creatina ~0 kcal)
    other = "other"


class MealType(str, Enum):
    breakfast = "breakfast"
    pre_workout = "pre_workout"  # refeicao extra (opcional): pre-treino
    post_workout = "post_workout"  # refeicao extra (opcional): pos-treino
    lunch = "lunch"
    snack = "snack"
    dinner = "dinner"
    supper = "supper"  # refeicao extra (opcional): ceia
    other = "other"


class EntrySource(str, Enum):
    food = "food"
    recipe = "recipe"


class FavoriteKind(str, Enum):
    food = "food"
    recipe = "recipe"


class Food(SQLModel, table=True):
    __tablename__ = "foods"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    category: FoodCategory = Field(index=True)
    # Valores nutricionais por 100 g (ou 100 ml para líquidos).
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    default_portion_g: float = Field(default=100)
    # None = alimento global (catálogo); preenchido = criado pelo usuário.
    user_id: int | None = Field(default=None, foreign_key="users.id", ondelete="CASCADE")

    translations: list["FoodTranslation"] = Relationship(
        back_populates="food", cascade_delete=True
    )
    portions: list["FoodPortion"] = Relationship(back_populates="food", cascade_delete=True)


class FoodTranslation(SQLModel, table=True):
    __tablename__ = "food_translations"

    id: int | None = Field(default=None, primary_key=True)
    food_id: int = Field(foreign_key="foods.id", index=True, ondelete="CASCADE")
    locale: str = Field(index=True)
    name: str = Field(index=True)

    food: Food = Relationship(back_populates="translations")


class FoodPortion(SQLModel, table=True):
    __tablename__ = "food_portions"

    id: int | None = Field(default=None, primary_key=True)
    food_id: int = Field(foreign_key="foods.id", index=True, ondelete="CASCADE")
    # chave traduzível: unit, slice, tbsp, tsp, cup, glass, scoop, filet, handful, portion
    label_key: str
    grams: float

    food: Food = Relationship(back_populates="portions")


class Recipe(SQLModel, table=True):
    __tablename__ = "recipes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    name: str
    servings: int = Field(default=1)  # quantas porções a receita rende
    created_at: datetime = Field(default_factory=utcnow)

    ingredients: list["RecipeIngredient"] = Relationship(
        back_populates="recipe", cascade_delete=True
    )


class RecipeIngredient(SQLModel, table=True):
    __tablename__ = "recipe_ingredients"

    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipes.id", index=True, ondelete="CASCADE")
    food_id: int = Field(foreign_key="foods.id")
    grams: float

    recipe: Recipe = Relationship(back_populates="ingredients")


class DiaryEntry(SQLModel, table=True):
    __tablename__ = "diary_entries"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    entry_date: date = Field(index=True)  # dia local do usuário
    meal_type: MealType
    source: EntrySource
    food_id: int | None = Field(default=None, foreign_key="foods.id")
    recipe_id: int | None = Field(default=None, foreign_key="recipes.id")
    quantity: float  # gramas (alimento) ou porções (receita)
    # Gramas que o lancamento representa, para a tela ler sempre na mesma unidade.
    # Alimento: igual a quantity. Receita: porcoes x peso de uma porcao - senao a
    # lista mostraria "1,034 porcoes", que e o resto da conversao de 300 g e nao diz
    # nada a quem lancou em gramas. Nulo em lancamento antigo (calculamos na leitura).
    grams: float | None = Field(default=None)
    # snapshot para preservar o histórico mesmo se o alimento/receita mudar
    name_snapshot: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    logged_at: datetime = Field(default_factory=utcnow)


class Favorite(SQLModel, table=True):
    """Alimento ou receita marcado como favorito pelo usuario (a estrelinha).
    Tabela propria, e nao coluna em foods/recipes, porque favoritar e do usuario e
    nao do alimento. ref_id = food_id quando kind=food,
    recipe_id quando kind=recipe (receita ja adotada pelo usuario)."""

    __tablename__ = "favorites"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    kind: FavoriteKind = Field(index=True)
    ref_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)


class FeedbackReport(SQLModel, table=True):
    """Feedback / relato de problema enviado por um usuario. 'module' e string livre
    (workout, diet, progress, profile, other) e nao enum, porque a lista de modulos
    muda junto com as telas do app e nao merece uma migracao a cada ajuste. 'read'
    marca se o admin ja leu."""

    __tablename__ = "feedback_reports"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    module: str = Field(index=True)  # treino/dieta/progresso/perfil/outro
    description: str
    read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class UserAchievement(SQLModel, table=True):
    """Conquista desbloqueada por um usuario. As definicoes das conquistas ficam em
    codigo (services/achievements.py); aqui guardamos so o que cada um ja desbloqueou."""

    __tablename__ = "user_achievements"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    code: str = Field(index=True)  # codigo da conquista (ex.: "workouts_10")
    unlocked_at: datetime = Field(default_factory=utcnow)


class PasswordResetToken(SQLModel, table=True):
    """Token de uso unico para redefinir a senha (enviado por e-mail no deploy)."""

    __tablename__ = "password_reset_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    token: str = Field(index=True)
    expires_at: datetime
    used: bool = Field(default=False)


class LoginAttempt(SQLModel, table=True):
    """Contagem de tentativas de login que falharam, usada para travar forca bruta.

    Fica no banco e nao em memoria porque producao roda uvicorn com 2 workers:
    cada processo teria seu proprio contador (na pratica o limite valeria o dobro)
    e todo bloqueio sumiria a cada deploy."""

    __tablename__ = "login_attempts"

    id: int | None = Field(default=None, primary_key=True)
    # Quem esta sendo contado: "email:fulano@exemplo.com" ou "ip:203.0.113.7".
    key: str = Field(index=True, unique=True)
    failures: int = Field(default=0)
    # Inicio da janela de contagem: passado o prazo, a contagem recomeca do zero.
    window_started_at: datetime = Field(default_factory=utcnow)
    # Preenchido so quando a chave estourou o limite; nulo enquanto pode tentar.
    blocked_until: datetime | None = Field(default=None)


class Supplement(SQLModel, table=True):
    """Suplemento do usuario (ex.: creatina, vitamina D). Os zero-macro sao
    acompanhados por ADESAO diaria (tomou hoje?), nao por calorias."""

    __tablename__ = "supplements"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    name: str
    dose: str = ""  # texto livre, ex.: "5 g", "2000 UI" (pode ficar vazio)
    active: bool = Field(default=True)
    position: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)

    logs: list["SupplementLog"] = Relationship(back_populates="supplement", cascade_delete=True)


class SupplementLog(SQLModel, table=True):
    """Registro de que o suplemento foi tomado num dia. A presenca da linha = tomou."""

    __tablename__ = "supplement_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    supplement_id: int = Field(foreign_key="supplements.id", index=True, ondelete="CASCADE")
    log_date: date = Field(index=True)  # dia local do usuario

    supplement: "Supplement" = Relationship(back_populates="logs")


class DietPeriod(SQLModel, table=True):
    """Periodo (vigencia) da meta de dieta: quando comecou, o objetivo e a validade.
    Renovar cria um periodo novo (o anterior fica inativo). Ao adotar a manutencao real
    medida pelo TDEE adaptativo, guarda em maintenance_kcal (override da formula)."""

    __tablename__ = "diet_periods"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    started_on: date = Field(index=True)
    objective: Objective
    review_weeks: int = Field(default=4)
    target_kcal: int  # meta calorica no inicio do periodo (snapshot para exibir)
    maintenance_kcal: int | None = Field(default=None)  # manutencao real adotada (override)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


# --- Compartilhar entre contas --------------------------------------------
# Uma pessoa compartilha receita/alimento com outra ja conectada. No aceite o item
# e COPIADO para a conta de quem recebe (nunca referenciado): uma receita pode usar
# alimento pessoal de quem enviou, e todo caminho de leitura do app filtra alimento
# por "global OU meu" - referencia obrigaria a reescrever esse filtro no motor
# inteiro. Copiar resolve na entrada e nao muda nenhuma consulta existente.


class ConnectionStatus(str, Enum):
    pending = "pending"  # convite enviado, aguardando resposta
    accepted = "accepted"
    blocked = "blocked"


class ShareOfferStatus(str, Enum):
    pending = "pending"  # esperando na caixa de entrada de quem recebeu
    accepted = "accepted"
    declined = "declined"


class SharedItemKind(str, Enum):
    recipe = "recipe"
    food = "food"


class Connection(SQLModel, table=True):
    """Vinculo entre duas pessoas. Modelado como entidade com estado (e nao como um
    campo "amigo" no perfil) porque e o que permite crescer para comunidade aberta
    sem recomecar: bloqueio e permissao ja tem onde morar."""

    __tablename__ = "connections"

    id: int | None = Field(default=None, primary_key=True)
    requester_user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    addressee_user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    status: ConnectionStatus = Field(default=ConnectionStatus.pending)
    created_at: datetime = Field(default_factory=utcnow)
    responded_at: datetime | None = Field(default=None)


class ShareOffer(SQLModel, table=True):
    """Item oferecido, esperando aceite - a caixa de entrada. Nada entra na conta de
    quem recebe sem ela aceitar."""

    __tablename__ = "share_offers"

    id: int | None = Field(default=None, primary_key=True)
    from_user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    to_user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    item_kind: SharedItemKind
    item_id: int  # id na conta de QUEM ENVIOU
    # nome no momento do envio: a lista da caixa de entrada mostra isso sem precisar
    # ler a conta alheia (e continua legivel se o original for renomeado depois).
    item_name: str
    status: ShareOfferStatus = Field(default=ShareOfferStatus.pending)
    created_at: datetime = Field(default_factory=utcnow)
    responded_at: datetime | None = Field(default=None)


class SharedItem(SQLModel, table=True):
    """De quem veio cada copia aceita. E o que a pilula "Recebidas" filtra e o que
    evita copiar duas vezes o mesmo alimento de origem.

    Mora em tabela propria, e nao numa coluna em recipes/foods, porque o vinculo e
    entre duas pessoas e nao um atributo do alimento: guardar em coluna misturaria
    dado de compartilhamento com dado nutricional."""

    __tablename__ = "shared_items"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    item_kind: SharedItemKind
    item_id: int  # id da COPIA, na conta de quem recebeu
    source_item_id: int  # id do original, na conta de quem enviou
    from_user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    accepted_at: datetime = Field(default_factory=utcnow)


class SessionExerciseSwap(SQLModel, table=True):
    """Troca de exercicio valida SO nesta sessao - a rotina salva nao muda.

    Precisa existir no banco (e nao so na memoria da tela) por dois motivos: a tela
    remonta a lista de exercicios lendo a rotina AO VIVO a cada carregamento, e o
    Safari do iPhone descarta e recarrega a aba sozinho. Sem isso, ao voltar para o
    treino o exercicio original reapareceria e as series ja feitas no substituto
    ficariam orfas - os blocos pareceriam nao feitos e dariam para registrar de novo.
    """

    __tablename__ = "session_exercise_swaps"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="workout_sessions.id", index=True, ondelete="CASCADE")
    routine_exercise_id: int = Field(foreign_key="routine_exercises.id", ondelete="CASCADE")
    exercise_id: int = Field(foreign_key="exercises.id")  # o substituto
    created_at: datetime = Field(default_factory=utcnow)


class CyclePhase(str, Enum):
    menstrual = "menstrual"
    follicular = "follicular"  # folicular: do fim da menstruacao ate perto da ovulacao
    ovulatory = "ovulatory"
    luteal = "luteal"  # lutea: da ovulacao ate o proximo periodo


class CycleMode(str, Enum):
    manual = "manual"  # a pessoa marca a fase atual direto
    by_date = "by_date"  # informa a data do ultimo periodo e o app estima


class CycleTracking(SQLModel, table=True):
    """Acompanhamento do ciclo menstrual (Fase A) - uma linha por usuaria.

    Tabela propria, e nao colunas em profiles: isso
    mantem o dado de saude mais sensivel do app num lugar so - facil de exportar
    (LGPD), facil de apagar, impossivel de vazar por um ProfileOut mais largo.

    enabled e opt-in EXPLICITO: nunca e derivado do sexo cadastrado. Desligar preserva
    a linha (a pessoa pode religar sem reconfigurar); apagar a conta apaga junto
    (CASCADE, como toda tabela do usuario)."""

    __tablename__ = "cycle_tracking"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True, ondelete="CASCADE")
    enabled: bool = Field(default=False)
    mode: CycleMode = Field(default=CycleMode.manual)
    # modo manual: a fase marcada; modo by_date: ignorada (a fase vem da estimativa)
    phase: CyclePhase | None = Field(default=None)
    last_period_date: date | None = Field(default=None)
    # duracao tipica do ciclo, usada SO na estimativa por data (21-40 validado no schema)
    cycle_length_days: int = Field(default=28)
    updated_at: datetime = Field(default_factory=utcnow)


class NewsImportance(str, Enum):
    """Quanto uma novidade pode atrapalhar quem so queria usar o app.

    A distincao existe porque interromper custa: depois de dois ou tres modais
    seguidos a pessoa aprende a fechar sem ler, e ai o aviso nao serve nem quando
    importa. Entao so o que muda o que o app te diz para fazer vira 'important'."""

    normal = "normal"  # aparece na lista e no contador; nao interrompe
    important = "important"  # abre a modal uma vez, na proxima abertura do app


class NewsItem(SQLModel, table=True):
    """Novidade do app (o que mudou, correcoes que afetam o usuario).

    Titulo e corpo ficam nos tres idiomas no proprio registro. Isso foge da regra
    geral do projeto (texto de UI vive em messages/*.json, a API devolve codigo) e o
    motivo e simples: aqui o texto e escrito em tempo de execucao, no painel admin,
    entao nao existe chave para o paraglide compilar. E dado, nao interface.

    'published' e o controle do admin: novidade nasce publicada e pode ser tirada do ar
    sem apagar. 'published_on' e a data que o usuario ve, separada de created_at para
    permitir escrever hoje uma novidade datada de ontem."""

    __tablename__ = "news_items"

    id: int | None = Field(default=None, primary_key=True)
    published_on: date = Field(index=True)
    importance: NewsImportance = Field(default=NewsImportance.normal)
    published: bool = Field(default=True, index=True)
    title_pt_br: str
    body_pt_br: str
    title_en: str
    body_en: str
    title_es: str
    body_es: str
    created_at: datetime = Field(default_factory=utcnow)


class NewsRead(SQLModel, table=True):
    """Marca que um usuario ja viu uma novidade.

    Precisa ser tabela e nao localStorage: o "ja vi" tem que atravessar troca de
    aparelho e reinstalacao, senao a pessoa reve o mesmo aviso a cada celular novo.
    Chave composta (user_id, news_id) para o marcar-como-lido ser idempotente."""

    __tablename__ = "news_reads"

    user_id: int = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    news_id: int = Field(foreign_key="news_items.id", primary_key=True, ondelete="CASCADE")
    read_at: datetime = Field(default_factory=utcnow)
