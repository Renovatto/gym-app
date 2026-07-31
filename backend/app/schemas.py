from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    ActivityIntensity,
    ActivityLevel,
    ConnectionStatus,
    CutIntensity,
    Equipment,
    EntrySource,
    FavoriteKind,
    ExerciseKind,
    ExerciseLevel,
    FoodCategory,
    MealType,
    MuscleGroup,
    Objective,
    Plan,
    Sex,
    SharedItemKind,
    StandaloneActivityKind,
    WeightSource,
)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    locale: str = "pt-BR"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    locale: str
    plan: Plan
    has_profile: bool
    is_admin: bool = False


class FeedbackIn(BaseModel):
    # module: workout | diet | progress | profile | other (front faz o i18n)
    module: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=2000)


class FeedbackOut(BaseModel):
    id: int
    module: str
    description: str
    read: bool
    created_at: datetime
    user_email: str  # so o admin ve a lista, entao expor o e-mail e ok aqui


class FeedbackReadUpdate(BaseModel):
    read: bool


class ProfileIn(BaseModel):
    first_name: str | None = Field(default=None, max_length=60)
    last_name: str | None = Field(default=None, max_length=60)
    height_cm: float = Field(gt=50, lt=280)
    weight_kg: float = Field(gt=20, lt=400)
    birthdate: date
    sex: Sex
    activity_level: ActivityLevel
    objective: Objective
    cut_intensity: CutIntensity = CutIntensity.moderate
    diet_enabled: bool = False
    scale_mac: str | None = None


class ProfileOut(BaseModel):
    first_name: str | None
    last_name: str | None
    height_cm: float
    weight_kg: float | None
    birthdate: date
    sex: Sex
    activity_level: ActivityLevel
    objective: Objective
    cut_intensity: CutIntensity
    diet_enabled: bool
    scale_mac: str | None


class GoalsOut(BaseModel):
    age: int
    bmi: float
    # Classificacao da OMS: underweight | normal | overweight | obese_1 | obese_2 | obese_3
    bmi_category: str
    bmr_kcal: int
    tdee_kcal: int
    target_kcal: int
    protein_g: int
    fat_g: int
    carbs_g: int
    water_ml: int


# Campos de composicao corporal informados pela balanca (todos opcionais).
# Reutilizados na entrada (WeightLogIn) e na saida (WeightLogOut).
class BodyCompositionFields(BaseModel):
    fat_percentage: float | None = Field(default=None, ge=0, le=80)  # gordura em %
    fat_mass_kg: float | None = Field(default=None, ge=0, le=300)  # gordura em kg
    skeletal_muscle_percentage: float | None = Field(default=None, ge=0, le=100)  # musculo esqueletico %
    skeletal_muscle_kg: float | None = Field(default=None, ge=0, le=200)  # musculo esqueletico kg
    muscle_percentage: float | None = Field(default=None, ge=0, le=100)  # musculo total %
    muscle_mass_kg: float | None = Field(default=None, ge=0, le=200)  # musculo total kg
    water_percentage: float | None = Field(default=None, ge=0, le=100)  # agua corporal %
    water_mass_kg: float | None = Field(default=None, ge=0, le=200)  # agua em kg
    visceral_fat_index: float | None = Field(default=None, ge=0, le=60)  # V-fat = gordura visceral
    scale_bmr_kcal: int | None = Field(default=None, ge=0, le=5000)  # BMR estimado pela balanca


# Medidas de fita metrica (todas opcionais). Mixin SEPARADA da balanca de proposito:
# a tela e o painel precisam distinguir o que veio de onde.
class TapeMeasurementFields(BaseModel):
    waist_cm: float | None = Field(default=None, ge=30, le=250)  # cintura
    neck_cm: float | None = Field(default=None, ge=15, le=80)  # pescoco
    hip_cm: float | None = Field(default=None, ge=40, le=250)  # quadril
    arm_cm: float | None = Field(default=None, ge=10, le=80)  # braco
    thigh_cm: float | None = Field(default=None, ge=20, le=120)  # coxa
    chest_cm: float | None = Field(default=None, ge=40, le=250)  # peito


class WeightLogIn(BodyCompositionFields, TapeMeasurementFields):
    weight_kg: float = Field(gt=20, lt=400)
    source: WeightSource = WeightSource.manual
    logged_at: datetime | None = None


class WeightLogOut(BodyCompositionFields, TapeMeasurementFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weight_kg: float
    source: WeightSource
    logged_at: datetime


class WeightHistoryOut(BaseModel):
    logs: list[WeightLogOut]
    current_kg: float | None
    start_kg: float | None
    delta_kg: float | None
    # ultimo weigh-in que trouxe composicao corporal (para o painel de composicao)
    latest_body_composition: WeightLogOut | None = None


class ActivityEstimateOut(BaseModel):
    kcal: float


class StandaloneActivityIn(BaseModel):
    entry_date: date
    time_of_day: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    kind: StandaloneActivityKind
    duration_min: int = Field(gt=0, le=600)
    intensity: ActivityIntensity
    distance_km: float | None = Field(default=None, gt=0, le=300)
    kcal: float | None = Field(default=None, ge=0, le=5000)  # None = usa a estimativa automatica


class StandaloneActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    time_of_day: str
    kind: StandaloneActivityKind
    duration_min: int
    intensity: ActivityIntensity
    distance_km: float | None
    kcal: float
    kcal_is_manual: bool


class WaterLogIn(BaseModel):
    amount_ml: int = Field(gt=0, le=5000)


class WaterLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_ml: int
    logged_at: datetime


class WaterDayOut(BaseModel):
    date: date
    total_ml: int
    goal_ml: int
    logs: list[WaterLogOut]


class LocaleUpdate(BaseModel):
    locale: str = Field(pattern=r"^(pt-BR|en|es)$")


class WeekSummaryOut(BaseModel):
    workouts: int
    # dias distintos com treino OU atividade avulsa (uniao, nunca soma: passar de 7
    # seria mentira). E o numero que responde "como foi minha semana?".
    active_days: int
    # QUAIS dias, nao so quantos: a tela marca cada dia da semana, entao "treinei
    # segunda e quarta" e uma informacao melhor que "treinei 2 dias".
    active_dates: list[date]
    activities: int  # quantas atividades avulsas
    activities_kcal: int  # gasto estimado delas
    # Soma de repeticoes x peso. Continua no schema porque a tela de detalhe do treino
    # ainda usa, mas saiu do resumo semanal: da zero para peso corporal e para cardio.
    total_volume_kg: float
    total_sets: int
    avg_kcal: int
    days_logged_diet: int
    avg_water_ml: int
    days_with_water: int


class AchievementOut(BaseModel):
    code: str
    icon: str
    category: str  # workout | streak | weight | diet
    unlocked: bool
    unlocked_at: datetime | None
    progress_current: float  # valor atual da metrica
    progress_goal: float  # meta para desbloquear


class AchievementsOut(BaseModel):
    achievements: list[AchievementOut]
    weekly_streak: int
    workouts_this_week: int
    newly_unlocked: list[str]  # desbloqueadas nesta consulta (para celebrar na tela)
    # Titulo evolutivo (escada fixa por total de treinos - nunca peso/corpo).
    title_tier: int  # indice na escada (0 = iniciante)
    title_progress_current: float  # total de treinos atual
    title_progress_next: float | None  # meta do PROXIMO nivel (None = ja no topo)


class CoachNote(BaseModel):
    # code = mensagem traduzida no frontend; severity controla a cor (warn/info).
    code: str
    severity: str  # "warn" | "info"


class CoachOut(BaseModel):
    notes: list[CoachNote]
    # dias desde a ultima pesagem (None = nunca pesou). Alimenta o lembrete de pesagem.
    days_since_weigh_in: int | None
    # Pesagens ja feitas na janela do TDEE adaptativo, para o lembrete mostrar o
    # progresso ("3/8"). None = nao se aplica: dieta desligada ou minimo ja atingido.
    weigh_ins_in_window: int | None = None
    min_weigh_ins: int = 0


class AdaptiveTdeeOut(BaseModel):
    # Resultado do TDEE adaptativo: manutencao real estimada pelos dados do usuario.
    has_enough_data: bool
    span_days: int  # dias entre a primeira e a ultima pesagem analisada
    weigh_ins: int  # pesagens na janela
    days_logged: int  # dias com diario alimentar na janela
    # Quanto falta para a estimativa ficar pronta. Vem do backend (e nao fixo no
    # frontend) para os minimos terem uma fonte unica: adaptive.py.
    min_span_days: int
    min_weigh_ins: int
    min_days_logged: int
    avg_intake_kcal: int  # media diaria consumida
    weekly_change_kg: float  # variacao de peso por semana (negativo = perdendo)
    estimated_maintenance_kcal: int | None  # manutencao REAL estimada
    formula_tdee_kcal: int  # manutencao ESTIMADA pela formula (para comparar)
    current_target_kcal: int  # meta atual (baseada na formula)
    suggested_target_kcal: int | None  # meta sugerida com base na manutencao real
    # A estimativa e confiavel o bastante para virar a meta do app? False esconde o
    # botao de adotar (mas o numero continua visivel, so que sem virar meta).
    can_adopt: bool
    # codigo traduzido no frontend: NOT_ENOUGH_DATA, ON_TRACK, TOO_SLOW, STALLED,
    # TOO_FAST, ESTIMATE_READY
    message_code: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailChange(BaseModel):
    new_email: EmailStr
    current_password: str | None = None  # opcional: a troca de e-mail nao exige senha


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# --- Treino ---------------------------------------------------------------


class ExerciseOut(BaseModel):
    id: int
    slug: str
    name: str
    muscle_group: MuscleGroup
    equipment: Equipment
    kind: ExerciseKind
    level: ExerciseLevel | None
    media_urls: list[str]
    is_custom: bool


class RoutineItemIn(BaseModel):
    exercise_id: int
    target_sets: int = Field(default=3, ge=1, le=20)
    target_reps: int = Field(default=10, ge=0, le=100)
    target_weight_kg: float | None = Field(default=None, ge=0, le=1000)
    target_duration_min: int | None = Field(default=None, ge=1, le=300)
    rest_seconds: int = Field(default=90, ge=0, le=600)


class RoutineIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    items: list[RoutineItemIn]


class RoutineItemOut(BaseModel):
    id: int
    exercise: ExerciseOut
    position: int
    target_sets: int
    target_reps: int
    target_weight_kg: float | None
    target_duration_min: int | None
    rest_seconds: int
    last_weight_kg: float | None = None


class RoutineOut(BaseModel):
    id: int
    name: str
    position: int
    items: list[RoutineItemOut]


class SetLogIn(BaseModel):
    exercise_id: int
    set_number: int = Field(ge=1, le=50)
    reps: int = Field(default=0, ge=0, le=100)
    weight_kg: float = Field(default=0, ge=0, le=1000)
    duration_min: float | None = Field(default=None, ge=0, le=600)
    done: bool = True


class SetLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    set_number: int
    reps: int
    weight_kg: float
    duration_min: float | None
    done: bool


class SessionStartIn(BaseModel):
    routine_id: int | None = None


class RoutineCompleteIn(BaseModel):
    """Marcar um treino como feito. Sem 'day', o treino e registrado agora (fluxo
    normal). Com 'day', registra um treino de data passada que a pessoa esqueceu
    de lancar - 'tz_offset' e o Date.getTimezoneOffset() do cliente."""

    day: date | None = None
    tz_offset: int = Field(default=0, ge=-840, le=840)


class ExerciseSwapOut(BaseModel):
    """Troca feita nesta sessao. A tela aplica antes de montar os blocos."""

    routine_exercise_id: int
    exercise: ExerciseOut
    original_exercise: ExerciseOut  # para a tela poder dizer "no lugar de X"
    last_weight_kg: float | None  # ultima carga usada NO SUBSTITUTO


class SessionOut(BaseModel):
    id: int
    routine_id: int | None
    routine_name: str | None
    started_at: datetime
    finished_at: datetime | None
    sets: list[SetLogOut]
    swaps: list[ExerciseSwapOut] = []


class ExerciseSwapIn(BaseModel):
    exercise_id: int


class AlternativeExerciseOut(BaseModel):
    """Candidato a substituto, com a carga que a pessoa ja usou nele (se usou)."""

    exercise: ExerciseOut
    last_weight_kg: float | None
    same_equipment: bool  # ordena primeiro, mas a tela tambem marca visualmente


class SessionSummaryOut(BaseModel):
    id: int
    # id da rotina treinada (None = treino livre ou rotina ja excluida). E o que
    # permite a tela apontar o PROXIMO treino do ciclo: o seguinte ao ultimo feito.
    routine_id: int | None
    routine_name: str | None
    started_at: datetime
    finished_at: datetime | None
    total_sets: int
    total_volume_kg: float


class WorkoutDayExerciseOut(BaseModel):
    # exercicio de um treino ja concluido, com suas series (somente leitura).
    exercise_name: str
    is_cardio: bool
    sets: list[SetLogOut]


class WorkoutDayDetailOut(BaseModel):
    # treino concluido de um dia, agrupado por exercicio (visualizacao).
    session_id: int
    routine_name: str | None
    started_at: datetime
    finished_at: datetime | None
    total_volume_kg: float
    total_sets: int
    exercises: list[WorkoutDayExerciseOut]


# --- Dieta ----------------------------------------------------------------


class MacrosOut(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class FoodPortionOut(BaseModel):
    label_key: str
    grams: float


class FoodOut(BaseModel):
    id: int
    slug: str
    name: str
    category: FoodCategory
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    default_portion_g: float
    portions: list[FoodPortionOut]
    is_custom: bool
    is_favorite: bool = False


class FoodIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: FoodCategory = FoodCategory.other
    kcal: float = Field(ge=0, le=1000)
    protein_g: float = Field(ge=0, le=100)
    carbs_g: float = Field(ge=0, le=100)
    fat_g: float = Field(ge=0, le=100)
    default_portion_g: float = Field(default=100, gt=0, le=2000)


class RecipeIngredientIn(BaseModel):
    food_id: int
    grams: float = Field(gt=0, le=5000)


class RecipeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    servings: int = Field(default=1, ge=1, le=50)
    ingredients: list[RecipeIngredientIn]


class RecipeIngredientOut(BaseModel):
    id: int
    food: FoodOut
    grams: float
    macros: MacrosOut


class RecipeOut(BaseModel):
    id: int
    name: str
    servings: int
    ingredients: list[RecipeIngredientOut]
    total: MacrosOut
    per_serving: MacrosOut
    is_favorite: bool = False


class DiaryEntryIn(BaseModel):
    entry_date: date
    meal_type: MealType
    source: EntrySource
    food_id: int | None = None
    recipe_id: int | None = None
    quantity: float = Field(gt=0, le=5000)


class DiaryEntryUpdate(BaseModel):
    quantity: float = Field(gt=0, le=5000)


class DiaryFromLibraryIn(BaseModel):
    """Adotar (idempotente) uma receita da biblioteca e ja lancar no diario, 1 toque."""

    slug: str
    entry_date: date
    meal_type: MealType
    quantity: float = Field(default=1, gt=0, le=50)  # porcoes


class DiaryEntryOut(BaseModel):
    id: int
    meal_type: MealType
    source: EntrySource
    food_id: int | None
    recipe_id: int | None
    name: str
    quantity: float
    macros: MacrosOut


class MealGroupOut(BaseModel):
    meal_type: MealType
    entries: list[DiaryEntryOut]
    subtotal: MacrosOut


class DiaryDayOut(BaseModel):
    date: date
    meals: list[MealGroupOut]
    totals: MacrosOut
    goals: MacrosOut | None


# --- Biblioteca de receitas semente (fase 2) -------------------------------


class LibraryIngredientOut(BaseModel):
    name: str
    grams: float
    macros: MacrosOut


class LibraryRecipeOut(BaseModel):
    slug: str
    name: str
    # tags de perfil: protein | quick | veggie | sweet | budget (front faz o i18n)
    tags: list[str]
    servings: int
    total: MacrosOut
    per_serving: MacrosOut
    ingredients: list[LibraryIngredientOut]
    # True quando o usuario ja adotou esta receita e a marcou como favorita
    is_favorite: bool = False


class RecipeSuggestionOut(BaseModel):
    """Sugestao de receita da biblioteca para fechar a lacuna de uma refeicao/dia.
    Adicionar (1 toque) adota a receita e lanca a porcao no diario."""

    slug: str  # identifica a receita na biblioteca (para adotar + lancar)
    name: str
    tags: list[str]
    macros: MacrosOut  # de UMA porcao (o que sera lancado)
    is_favorite: bool = False


class FavoriteToggleIn(BaseModel):
    kind: FavoriteKind
    ref_id: int  # food_id (kind=food) ou recipe_id (kind=recipe)


class FavoriteToggleOut(BaseModel):
    favorite: bool  # novo estado apos alternar


# --- Recomendacao da dieta (motor de encaixe) -----------------------------


class FoodSuggestionOut(BaseModel):
    food: FoodOut
    grams: float
    macros: MacrosOut


class DiaryGapOut(BaseModel):
    date: date
    goals: MacrosOut | None
    consumed: MacrosOut
    remaining: MacrosOut | None
    # Codigo do macro que mais falta (front faz o i18n):
    # protein | carbs | fat | calories | complete | no_goal
    primary: str
    suggestions: list[FoodSuggestionOut]
    recipe_suggestions: list[RecipeSuggestionOut] = []


class PantryRecipeMatchOut(BaseModel):
    """Receita da biblioteca que da pra fazer com o que a pessoa tem em casa (mais os
    itens basicos, sempre disponiveis). quantity ja vem escalado (porcoes fracionarias)
    para fechar a lacuna do dia - o mesmo campo aceito por DiaryFromLibraryIn.quantity."""

    slug: str
    name: str
    tags: list[str]
    quantity: float
    macros: MacrosOut  # ja escalado por quantity
    is_favorite: bool = False
    match_ratio: float  # 0..1, sobre os ingredientes NAO-basicos da receita
    missing: list[str] = []  # nomes localizados dos ingredientes que faltam


class BuildMealOut(BaseModel):
    """Resultado de 'montar refeicao com o que tenho em casa': receitas que da pra
    cozinhar + alimentos avulsos que fecham a lacuna do dia, dado o que a pessoa
    informou que tem (mesmos codigos de primary/no_goal/complete de DiaryGapOut)."""

    date: date
    remaining: MacrosOut | None
    primary: str
    recipe_matches: list[PantryRecipeMatchOut] = []
    food_matches: list[FoodSuggestionOut] = []


class SubstituteSourceOut(BaseModel):
    food: FoodOut
    grams: float
    macros: MacrosOut


class SubstituteItemOut(BaseModel):
    food: FoodOut
    grams: float
    macros: MacrosOut
    kcal_delta: float


class SubstitutesOut(BaseModel):
    source: SubstituteSourceOut
    # Macro-ancora igualado na troca: protein | carbs | fat | calories
    anchor: str
    items: list[SubstituteItemOut]


# --- Cardapio consultivo (plano por refeicao) -----------------------------


class MealPlanMealOut(BaseModel):
    meal_type: MealType
    target: MacrosOut  # alvo recomendado desta refeicao (fatia do dia)
    consumed: MacrosOut  # o que ja foi lancado nela
    remaining: MacrosOut  # lacuna adaptativa (alvo x consumido x sobra do dia)
    primary: str  # macro-alvo da refeicao: protein | carbs | fat | calories | complete
    suggestions: list[FoodSuggestionOut]
    recipe_suggestions: list[RecipeSuggestionOut] = []


class MealPlanOut(BaseModel):
    date: date
    goals: MacrosOut | None
    meals: list[MealPlanMealOut]


# --- Acompanhamento & periodizacao (fase 3) -------------------------------


class DietAdherenceOut(BaseModel):
    window: int  # janela em dias (ex.: 7)
    logged_days: int  # dias com lancamento na janela
    kcal_pct: int  # aderencia calorica media (0-100)
    protein_pct: int  # aderencia de proteina media (0-100)
    has_goal: bool  # False = perfil/pesagem incompletos


class RoutinePeriodizationOut(BaseModel):
    routine_id: int
    name: str
    started_on: date  # inicio do ciclo (criacao da rotina)
    renew_on: date  # validade sugerida = inicio + mesociclo
    weeks_active: int
    weeks_remaining: int  # semanas ate a validade (0 = ja venceu)
    due: bool  # passou da validade sugerida (mesociclo) -> hora de variar


class DietPeriodOut(BaseModel):
    started_on: date  # inicio do periodo (vigencia) da meta
    review_on: date  # validade sugerida = inicio + review_weeks
    objective: Objective  # objetivo daquele periodo (do perfil)
    review_weeks: int
    target_kcal: int  # meta calorica efetiva atual (ja com override, se houver)
    maintenance_kcal: int | None  # manutencao real adotada (override) ou None
    days_active: int
    due: bool  # passou da validade sugerida -> hora de revisar/renovar


# --- Busca externa de alimentos (fase 5) ----------------------------------


class ExternalFoodOut(BaseModel):
    name: str
    brand: str | None
    kcal: float  # valores por 100 g
    protein_g: float
    carbs_g: float
    fat_g: float


# --- Variar o treino (troca de exercicios, mesmo grupo muscular) -----------


class RoutineVariationItemOut(BaseModel):
    original_exercise: ExerciseOut
    new_exercise: ExerciseOut
    # alvos herdados do item original (mantem o esquema de series)
    target_sets: int
    target_reps: int
    target_weight_kg: float | None
    target_duration_min: int | None
    rest_seconds: int


class RoutineVariationOut(BaseModel):
    routine_id: int
    name: str
    items: list[RoutineVariationItemOut]


# --- Suplementos (adesao diaria; zero-macro nao entra no calculo de macros) ---


class SupplementIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    dose: str = Field(default="", max_length=40)


class SupplementOut(BaseModel):
    id: int
    name: str
    dose: str
    active: bool
    taken: bool  # tomado no dia consultado
    taken_last_7: int  # dias tomados nos ultimos 7 (consistencia)


class SupplementsDayOut(BaseModel):
    date: date
    items: list[SupplementOut]
    taken_count: int
    total: int


# --- Compartilhar entre contas --------------------------------------------


class ConnectionInviteIn(BaseModel):
    email: EmailStr


class ConnectionOut(BaseModel):
    id: int
    person_name: str  # nome da outra pessoa (ou o e-mail, se ela nao preencheu)
    person_email: str
    status: ConnectionStatus
    # quem convidou define o que a tela oferece: aceitar/recusar de um lado,
    # "convite enviado" do outro.
    i_invited: bool
    created_at: datetime


class ShareItemRefIn(BaseModel):
    item_kind: SharedItemKind
    item_id: int


class ShareOfferIn(BaseModel):
    # a conexao (e nao o id da pessoa) e o endereco: so da para oferecer a quem ja
    # aceitou se conectar com voce.
    connection_id: int
    items: list[ShareItemRefIn] = Field(min_length=1, max_length=50)


class ShareOfferOut(BaseModel):
    id: int
    item_kind: SharedItemKind
    item_name: str
    from_name: str
    created_at: datetime


class ReceivedItemOut(BaseModel):
    """Copia aceita, com a origem - e o que a pilula "Recebidas" usa para filtrar."""

    item_kind: SharedItemKind
    item_id: int
    from_name: str


# --- Composicao corporal (painel do Progresso) ----------------------------


class BodyFatBandOut(BaseModel):
    """Faixa de referencia de gordura corporal. O frontend traduz pela chave."""

    key: str  # essential | athlete | fitness | acceptable | high
    from_pct: float
    to_pct: float


class BodyCompositionPanelOut(BaseModel):
    """Leitura da ultima pesagem com bioimpedancia, ja com regua e tendencia.

    Tudo calculado no backend para a formula viver num lugar so (ver
    services/body_composition.py)."""

    measured_at: datetime | None = None
    weight_kg: float | None = None
    fat_percentage: float | None = None
    fat_mass_kg: float | None = None
    lean_mass_kg: float | None = None
    visceral_fat_index: float | None = None
    water_percentage: float | None = None

    # regua de referencia (muda conforme o sexo do perfil)
    bands: list[BodyFatBandOut] = []
    band_key: str | None = None
    gauge_min: float = 0
    gauge_max: float = 100

    # tendencia contra uma pesagem antiga o bastante para significar algo
    trend_days: int | None = None
    fat_percentage_delta: float | None = None
    lean_mass_delta_kg: float | None = None

    # alvo escolhido pela pessoa (o app nunca escolhe sozinho)
    target_fat_percentage: float | None = None
    target_weight_min_kg: float | None = None
    target_weight_max_kg: float | None = None

    # De onde veio o numero principal de gordura: "scale" | "tape" | None.
    # As duas estimativas viajam juntas para a tela comparar ("Balanca: X - Fita: Y") -
    # ambas erram, e fingir que uma delas e A verdade seria desonesto.
    fat_source: str | None = None
    fat_percentage_scale: float | None = None
    fat_percentage_tape: float | None = None
    # preferencia gravada no perfil: "auto" | "scale" | "tape"
    source_preference: str = "auto"

    # Medidas de fita da ultima pesagem que as trouxe
    waist_cm: float | None = None
    neck_cm: float | None = None
    hip_cm: float | None = None
    arm_cm: float | None = None
    thigh_cm: float | None = None
    chest_cm: float | None = None
    # cintura como marcador de risco (cortes da OMS): ok | increased | high
    waist_risk: str | None = None
    waist_risk_increased_cm: float | None = None
    waist_risk_high_cm: float | None = None
    # variacao das medidas na mesma janela da tendencia de gordura
    waist_delta_cm: float | None = None
    arm_delta_cm: float | None = None
    thigh_delta_cm: float | None = None


class BodyCompSourceIn(BaseModel):
    # auto = fita quando completa (erra menos), senao balanca
    source: str = Field(pattern=r"^(auto|scale|tape)$")


class BodyFatTargetIn(BaseModel):
    # None limpa o alvo. O piso de 5% evita alvo abaixo da gordura essencial.
    target_fat_percentage: float | None = Field(default=None, ge=5, le=45)


class SharingPendingCountOut(BaseModel):
    """Quantas coisas de compartilhamento esperam uma acao sua.

    Existe para o badge nao precisar baixar as duas listas inteiras so para desenhar
    um numero - a chamada roda a cada abertura do app."""

    invites: int  # convites de conexao que voce recebeu e ainda nao respondeu
    offers: int  # receitas/alimentos oferecidos, esperando aceite
    total: int
