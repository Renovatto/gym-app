// VITE_API_PORT permite ao start.sh avisar o front quando a porta padrão (8765)
// estava ocupada e o backend subiu em outra.
const API_PORT = import.meta.env.VITE_API_PORT ?? '8765';

// Sem VITE_API_URL, deriva a base da API do host acessado: assim funciona em
// localhost, no IP da rede local (celular via --host) e via túnel, sem rebuild.
function defaultApiUrl(): string {
	if (typeof window !== 'undefined') {
		return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
	}
	return `http://localhost:${API_PORT}`;
}

const API_URL: string = import.meta.env.VITE_API_URL ?? defaultApiUrl();

// Aborta requests pendurados (API dormindo/caindo) para o app sempre dar retorno
// em vez de travar. 60s cobre com folga o cold start do plano free do Render (~50s).
const REQUEST_TIMEOUT_MS = 60000;

const ACCESS_KEY = 'gymapp.access';
const REFRESH_KEY = 'gymapp.refresh';

export class ApiError extends Error {
	constructor(
		public code: string,
		public status: number,
		// Segundos que a API pediu para esperar antes de tentar de novo (cabecalho
		// Retry-After). Hoje so vem no bloqueio por excesso de tentativas de login.
		public retryAfterSeconds: number | null = null
	) {
		super(code);
	}
}

export interface TokenPair {
	access_token: string;
	refresh_token: string;
}

export interface UserOut {
	id: number;
	email: string;
	locale: string;
	plan: 'free' | 'premium';
	has_profile: boolean;
	is_admin: boolean;
}

// modulos do feedback (o front faz o i18n dos rotulos)
export type FeedbackModule = 'workout' | 'diet' | 'progress' | 'profile' | 'other';

export interface FeedbackReport {
	id: number;
	module: string;
	description: string;
	read: boolean;
	created_at: string;
	user_email: string;
}

export type Sex = 'male' | 'female';
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';
export type Objective = 'lose_fat' | 'maintain' | 'gain_muscle' | 'recomp';
// Intensidade do deficit (taxa de perda por semana). So tem efeito em lose_fat.
export type CutIntensity = 'light' | 'moderate' | 'aggressive';

export interface ProfileData {
	first_name: string | null;
	last_name: string | null;
	height_cm: number;
	weight_kg: number | null;
	birthdate: string;
	sex: Sex;
	activity_level: ActivityLevel;
	objective: Objective;
	cut_intensity: CutIntensity;
	diet_enabled: boolean;
	scale_mac: string | null;
	// Estado do tutorial guiado. So chega na leitura do perfil; quem escreve e o
	// PUT /me/tutorial, para o formulario "Meus dados" nao apagar o progresso.
	tutorial_enabled: boolean;
	tutorial_progress: Record<string, number>;
}

// O que o formulario "Meus dados" manda: o perfil sem os campos que ele nao edita.
export type ProfileInput = Omit<
	ProfileData,
	'weight_kg' | 'tutorial_enabled' | 'tutorial_progress'
> & { weight_kg: number };

export interface TutorialState {
	enabled: boolean;
	progress: Record<string, number>;
}

export type BmiCategory = 'underweight' | 'normal' | 'overweight' | 'obese_1' | 'obese_2' | 'obese_3';

export interface GoalsOut {
	age: number;
	bmi: number;
	bmi_category: BmiCategory;
	bmr_kcal: number;
	tdee_kcal: number;
	target_kcal: number;
	protein_g: number;
	fat_g: number;
	carbs_g: number;
	water_ml: number;
}

// Composicao corporal vinda da balanca de bioimpedancia (BIA). Todos opcionais.
export interface BodyComposition {
	fat_percentage: number | null; // gordura corporal em %
	fat_mass_kg: number | null; // peso da gordura em kg
	skeletal_muscle_percentage: number | null; // musculo esqueletico em %
	skeletal_muscle_kg: number | null; // musculo esqueletico em kg
	muscle_percentage: number | null; // musculo total em %
	muscle_mass_kg: number | null; // musculo total em kg
	water_percentage: number | null; // agua corporal em %
	water_mass_kg: number | null; // peso da agua em kg
	visceral_fat_index: number | null; // V-fat = gordura visceral (indice da balanca)
	scale_bmr_kcal: number | null; // BMR estimado pela balanca (kcal/dia)
}

// Medidas de fita metrica. Separadas da balanca porque a tela precisa distinguir:
// cintura/pescoco/quadril alimentam a estimativa de gordura, o resto e acompanhamento.
export interface TapeMeasurements {
	waist_cm: number | null; // cintura
	neck_cm: number | null; // pescoco
	hip_cm: number | null; // quadril
	arm_cm: number | null; // braco
	thigh_cm: number | null; // coxa
	chest_cm: number | null; // peito
}

export type BodyCompSource = 'auto' | 'scale' | 'tape';

export interface WeightLog extends BodyComposition, TapeMeasurements {
	id: number;
	weight_kg: number;
	source: 'manual' | 'ble';
	logged_at: string;
}

// Faixa de referencia de gordura corporal (chave traduzida no frontend).
export interface BodyFatBand {
	key: string; // essential | athlete | fitness | acceptable | high
	from_pct: number;
	to_pct: number;
}

// Painel de composicao corporal: a leitura da ultima pesagem com bioimpedancia,
// ja com regua, tendencia e a faixa de peso do alvo. Tudo calculado no backend.
export interface BodyCompositionPanel {
	measured_at: string | null;
	weight_kg: number | null;
	fat_percentage: number | null;
	fat_mass_kg: number | null;
	lean_mass_kg: number | null;
	visceral_fat_index: number | null;
	water_percentage: number | null;
	bands: BodyFatBand[];
	band_key: string | null;
	gauge_min: number;
	gauge_max: number;
	trend_days: number | null;
	fat_percentage_delta: number | null;
	lean_mass_delta_kg: number | null;
	target_fat_percentage: number | null;
	target_weight_min_kg: number | null;
	target_weight_max_kg: number | null;
	// de onde veio o numero principal, e as DUAS estimativas para comparar
	fat_source: 'scale' | 'tape' | null;
	fat_percentage_scale: number | null;
	fat_percentage_tape: number | null;
	source_preference: BodyCompSource;
	// medidas da ultima pesagem que as trouxe
	waist_cm: number | null;
	neck_cm: number | null;
	hip_cm: number | null;
	arm_cm: number | null;
	thigh_cm: number | null;
	chest_cm: number | null;
	// cintura como marcador de risco (cortes da OMS): ok | increased | high
	waist_risk: string | null;
	waist_risk_increased_cm: number | null;
	waist_risk_high_cm: number | null;
	waist_delta_cm: number | null;
	arm_delta_cm: number | null;
	thigh_delta_cm: number | null;
}

export interface WeightHistory {
	logs: WeightLog[];
	current_kg: number | null;
	start_kg: number | null;
	delta_kg: number | null;
	latest_body_composition: WeightLog | null;
}

// Entrada da pesagem: peso obrigatorio + composicao corporal opcional.
export type WeighInInput = { weight_kg: number } & Partial<BodyComposition> &
	Partial<TapeMeasurements>;

export interface WaterLog {
	id: number;
	amount_ml: number;
	logged_at: string;
}

export interface WaterDay {
	date: string;
	total_ml: number;
	goal_ml: number;
	logs: WaterLog[];
}

export type MuscleGroup =
	| 'chest'
	| 'back'
	| 'shoulders'
	| 'biceps'
	| 'triceps'
	| 'legs'
	| 'glutes'
	| 'abs'
	| 'calves'
	| 'cardio';

export type MuscleRegion =
	| 'chest_upper'
	| 'chest_mid'
	| 'chest_lower'
	| 'lats'
	| 'upper_back'
	| 'traps'
	| 'lower_back'
	| 'delt_front'
	| 'delt_side'
	| 'delt_rear'
	| 'biceps'
	| 'forearms'
	| 'triceps_long'
	| 'triceps_lateral'
	| 'quads'
	| 'hamstrings'
	| 'adductors'
	| 'abductors'
	| 'glute_max'
	| 'glute_med'
	| 'abs_upper'
	| 'abs_lower'
	| 'obliques'
	| 'core'
	| 'gastrocnemius'
	| 'soleus';

export type Equipment =
	| 'barbell'
	| 'dumbbell'
	| 'machine'
	| 'cable'
	| 'bodyweight'
	| 'kettlebell'
	| 'band'
	| 'other';

export type ExerciseKind = 'strength' | 'cardio';
export type ExerciseLevel = 'beginner' | 'intermediate' | 'expert';

export interface Exercise {
	id: number;
	slug: string;
	name: string;
	muscle_group: MuscleGroup;
	muscle_region: MuscleRegion | null;
	equipment: Equipment;
	kind: ExerciseKind;
	level: ExerciseLevel | null;
	media_urls: string[];
	is_custom: boolean;
}

export interface RoutineItem {
	id: number;
	exercise: Exercise;
	position: number;
	target_sets: number;
	target_reps: number;
	target_weight_kg: number | null;
	target_duration_min: number | null;
	rest_seconds: number;
	last_weight_kg: number | null;
}

export interface Routine {
	id: number;
	name: string;
	position: number;
	items: RoutineItem[];
	// null = ativa (no ciclo); com data = arquivada (fora do ciclo, mas consultavel)
	archived_at: string | null;
}

export interface RoutineItemInput {
	exercise_id: number;
	target_sets: number;
	target_reps: number;
	target_weight_kg: number | null;
	target_duration_min: number | null;
	rest_seconds: number;
}

export interface RoutineVariationItem {
	original_exercise: Exercise;
	new_exercise: Exercise;
	target_sets: number;
	target_reps: number;
	target_weight_kg: number | null;
	target_duration_min: number | null;
	rest_seconds: number;
}

export interface RoutineVariation {
	routine_id: number;
	name: string;
	items: RoutineVariationItem[];
}

export interface SetLog {
	id: number;
	exercise_id: number;
	set_number: number;
	reps: number;
	weight_kg: number;
	duration_min: number | null;
	done: boolean;
}

// Troca de exercicio valida so nesta sessao (a rotina salva nao muda).
export interface ExerciseSwap {
	routine_exercise_id: number;
	exercise: Exercise;
	original_exercise: Exercise;
	last_weight_kg: number | null;
}

export interface AlternativeExercise {
	exercise: Exercise;
	last_weight_kg: number | null;
	same_equipment: boolean;
}

export interface WorkoutSession {
	id: number;
	routine_id: number | null;
	routine_name: string | null;
	started_at: string;
	finished_at: string | null;
	sets: SetLog[];
	swaps: ExerciseSwap[];
}

export interface SessionSummary {
	id: number;
	// id da rotina (null = treino livre ou rotina excluida); aponta o proximo do ciclo
	routine_id: number | null;
	routine_name: string | null;
	started_at: string;
	finished_at: string | null;
	total_sets: number;
	total_volume_kg: number;
}

// Visualizacao (somente leitura) de um treino concluido de um dia.
export interface WorkoutDayExercise {
	exercise_name: string;
	is_cardio: boolean;
	sets: SetLog[];
}

export interface WorkoutDayDetail {
	session_id: number;
	routine_name: string | null;
	started_at: string;
	finished_at: string | null;
	total_volume_kg: number;
	total_sets: number;
	exercises: WorkoutDayExercise[];
}

export interface WeekSummary {
	workouts: number;
	// dias distintos com treino OU atividade avulsa (uniao, nunca soma)
	active_days: number;
	// quais dias tiveram movimento (YYYY-MM-DD), para marcar cada dia da semana
	active_dates: string[];
	activities: number;
	activities_kcal: number;
	total_volume_kg: number;
	total_sets: number;
	avg_kcal: number;
	days_logged_diet: number;
	avg_water_ml: number;
	days_with_water: number;
}

// Conquista (gamificacao). Nome/descricao sao traduzidos no frontend pelo code.
export interface AchievementItem {
	code: string;
	icon: string;
	category: string;
	unlocked: boolean;
	unlocked_at: string | null;
	progress_current: number;
	progress_goal: number;
}

export interface AchievementsResult {
	achievements: AchievementItem[];
	weekly_streak: number;
	workouts_this_week: number;
	newly_unlocked: string[];
	// Titulo evolutivo (escada fixa por total de treinos - nunca peso/corpo).
	title_tier: number;
	title_progress_current: number;
	title_progress_next: number | null;
}

// Dica do coach por regras (code traduzido no frontend; severity define a cor).
export interface CoachNote {
	code: string;
	severity: 'warn' | 'info';
}

export interface CoachResult {
	notes: CoachNote[];
	days_since_weigh_in: number | null;
	// Progresso de pesagens rumo ao TDEE adaptativo. null = nao se aplica.
	weigh_ins_in_window: number | null;
	min_weigh_ins: number;
}

// Resultado do TDEE adaptativo (manutencao real estimada a partir dos dados).
export interface AdaptiveTdee {
	has_enough_data: boolean;
	span_days: number;
	weigh_ins: number;
	days_logged: number;
	// Dias que tinham registro mas ficaram pela metade e nao entraram na media.
	days_discarded: number;
	// Minimos vindos do backend (fonte unica), para a tela mostrar "quanto falta".
	min_span_days: number;
	min_weigh_ins: number;
	min_days_logged: number;
	avg_intake_kcal: number;
	weekly_change_kg: number;
	estimated_maintenance_kcal: number | null;
	// Gasto em repouso: referencia que torna a estimativa compreensivel na tela.
	bmr_kcal: number;
	formula_tdee_kcal: number;
	current_target_kcal: number;
	suggested_target_kcal: number | null;
	// Estimativa confiavel o bastante para virar meta? False esconde o botao de adotar.
	can_adopt: boolean;
	message_code: string;
}

// --- Novidades do app ---
// O texto ja vem traduzido do servidor (o conteudo e escrito no admin em tempo de
// execucao, entao nao passa pelo paraglide como o resto das strings de UI).
export interface NewsItem {
	id: number;
	published_on: string;
	importance: 'normal' | 'important';
	title: string;
	body: string;
	read: boolean;
}

export interface NewsFeed {
	items: NewsItem[];
	unread_count: number;
	// Novidade importante nao lida que deve abrir a modal; null = nao interrompe.
	pending_important: NewsItem | null;
}

// --- Dieta ---
export type FoodCategory =
	| 'bakery'
	| 'cereal_grain'
	| 'tuber'
	| 'legume'
	| 'meat'
	| 'seafood'
	| 'egg'
	| 'dairy'
	| 'vegetable'
	| 'fruit'
	| 'nuts_seeds'
	| 'fat'
	| 'sweet'
	| 'sauce_condiment'
	| 'beverage'
	| 'prepared'
	| 'supplement'
	| 'other';

export type MealType =
	| 'breakfast'
	| 'pre_workout'
	| 'post_workout'
	| 'lunch'
	| 'snack'
	| 'dinner'
	| 'supper'
	| 'other';
export type EntrySource = 'food' | 'recipe';

export type StandaloneActivityKind =
	| 'running'
	| 'cycling'
	| 'walking'
	| 'yoga'
	| 'pilates'
	| 'boxing'
	| 'swimming'
	| 'dance'
	| 'other';
export type ActivityIntensity = 'light' | 'moderate' | 'hard';

// --- Compartilhar entre contas -------------------------------------------
export type ConnectionStatus = 'pending' | 'accepted' | 'blocked';
export type SharedItemKind = 'recipe' | 'food';

export interface Connection {
	id: number;
	person_name: string;
	person_email: string;
	status: ConnectionStatus;
	// quem convidou: define se a tela mostra aceitar/recusar ou "convite enviado"
	i_invited: boolean;
	created_at: string;
}

export interface ShareOffer {
	id: number;
	item_kind: SharedItemKind;
	item_name: string;
	from_name: string;
	created_at: string;
}

export interface ShareItemRef {
	item_kind: SharedItemKind;
	item_id: number;
}

export interface SharingPendingCount {
	invites: number; // convites de conexao esperando sua resposta
	offers: number; // receitas/alimentos esperando aceite
	total: number;
}

export interface ReceivedItem {
	item_kind: SharedItemKind;
	item_id: number;
	from_name: string;
}

export interface StandaloneActivity {
	id: number;
	entry_date: string;
	time_of_day: string;
	kind: StandaloneActivityKind;
	duration_min: number;
	intensity: ActivityIntensity;
	distance_km: number | null;
	kcal: number;
	kcal_is_manual: boolean;
}

export interface StandaloneActivityInput {
	entry_date: string;
	time_of_day: string;
	kind: StandaloneActivityKind;
	duration_min: number;
	intensity: ActivityIntensity;
	distance_km?: number | null;
	kcal?: number | null;
}

export interface Macros {
	kcal: number;
	protein_g: number;
	carbs_g: number;
	fat_g: number;
}

export interface FoodPortion {
	label_key: string;
	grams: number;
}

export interface Food {
	id: number;
	slug: string;
	name: string;
	category: FoodCategory;
	kcal: number;
	protein_g: number;
	carbs_g: number;
	fat_g: number;
	default_portion_g: number;
	portions: FoodPortion[];
	is_custom: boolean;
	is_favorite: boolean;
}

export interface RecipeIngredient {
	id: number;
	food: Food;
	grams: number;
	macros: Macros;
}

export interface Recipe {
	id: number;
	name: string;
	servings: number;
	ingredients: RecipeIngredient[];
	total: Macros;
	per_serving: Macros;
	is_favorite: boolean;
}

export interface DiaryEntry {
	id: number;
	meal_type: MealType;
	source: EntrySource;
	food_id: number | null;
	recipe_id: number | null;
	name: string;
	quantity: number;
	// gramas equivalentes: alimento = quantity, receita = porcoes x peso da porcao.
	// Nulo so quando a receita sumiu e nao da para converter.
	grams: number | null;
	macros: Macros;
}

export interface MealGroup {
	meal_type: MealType;
	entries: DiaryEntry[];
	subtotal: Macros;
}

export interface DiaryDay {
	date: string;
	meals: MealGroup[];
	totals: Macros;
	goals: Macros | null;
}

// --- Recomendacao da dieta (motor de encaixe) ---
export type GapPrimary = 'protein' | 'carbs' | 'fat' | 'calories' | 'complete' | 'no_goal';
export type MacroAnchor = 'protein' | 'carbs' | 'fat' | 'calories';

export interface FoodSuggestion {
	food: Food;
	grams: number;
	macros: Macros;
	// esta sugestao subiu por causa da fase do ciclo (a tela marca com um selo)
	from_phase?: boolean;
}

// Sugestao de receita da biblioteca (adotar+lancar em 1 toque via slug).
export interface RecipeSuggestion {
	slug: string;
	name: string;
	tags: string[];
	macros: Macros; // de UMA porcao
	is_favorite: boolean;
}

export interface DiaryGap {
	date: string;
	goals: Macros | null;
	consumed: Macros;
	remaining: Macros | null;
	primary: GapPrimary;
	suggestions: FoodSuggestion[];
	recipe_suggestions: RecipeSuggestion[];
}

// "Montar refeicao com o que tenho em casa": receita da biblioteca que da pra
// cozinhar com o que foi selecionado (+ itens basicos). quantity ja vem escalado.
export interface PantryRecipeMatch {
	slug: string;
	name: string;
	tags: string[];
	quantity: number;
	macros: Macros;
	is_favorite: boolean;
	match_ratio: number; // 0..1
	missing: string[]; // nomes localizados do que falta
}

export interface BuildMeal {
	date: string;
	remaining: Macros | null;
	primary: GapPrimary;
	recipe_matches: PantryRecipeMatch[];
	food_matches: FoodSuggestion[];
}

export interface SubstituteItem {
	food: Food;
	grams: number;
	macros: Macros;
	kcal_delta: number;
}

export interface Substitutes {
	source: { food: Food; grams: number; macros: Macros };
	anchor: MacroAnchor;
	items: SubstituteItem[];
}

export interface MealPlanMeal {
	meal_type: MealType;
	target: Macros;
	consumed: Macros;
	remaining: Macros;
	primary: GapPrimary;
	suggestions: FoodSuggestion[];
	recipe_suggestions: RecipeSuggestion[];
}

export interface MealPlan {
	date: string;
	goals: Macros | null;
	meals: MealPlanMeal[];
}

export interface DietAdherence {
	window: number;
	logged_days: number;
	kcal_pct: number;
	protein_pct: number;
	has_goal: boolean;
}

export interface RoutinePeriodization {
	routine_id: number;
	name: string;
	started_on: string;
	renew_on: string;
	weeks_active: number;
	weeks_remaining: number;
	due: boolean;
}

export interface DietPeriod {
	started_on: string;
	review_on: string;
	objective: Objective;
	review_weeks: number;
	target_kcal: number;
	maintenance_kcal: number | null;
	days_active: number;
	due: boolean;
}

export interface ExternalFood {
	name: string;
	brand: string | null;
	kcal: number;
	protein_g: number;
	carbs_g: number;
	fat_g: number;
}

export interface FoodInput {
	name: string;
	category: FoodCategory;
	kcal: number;
	protein_g: number;
	carbs_g: number;
	fat_g: number;
	default_portion_g: number;
	portion?: FoodPortion | null;
}

export interface LibraryRecipe {
	slug: string;
	name: string;
	tags: string[];
	servings: number;
	total: Macros;
	per_serving: Macros;
	ingredients: { name: string; grams: number; macros: Macros }[];
	is_favorite: boolean;
}

export type FavoriteKind = 'food' | 'recipe';

// Forma comum para a modal de visualizacao (read-only) de uma receita, servindo
// tanto a biblioteca (LibraryRecipe) quanto as receitas do usuario (mapeadas).
export interface RecipeView {
	name: string;
	tags: string[];
	servings: number;
	total: Macros;
	per_serving: Macros;
	ingredients: { name: string; grams: number; macros: Macros }[];
	is_favorite?: boolean;
}

export interface RecipeInput {
	name: string;
	servings: number;
	ingredients: { food_id: number; grams: number }[];
}

export interface DiaryEntryInput {
	entry_date: string;
	meal_type: MealType;
	source: EntrySource;
	food_id?: number | null;
	recipe_id?: number | null;
	quantity: number;
}

// --- Suplementos (adesao diaria; zero-macro nao entra no calculo de macros) ---
export interface Supplement {
	id: number;
	name: string;
	dose: string;
	active: boolean;
	taken: boolean;
	taken_last_7: number;
}

export interface SupplementsDay {
	date: string;
	items: Supplement[];
	taken_count: number;
	total: number;
}

export interface SupplementInput {
	name: string;
	dose: string;
}

export function getTokens(): { access: string | null; refresh: string | null } {
	return {
		access: localStorage.getItem(ACCESS_KEY),
		refresh: localStorage.getItem(REFRESH_KEY)
	};
}

export function setTokens(pair: TokenPair): void {
	localStorage.setItem(ACCESS_KEY, pair.access_token);
	localStorage.setItem(REFRESH_KEY, pair.refresh_token);
}

export function clearTokens(): void {
	localStorage.removeItem(ACCESS_KEY);
	localStorage.removeItem(REFRESH_KEY);
}

async function request<T>(
	path: string,
	options: { method?: string; body?: unknown; auth?: boolean; retried?: boolean } = {}
): Promise<T> {
	const { method = 'GET', body, auth = true, retried = false } = options;
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (auth) {
		const { access } = getTokens();
		if (access) headers.Authorization = `Bearer ${access}`;
	}

	let response: Response;
	// Timeout: aborta se a API nao responder a tempo (evita botao/tela travados).
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
	try {
		response = await fetch(`${API_URL}${path}`, {
			method,
			headers,
			body: body === undefined ? undefined : JSON.stringify(body),
			signal: controller.signal
		});
	} catch {
		// Inclui o AbortError do timeout: para o usuario, e sempre "sem conexao".
		throw new ApiError('NETWORK_ERROR', 0);
	} finally {
		clearTimeout(timeout);
	}

	if (response.status === 401 && auth && !retried) {
		const refreshed = await tryRefresh();
		if (refreshed) return request<T>(path, { method, body, auth, retried: true });
	}

	if (!response.ok) {
		let code = 'GENERIC_ERROR';
		try {
			const data = await response.json();
			if (typeof data.detail === 'string') code = data.detail;
		} catch {
			// resposta sem corpo JSON: mantém GENERIC_ERROR
		}
		const retryAfter = Number(response.headers.get('Retry-After'));
		throw new ApiError(
			code,
			response.status,
			Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null
		);
	}

	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}

async function tryRefresh(): Promise<boolean> {
	const { refresh } = getTokens();
	if (!refresh) return false;
	try {
		const pair = await request<TokenPair>('/auth/refresh', {
			method: 'POST',
			body: { refresh_token: refresh },
			auth: false
		});
		setTokens(pair);
		return true;
	} catch {
		clearTokens();
		return false;
	}
}

export type CyclePhase = 'menstrual' | 'follicular' | 'ovulatory' | 'luteal';
export type CycleMode = 'manual' | 'by_date';

export interface CycleStatus {
	enabled: boolean;
	mode: CycleMode;
	// fase ja RESOLVIDA pelo backend (marcada ou estimada) para o dia pedido
	phase: CyclePhase | null;
	phase_source: 'manual' | 'estimated' | null;
	day_in_cycle: number | null;
	// a data do ultimo periodo ja passou de um ciclo inteiro: hora de atualizar
	estimate_stale: boolean;
	last_period_date: string | null;
	cycle_length_days: number;
	// alimentos da fase que cabem no que falta do dia (lista propria, para a fase
	// ser visivel sem atropelar a recomendacao principal)
	suggestions: FoodSuggestion[];
}

export interface CycleInput {
	enabled: boolean;
	mode: CycleMode;
	phase?: CyclePhase | null;
	last_period_date?: string | null;
	cycle_length_days?: number;
}

export const api = {
	register: (email: string, password: string, locale: string) =>
		request<TokenPair>('/auth/register', {
			method: 'POST',
			body: { email, password, locale },
			auth: false
		}),
	login: (email: string, password: string) =>
		request<TokenPair>('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
	forgotPassword: (email: string) =>
		request<unknown>('/auth/forgot-password', { method: 'POST', body: { email }, auth: false }),
	resetPassword: (token: string, newPassword: string) =>
		request<void>('/auth/reset-password', {
			method: 'POST',
			body: { token, new_password: newPassword },
			auth: false
		}),
	me: () => request<UserOut>('/me'),
	// feedback / reportar problema
	submitFeedback: (module: FeedbackModule, description: string) =>
		request<FeedbackReport>('/me/feedback', { method: 'POST', body: { module, description } }),
	getAdminFeedback: () => request<FeedbackReport[]>('/me/feedback/admin'),
	markFeedbackRead: (id: number, read: boolean) =>
		request<FeedbackReport>(`/me/feedback/admin/${id}/read`, { method: 'PATCH', body: { read } }),
	getNews: () => request<NewsFeed>('/me/news'),
	markNewsRead: (id: number) =>
		request<void>(`/me/news/${id}/read`, { method: 'POST' }),
	updateLocale: (locale: string) =>
		request<UserOut>('/me/locale', { method: 'PUT', body: { locale } }),
	changePassword: (currentPassword: string, newPassword: string) =>
		request<void>('/me/password', {
			method: 'PUT',
			body: { current_password: currentPassword, new_password: newPassword }
		}),
	changeEmail: (newEmail: string) =>
		request<UserOut>('/me/email', { method: 'PUT', body: { new_email: newEmail } }),
	getProfile: () => request<ProfileData>('/me/profile'),
	saveProfile: (profile: ProfileInput) =>
		request<ProfileData>('/me/profile', { method: 'PUT', body: profile }),
	saveTutorial: (state: TutorialState) =>
		request<TutorialState>('/me/tutorial', { method: 'PUT', body: state }),
	getGoals: () => request<GoalsOut>('/me/goals'),
	getWeightHistory: () => request<WeightHistory>('/me/weight'),
	addWeight: (weighIn: WeighInInput) =>
		request<WeightLog>('/me/weight', { method: 'POST', body: weighIn }),
	deleteWeight: (id: number) => request<void>(`/me/weight/${id}`, { method: 'DELETE' }),
	getBodyComposition: () => request<BodyCompositionPanel>('/me/weight/body-composition'),
	// null limpa o alvo de gordura; devolve o painel ja recalculado
	setBodyCompSource: (source: BodyCompSource) =>
		request<BodyCompositionPanel>('/me/weight/body-composition/source', {
			method: 'PUT',
			body: { source }
		}),
	setBodyFatTarget: (targetPct: number | null) =>
		request<BodyCompositionPanel>('/me/weight/body-composition/target', {
			method: 'PUT',
			body: { target_fat_percentage: targetPct }
		}),
	getWaterDay: (day: string, tzOffset: number) =>
		request<WaterDay>(`/me/water?day=${day}&tz_offset=${tzOffset}`),
	addWater: (amount_ml: number) =>
		request<WaterLog>('/me/water', { method: 'POST', body: { amount_ml } }),
	deleteWater: (id: number) => request<void>(`/me/water/${id}`, { method: 'DELETE' }),
	getActivityEstimate: (kind: StandaloneActivityKind, intensity: ActivityIntensity, durationMin: number) =>
		request<{ kcal: number }>(
			`/me/activities/estimate?kind=${kind}&intensity=${intensity}&duration_min=${durationMin}`
		),
	// compartilhar entre contas: conexao, oferta e o que ja foi aceito
	getConnections: () => request<Connection[]>('/me/sharing/connections'),
	inviteConnection: (email: string) =>
		request<Connection>('/me/sharing/connections', { method: 'POST', body: { email } }),
	acceptConnection: (id: number) =>
		request<Connection>(`/me/sharing/connections/${id}/accept`, { method: 'POST' }),
	removeConnection: (id: number) =>
		request<void>(`/me/sharing/connections/${id}`, { method: 'DELETE' }),
	getShareOffers: () => request<ShareOffer[]>('/me/sharing/offers'),
	createShareOffers: (connectionId: number, items: ShareItemRef[]) =>
		request<ShareOffer[]>('/me/sharing/offers', {
			method: 'POST',
			body: { connection_id: connectionId, items }
		}),
	acceptShareOffer: (id: number) =>
		request<ReceivedItem>(`/me/sharing/offers/${id}/accept`, { method: 'POST' }),
	declineShareOffer: (id: number) =>
		request<void>(`/me/sharing/offers/${id}/decline`, { method: 'POST' }),
	getReceivedItems: () => request<ReceivedItem[]>('/me/sharing/received'),
	getSharingPendingCount: () =>
		request<SharingPendingCount>('/me/sharing/pending-count'),
	getActivities: (day: string) => request<StandaloneActivity[]>(`/me/activities?day=${day}`),
	// dias que tem atividade avulsa, para marcar no calendario de treino
	getActivityDays: () => request<string[]>('/me/activities/days'),
	addActivity: (activity: StandaloneActivityInput) =>
		request<StandaloneActivity>('/me/activities', { method: 'POST', body: activity }),
	deleteActivity: (id: number) => request<void>(`/me/activities/${id}`, { method: 'DELETE' }),
	// treino
	getExercises: (
		muscleGroup?: MuscleGroup,
		opts: { region?: MuscleRegion; level?: ExerciseLevel; full?: boolean; q?: string } = {}
	) => {
		const params = new URLSearchParams();
		if (opts.q) params.set('q', opts.q);
		if (muscleGroup) params.set('muscle_group', muscleGroup);
		if (opts.region) params.set('muscle_region', opts.region);
		if (opts.level) params.set('level', opts.level);
		if (opts.full) params.set('full', 'true');
		const qs = params.toString();
		return request<Exercise[]>(`/exercises${qs ? `?${qs}` : ''}`);
	},
	getRoutines: (includeArchived = false) =>
		request<Routine[]>(`/me/routines${includeArchived ? '?include_archived=true' : ''}`),
	getRoutine: (id: number) => request<Routine>(`/me/routines/${id}`),
	getRoutineVariation: (id: number) =>
		request<RoutineVariation>(`/me/routines/${id}/variation`),
	createRoutine: (name: string, items: RoutineItemInput[]) =>
		request<Routine>('/me/routines', { method: 'POST', body: { name, items } }),
	updateRoutine: (id: number, name: string, items: RoutineItemInput[]) =>
		request<Routine>(`/me/routines/${id}`, { method: 'PUT', body: { name, items } }),
	deleteRoutine: (id: number) => request<void>(`/me/routines/${id}`, { method: 'DELETE' }),
	// arquivar tira do ciclo sem apagar; reativar devolve como ultima do ciclo
	archiveRoutine: (id: number) => request<Routine>(`/me/routines/${id}/archive`, { method: 'POST' }),
	unarchiveRoutine: (id: number) =>
		request<Routine>(`/me/routines/${id}/unarchive`, { method: 'POST' }),
	archiveRoutines: (routineIds: number[]) =>
		request<Routine[]>('/me/routines/archive', { method: 'POST', body: { routine_ids: routineIds } }),
	createFromTemplate: (frequency: number) =>
		request<Routine[]>(`/me/routines/from-template?frequency=${frequency}`, { method: 'POST' }),
	// day ausente = treino de agora. Com day, registra um treino esquecido em data
	// passada (o backend usa o meio-dia local daquele dia).
	completeRoutine: (routineId: number, day?: string) =>
		request<WorkoutSession>(`/me/routines/${routineId}/complete`, {
			method: 'POST',
			body: day ? { day, tz_offset: new Date().getTimezoneOffset() } : {}
		}),
	startSession: (routineId: number | null) =>
		request<WorkoutSession>('/me/sessions', { method: 'POST', body: { routine_id: routineId } }),
	getActiveSession: () => request<WorkoutSession | null>('/me/sessions/active'),
	deleteSession: (id: number) => request<void>(`/me/sessions/${id}`, { method: 'DELETE' }),
	getExerciseAlternatives: (exerciseId: number) =>
		request<AlternativeExercise[]>(`/exercises/${exerciseId}/alternatives`),
	swapExercise: (sessionId: number, routineExerciseId: number, exerciseId: number) =>
		request<WorkoutSession>(`/me/sessions/${sessionId}/swaps/${routineExerciseId}`, {
			method: 'PUT',
			body: { exercise_id: exerciseId }
		}),
	undoExerciseSwap: (sessionId: number, routineExerciseId: number) =>
		request<WorkoutSession>(`/me/sessions/${sessionId}/swaps/${routineExerciseId}`, {
			method: 'DELETE'
		}),
	getSession: (id: number) => request<WorkoutSession>(`/me/sessions/${id}`),
	logSet: (
		sessionId: number,
		set: {
			exercise_id: number;
			set_number: number;
			reps: number;
			weight_kg: number;
			duration_min?: number | null;
			done: boolean;
		}
	) => request<SetLog>(`/me/sessions/${sessionId}/sets`, { method: 'POST', body: set }),
	deleteSet: (sessionId: number, setId: number) =>
		request<void>(`/me/sessions/${sessionId}/sets/${setId}`, { method: 'DELETE' }),
	finishSession: (sessionId: number) =>
		request<WorkoutSession>(`/me/sessions/${sessionId}/finish`, { method: 'POST' }),
	getSessions: () => request<SessionSummary[]>('/me/sessions'),
	getWorkoutsByDay: (day: string, tzOffset: number) =>
		request<WorkoutDayDetail[]>(`/me/sessions/by-day?day=${day}&tz_offset=${tzOffset}`),
	getWeekSummary: (day: string, tzOffset: number) =>
		request<WeekSummary>(`/me/summary/week?day=${day}&tz_offset=${tzOffset}`),
	getAdaptiveTdee: (day: string, tzOffset: number) =>
		request<AdaptiveTdee>(`/me/summary/adaptive?day=${day}&tz_offset=${tzOffset}`),
	// Ciclo menstrual (Fase A): o dia local vai na query porque a estimativa por
	// data depende do "hoje" de quem usa, nao do fuso do servidor.
	getCycle: (day: string) => request<CycleStatus>(`/me/cycle?day=${day}`),
	saveCycle: (day: string, input: CycleInput) =>
		request<CycleStatus>(`/me/cycle?day=${day}`, { method: 'PUT', body: input }),
	getCoach: (day: string, tzOffset: number) =>
		request<CoachResult>(`/me/coach?day=${day}&tz_offset=${tzOffset}`),
	getAchievements: (day: string, tzOffset: number) =>
		request<AchievementsResult>(`/me/achievements?day=${day}&tz_offset=${tzOffset}`),
	// dieta
	getFoods: (
		q = '',
		category?: FoodCategory,
		opts?: { scope?: 'mine' | 'catalog'; limit?: number; offset?: number }
	) => {
		const params = new URLSearchParams();
		if (q) params.set('q', q);
		if (category) params.set('category', category);
		if (opts?.scope) params.set('scope', opts.scope);
		if (opts?.limit) params.set('limit', String(opts.limit));
		if (opts?.offset) params.set('offset', String(opts.offset));
		const qs = params.toString();
		return request<Food[]>(`/foods${qs ? `?${qs}` : ''}`);
	},
	getRecentFoods: () => request<Food[]>('/me/foods/recent'),
	getFavoriteFoods: () => request<Food[]>('/me/foods/favorites'),
	// Liga/desliga a estrelinha; retorna o novo estado (true = favorito).
	toggleFavorite: (kind: FavoriteKind, refId: number) =>
		request<{ favorite: boolean }>('/me/favorites', {
			method: 'PUT',
			body: { kind, ref_id: refId }
		}),
	// 1 toque: adota a receita da biblioteca e ja lanca no diario.
	addDiaryFromLibrary: (input: {
		slug: string;
		entry_date: string;
		meal_type: MealType;
		quantity?: number;
	}) => request<DiaryEntry>('/me/diary/from-library', { method: 'POST', body: input }),
	createFood: (food: FoodInput) => request<Food>('/me/foods', { method: 'POST', body: food }),
	updateFood: (id: number, food: FoodInput) =>
		request<Food>(`/me/foods/${id}`, { method: 'PUT', body: food }),
	deleteFood: (id: number) => request<void>(`/me/foods/${id}`, { method: 'DELETE' }),
	getRecipeLibrary: (tag?: string) =>
		request<LibraryRecipe[]>(`/recipes/library${tag ? `?tag=${tag}` : ''}`),
	getLibraryRecipe: (slug: string) => request<LibraryRecipe>(`/recipes/library/${slug}`),
	adoptLibraryRecipe: (slug: string) =>
		request<Recipe>(`/me/recipes/from-library/${slug}`, { method: 'POST' }),
	getRecipes: () => request<Recipe[]>('/me/recipes'),
	createRecipe: (recipe: RecipeInput) =>
		request<Recipe>('/me/recipes', { method: 'POST', body: recipe }),
	updateRecipe: (id: number, recipe: RecipeInput) =>
		request<Recipe>(`/me/recipes/${id}`, { method: 'PUT', body: recipe }),
	deleteRecipe: (id: number) => request<void>(`/me/recipes/${id}`, { method: 'DELETE' }),
	getDiary: (day: string) => request<DiaryDay>(`/me/diary?day=${day}`),
	getDiaryGap: (day: string, limit = 4, mealType?: MealType) =>
		request<DiaryGap>(
			`/me/diary/gap?day=${day}&limit=${limit}${mealType ? `&meal_type=${mealType}` : ''}`
		),
	getBuildMeal: (day: string, haveFoodIds: number[], mealType?: MealType) => {
		const params = new URLSearchParams({ day });
		haveFoodIds.forEach((id) => params.append('have', String(id)));
		if (mealType) params.set('meal_type', mealType);
		return request<BuildMeal>(`/me/diary/build-meal?${params.toString()}`);
	},
	getSubstitutes: (foodId: number, grams: number, limit = 6) =>
		request<Substitutes>(`/me/foods/${foodId}/substitutes?grams=${grams}&limit=${limit}`),
	getMealPlan: (day: string, limit = 3) =>
		request<MealPlan>(`/me/diary/meal-plan?day=${day}&limit=${limit}`),
	getDietAdherence: (end: string, window = 7) =>
		request<DietAdherence>(`/me/diet/adherence?end=${end}&window=${window}`),
	getDietPeriod: (day: string) => request<DietPeriod | null>(`/me/diet/period?day=${day}`),
	renewDietPeriod: (day: string, adoptMaintenanceKcal?: number) => {
		const q = adoptMaintenanceKcal ? `&adopt_maintenance_kcal=${adoptMaintenanceKcal}` : '';
		return request<DietPeriod | null>(`/me/diet/period/renew?day=${day}${q}`, { method: 'POST' });
	},
	getTrainingPeriodization: (today: string) =>
		request<RoutinePeriodization[]>(`/me/training/periodization?today=${today}`),
	searchExternalFoods: (q: string, limit = 15) =>
		request<ExternalFood[]>(`/me/foods/search-external?q=${encodeURIComponent(q)}&limit=${limit}`),
	getDiaryLoggedDays: (start: string, end: string) =>
		request<string[]>(`/me/diary/logged-days?start=${start}&end=${end}`),
	getSupplements: (day: string) =>
		request<SupplementsDay>(`/me/supplements?day=${day}`),
	createSupplement: (day: string, data: SupplementInput) =>
		request<Supplement>(`/me/supplements?day=${day}`, { method: 'POST', body: data }),
	updateSupplement: (id: number, day: string, data: SupplementInput) =>
		request<Supplement>(`/me/supplements/${id}?day=${day}`, { method: 'PUT', body: data }),
	deleteSupplement: (id: number) =>
		request<void>(`/me/supplements/${id}`, { method: 'DELETE' }),
	markSupplement: (id: number, day: string) =>
		request<Supplement>(`/me/supplements/${id}/log?day=${day}`, { method: 'POST' }),
	unmarkSupplement: (id: number, day: string) =>
		request<Supplement>(`/me/supplements/${id}/log?day=${day}`, { method: 'DELETE' }),
	addDiaryEntry: (entry: DiaryEntryInput) =>
		request<DiaryEntry>('/me/diary', { method: 'POST', body: entry }),
	updateDiaryEntry: (id: number, quantity: number) =>
		request<DiaryEntry>(`/me/diary/${id}`, { method: 'PUT', body: { quantity } }),
	deleteDiaryEntry: (id: number) => request<void>(`/me/diary/${id}`, { method: 'DELETE' }),
	copyPreviousDay: (day: string, fromDay: string, mealType?: MealType) => {
		const params = new URLSearchParams({ day, from_day: fromDay });
		if (mealType) params.set('meal_type', mealType);
		return request<DiaryDay>(`/me/diary/copy-previous?${params.toString()}`, { method: 'POST' });
	},
	exportData: () => request<unknown>('/me/account/export'),
	deleteAccount: () => request<void>('/me/account', { method: 'DELETE' })
};

export function localDay(): string {
	const now = new Date();
	return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
		now.getDate()
	).padStart(2, '0')}`;
}

export function localDayParams(): { day: string; tzOffset: number } {
	const now = new Date();
	const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
		now.getDate()
	).padStart(2, '0')}`;
	return { day, tzOffset: now.getTimezoneOffset() };
}
