const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8765';

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

export interface ProfileData {
	height_cm: number;
	weight_kg: number | null;
	birthdate: string;
	sex: Sex;
	activity_level: ActivityLevel;
	objective: Objective;
	diet_enabled: boolean;
	scale_mac: string | null;
}

export interface GoalsOut {
	age: number;
	bmi: number;
	bmr_kcal: number;
	tdee_kcal: number;
	target_kcal: number;
	protein_g: number;
	fat_g: number;
	carbs_g: number;
	water_ml: number;
}

export interface WeightLog {
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
}

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
	| 'calves';

export type Equipment =
	| 'barbell'
	| 'dumbbell'
	| 'machine'
	| 'cable'
	| 'bodyweight'
	| 'kettlebell'
	| 'band'
	| 'other';

export interface Exercise {
	id: number;
	slug: string;
	name: string;
	muscle_group: MuscleGroup;
	equipment: Equipment;
	media_url: string | null;
	is_custom: boolean;
}

export interface RoutineItem {
	id: number;
	exercise: Exercise;
	position: number;
	target_sets: number;
	target_reps: number;
	target_weight_kg: number | null;
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
	rest_seconds: number;
}

export interface SetLog {
	id: number;
	exercise_id: number;
	set_number: number;
	reps: number;
	weight_kg: number;
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
	try {
		response = await fetch(`${API_URL}${path}`, {
			method,
			headers,
			body: body === undefined ? undefined : JSON.stringify(body)
		});
	} catch {
		throw new ApiError('NETWORK_ERROR', 0);
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
	me: () => request<UserOut>('/me'),
	updateLocale: (locale: string) =>
		request<UserOut>('/me/locale', { method: 'PUT', body: { locale } }),
	getProfile: () => request<ProfileData>('/me/profile'),
	saveProfile: (profile: Omit<ProfileData, 'weight_kg'> & { weight_kg: number }) =>
		request<ProfileData>('/me/profile', { method: 'PUT', body: profile }),
	getGoals: () => request<GoalsOut>('/me/goals'),
	getWeightHistory: () => request<WeightHistory>('/me/weight'),
	addWeight: (weight_kg: number) =>
		request<WeightLog>('/me/weight', { method: 'POST', body: { weight_kg } }),
	deleteWeight: (id: number) => request<void>(`/me/weight/${id}`, { method: 'DELETE' }),
	getWaterDay: (day: string, tzOffset: number) =>
		request<WaterDay>(`/me/water?day=${day}&tz_offset=${tzOffset}`),
	addWater: (amount_ml: number) =>
		request<WaterLog>('/me/water', { method: 'POST', body: { amount_ml } }),
	deleteWater: (id: number) => request<void>(`/me/water/${id}`, { method: 'DELETE' }),
	// treino
	getExercises: (muscleGroup?: MuscleGroup) =>
		request<Exercise[]>(`/exercises${muscleGroup ? `?muscle_group=${muscleGroup}` : ''}`),
	getRoutines: () => request<Routine[]>('/me/routines'),
	getRoutine: (id: number) => request<Routine>(`/me/routines/${id}`),
	createRoutine: (name: string, items: RoutineItemInput[]) =>
		request<Routine>('/me/routines', { method: 'POST', body: { name, items } }),
	updateRoutine: (id: number, name: string, items: RoutineItemInput[]) =>
		request<Routine>(`/me/routines/${id}`, { method: 'PUT', body: { name, items } }),
	deleteRoutine: (id: number) => request<void>(`/me/routines/${id}`, { method: 'DELETE' }),
	createFromTemplate: (frequency: number) =>
		request<Routine[]>(`/me/routines/from-template?frequency=${frequency}`, { method: 'POST' }),
	startSession: (routineId: number | null) =>
		request<WorkoutSession>('/me/sessions', { method: 'POST', body: { routine_id: routineId } }),
	getSession: (id: number) => request<WorkoutSession>(`/me/sessions/${id}`),
	logSet: (
		sessionId: number,
		set: { exercise_id: number; set_number: number; reps: number; weight_kg: number; done: boolean }
	) => request<SetLog>(`/me/sessions/${sessionId}/sets`, { method: 'POST', body: set }),
	deleteSet: (sessionId: number, setId: number) =>
		request<void>(`/me/sessions/${sessionId}/sets/${setId}`, { method: 'DELETE' }),
	finishSession: (sessionId: number) =>
		request<WorkoutSession>(`/me/sessions/${sessionId}/finish`, { method: 'POST' }),
	getSessions: () => request<SessionSummary[]>('/me/sessions'),
	exportData: () => request<unknown>('/me/account/export'),
	deleteAccount: () => request<void>('/me/account', { method: 'DELETE' })
};

export function localDayParams(): { day: string; tzOffset: number } {
	const now = new Date();
	const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
		now.getDate()
	).padStart(2, '0')}`;
	return { day, tzOffset: now.getTimezoneOffset() };
}
