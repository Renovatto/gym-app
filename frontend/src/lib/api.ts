const API_PORT = 8765;

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
		public status: number
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

export interface WeightLog extends BodyComposition {
	id: number;
	weight_kg: number;
	source: 'manual' | 'ble';
	logged_at: string;
}

export interface WeightHistory {
	logs: WeightLog[];
	current_kg: number | null;
	start_kg: number | null;
	delta_kg: number | null;
	latest_body_composition: WeightLog | null;
}

// Entrada da pesagem: peso obrigatorio + composicao corporal opcional.
export type WeighInInput = { weight_kg: number } & Partial<BodyComposition>;

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

export interface WorkoutSession {
	id: number;
	routine_id: number | null;
	routine_name: string | null;
	started_at: string;
	finished_at: string | null;
	sets: SetLog[];
}

export interface SessionSummary {
	id: number;
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
}

// Dica do coach por regras (code traduzido no frontend; severity define a cor).
export interface CoachNote {
	code: string;
	severity: 'warn' | 'info';
}

export interface CoachResult {
	notes: CoachNote[];
	days_since_weigh_in: number | null;
}

// Resultado do TDEE adaptativo (manutencao real estimada a partir dos dados).
export interface AdaptiveTdee {
	has_enough_data: boolean;
	span_days: number;
	days_logged: number;
	avg_intake_kcal: number;
	weekly_change_kg: number;
	estimated_maintenance_kcal: number | null;
	formula_tdee_kcal: number;
	current_target_kcal: number;
	suggested_target_kcal: number | null;
	message_code: string;
}

// --- Dieta ---
export type FoodCategory =
	| 'protein'
	| 'carb'
	| 'fruit'
	| 'vegetable'
	| 'dairy'
	| 'legume'
	| 'fat'
	| 'beverage'
	| 'sweet'
	| 'prepared'
	| 'supplement'
	| 'other';

export type MealType =
	| 'breakfast'
	| 'pre_workout'
	| 'lunch'
	| 'snack'
	| 'dinner'
	| 'supper'
	| 'other';
export type EntrySource = 'food' | 'recipe';

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
}

export interface LibraryRecipe {
	slug: string;
	name: string;
	tags: string[];
	servings: number;
	total: Macros;
	per_serving: Macros;
	ingredients: { name: string; grams: number }[];
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
	ingredients: { name: string; grams: number }[];
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
		throw new ApiError(code, response.status);
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
	saveProfile: (profile: Omit<ProfileData, 'weight_kg'> & { weight_kg: number }) =>
		request<ProfileData>('/me/profile', { method: 'PUT', body: profile }),
	getGoals: () => request<GoalsOut>('/me/goals'),
	getWeightHistory: () => request<WeightHistory>('/me/weight'),
	addWeight: (weighIn: WeighInInput) =>
		request<WeightLog>('/me/weight', { method: 'POST', body: weighIn }),
	deleteWeight: (id: number) => request<void>(`/me/weight/${id}`, { method: 'DELETE' }),
	getWaterDay: (day: string, tzOffset: number) =>
		request<WaterDay>(`/me/water?day=${day}&tz_offset=${tzOffset}`),
	addWater: (amount_ml: number) =>
		request<WaterLog>('/me/water', { method: 'POST', body: { amount_ml } }),
	deleteWater: (id: number) => request<void>(`/me/water/${id}`, { method: 'DELETE' }),
	// treino
	getExercises: (
		muscleGroup?: MuscleGroup,
		opts: { level?: ExerciseLevel; full?: boolean; q?: string } = {}
	) => {
		const params = new URLSearchParams();
		if (opts.q) params.set('q', opts.q);
		if (muscleGroup) params.set('muscle_group', muscleGroup);
		if (opts.level) params.set('level', opts.level);
		if (opts.full) params.set('full', 'true');
		const qs = params.toString();
		return request<Exercise[]>(`/exercises${qs ? `?${qs}` : ''}`);
	},
	getRoutines: () => request<Routine[]>('/me/routines'),
	getRoutine: (id: number) => request<Routine>(`/me/routines/${id}`),
	getRoutineVariation: (id: number) =>
		request<RoutineVariation>(`/me/routines/${id}/variation`),
	createRoutine: (name: string, items: RoutineItemInput[]) =>
		request<Routine>('/me/routines', { method: 'POST', body: { name, items } }),
	updateRoutine: (id: number, name: string, items: RoutineItemInput[]) =>
		request<Routine>(`/me/routines/${id}`, { method: 'PUT', body: { name, items } }),
	deleteRoutine: (id: number) => request<void>(`/me/routines/${id}`, { method: 'DELETE' }),
	createFromTemplate: (frequency: number) =>
		request<Routine[]>(`/me/routines/from-template?frequency=${frequency}`, { method: 'POST' }),
	completeRoutine: (routineId: number) =>
		request<WorkoutSession>(`/me/routines/${routineId}/complete`, { method: 'POST' }),
	startSession: (routineId: number | null) =>
		request<WorkoutSession>('/me/sessions', { method: 'POST', body: { routine_id: routineId } }),
	getActiveSession: () => request<WorkoutSession | null>('/me/sessions/active'),
	deleteSession: (id: number) => request<void>(`/me/sessions/${id}`, { method: 'DELETE' }),
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
	getCoach: (day: string, tzOffset: number) =>
		request<CoachResult>(`/me/coach?day=${day}&tz_offset=${tzOffset}`),
	getAchievements: (day: string, tzOffset: number) =>
		request<AchievementsResult>(`/me/achievements?day=${day}&tz_offset=${tzOffset}`),
	// dieta
	getFoods: (q = '', category?: FoodCategory) => {
		const params = new URLSearchParams();
		if (q) params.set('q', q);
		if (category) params.set('category', category);
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
	getDiaryGap: (day: string, limit = 4) =>
		request<DiaryGap>(`/me/diary/gap?day=${day}&limit=${limit}`),
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
