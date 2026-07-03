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
	exportData: () => request<unknown>('/me/account/export'),
	deleteAccount: () => request<void>('/me/account', { method: 'DELETE' })
};
