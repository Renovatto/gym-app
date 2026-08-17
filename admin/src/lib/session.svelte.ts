import { api, clearTokens, hasTokens, setTokens, type UserOut } from './api';

/**
 * Sessao do painel. `ready` existe para a tela nao piscar "acesso negado" antes
 * de o /me responder - enquanto e false, o layout mostra o estado de carregando.
 */
interface SessionState {
	user: UserOut | null;
	ready: boolean;
}

export const session = $state<SessionState>({ user: null, ready: false });

export async function loadSession(): Promise<void> {
	if (!hasTokens()) {
		session.user = null;
		session.ready = true;
		return;
	}
	try {
		session.user = await api.me();
	} catch {
		// Token invalido ou API fora: trata como deslogado e deixa o guard agir.
		clearTokens();
		session.user = null;
	}
	session.ready = true;
}

export async function login(email: string, password: string): Promise<void> {
	const pair = await api.login(email, password);
	setTokens(pair);
	session.user = await api.me();
	session.ready = true;
}

export function logout(): void {
	clearTokens();
	session.user = null;
}
