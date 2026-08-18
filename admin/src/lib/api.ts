/**
 * Cliente da API do painel admin.
 *
 * Fala com o MESMO backend do app (mesma base de dados, mesmo login). O que muda
 * e so o conjunto de rotas: tudo sob /admin exige e-mail na allowlist do servidor
 * (GYMAPP_ADMIN_EMAILS) - o painel nao decide quem e admin, so obedece o 403.
 */

const API_PORT = 8765;

// Sem VITE_API_URL, deriva a base da API do host acessado. Em producao o painel
// mora em /admin do mesmo dominio da API, entao a origem ja e a mesma.
function defaultApiUrl(): string {
	if (typeof window !== 'undefined') {
		const { protocol, hostname, port } = window.location;
		// Em dev o vite roda numa porta propria e a API em outra; em producao o
		// nginx serve os dois na mesma origem e nao ha porta a trocar.
		const isDevServer = port !== '' && port !== '80' && port !== '443';
		return isDevServer ? `${protocol}//${hostname}:${API_PORT}` : `${protocol}//${hostname}`;
	}
	return `http://localhost:${API_PORT}`;
}

const API_URL: string = import.meta.env.VITE_API_URL ?? defaultApiUrl();

// Aborta requests pendurados para a tela sempre dar retorno em vez de travar.
const REQUEST_TIMEOUT_MS = 30000;

// Chaves proprias do painel: um admin logado aqui nao interfere na sessao do app
// aberta no mesmo navegador, e sair daqui nao desloga de la.
const ACCESS_KEY = 'gymapp.admin.access';
const REFRESH_KEY = 'gymapp.admin.refresh';

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

export type Objective = 'lose_fat' | 'maintain' | 'gain_muscle' | 'recomp';
export type Plan = 'free' | 'premium';

export interface AdminUserRow {
	id: number;
	email: string;
	name: string | null;
	objective: Objective | null;
	plan: Plan;
	diet_enabled: boolean;
	created_at: string;
	last_activity_at: string | null;
	days_since_activity: number | null;
}

export interface AdminUserPage {
	items: AdminUserRow[];
	total: number;
	page: number;
	page_size: number;
}

export interface AdminUserDetail {
	id: number;
	email: string;
	name: string | null;
	objective: Objective | null;
	plan: Plan;
	locale: string;
	diet_enabled: boolean;
	cycle_enabled: boolean;
	created_at: string;
	last_activity_at: string | null;
	days_since_activity: number | null;
	meals_30d: number;
	workouts_30d: number;
	weigh_ins_30d: number;
	connections: number;
}

export interface AdminOverview {
	total_users: number;
	new_users_7d: number;
	new_users_30d: number;
	active_7d: number;
	active_30d: number;
	meals_7d: number;
	workouts_7d: number;
	diet_enabled_users: number;
	objectives: { objective: Objective | null; users: number }[];
}

export interface AdminActivityPoint {
	day: string;
	active_users: number;
	meals: number;
	workouts: number;
}

export interface AdminActivitySeries {
	days: number;
	points: AdminActivityPoint[];
}

export interface FeedbackReport {
	id: number;
	module: string;
	description: string;
	read: boolean;
	created_at: string;
	user_email: string;
}

/** Filtros da listagem de usuarios. Tudo opcional; o servidor e quem pagina. */
export interface UserQuery {
	page: number;
	page_size: number;
	q?: string;
	objective?: Objective | '';
	active_within_days?: number | '';
	inactive_for_days?: number | '';
	signed_up_within_days?: number | '';
	sort: 'email' | 'created_at' | 'last_activity';
	order: 'asc' | 'desc';
}

function getTokens(): { access: string | null; refresh: string | null } {
	if (typeof localStorage === 'undefined') return { access: null, refresh: null };
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

export function hasTokens(): boolean {
	return getTokens().access !== null;
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
		throw new ApiError('NETWORK_ERROR', 0);
	} finally {
		clearTimeout(timeout);
	}

	// 401 com refresh valido: renova uma vez e repete. Uma so, para nao entrar em
	// laco quando o refresh tambem estiver morto.
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
			// resposta sem corpo JSON: mantem GENERIC_ERROR
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

/** Monta a query string ignorando o que estiver vazio. */
function toQuery(params: Record<string, string | number | undefined>): string {
	const search = new URLSearchParams();
	for (const [key, value] of Object.entries(params)) {
		if (value === undefined || value === '') continue;
		search.set(key, String(value));
	}
	const text = search.toString();
	return text ? `?${text}` : '';
}

export const api = {
	login: (email: string, password: string) =>
		request<TokenPair>('/auth/login', {
			method: 'POST',
			body: { email, password },
			auth: false
		}),

	me: () => request<UserOut>('/me'),

	listUsers: (query: UserQuery) =>
		request<AdminUserPage>(
			`/admin/users${toQuery({
				page: query.page,
				page_size: query.page_size,
				q: query.q,
				objective: query.objective,
				active_within_days: query.active_within_days,
				inactive_for_days: query.inactive_for_days,
				signed_up_within_days: query.signed_up_within_days,
				sort: query.sort,
				order: query.order
			})}`
		),

	getUser: (id: number) => request<AdminUserDetail>(`/admin/users/${id}`),

	sendPasswordReset: (id: number) =>
		request<void>(`/admin/users/${id}/password-reset`, { method: 'POST' }),

	overview: () => request<AdminOverview>('/admin/metrics/overview'),

	activity: (days: number) => request<AdminActivitySeries>(`/admin/metrics/activity?days=${days}`),

	listFeedback: () => request<FeedbackReport[]>('/me/feedback/admin'),

	setFeedbackRead: (id: number, read: boolean) =>
		request<FeedbackReport>(`/me/feedback/admin/${id}/read`, { method: 'PATCH', body: { read } })
};
