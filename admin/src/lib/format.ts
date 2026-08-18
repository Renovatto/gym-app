import { ApiError } from './api';
import type { Objective } from './api';

/** Formatacao pt-BR usada em todo o painel (o admin nao tem i18n: so pt-BR). */

export function num(value: number): string {
	return value.toLocaleString('pt-BR');
}

export function pct(value: number, digits = 1): string {
	return value.toLocaleString('pt-BR', {
		minimumFractionDigits: digits,
		maximumFractionDigits: digits
	});
}

export function shortDate(iso: string): string {
	const date = new Date(iso);
	return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

export function fullDate(iso: string): string {
	const date = new Date(iso);
	return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' });
}

/** "hoje" / "ontem" / "ha N dias" / "ha N meses" a partir da contagem do servidor. */
export function relativeDays(days: number | null): string {
	if (days === null) return 'nunca registrou';
	if (days === 0) return 'hoje';
	if (days === 1) return 'ontem';
	if (days < 30) return `ha ${days} dias`;
	if (days < 60) return 'ha 1 mes';
	return `ha ${Math.floor(days / 30)} meses`;
}

/** Dias inteiros entre uma data ISO e agora (para "cadastrou-se ha N dias"). */
export function daysSince(iso: string): number {
	const elapsed = Date.now() - new Date(iso).getTime();
	return Math.max(0, Math.floor(elapsed / 86400000));
}

export const OBJECTIVE_LABEL: Record<Objective, string> = {
	lose_fat: 'Perder gordura',
	maintain: 'Manter',
	gain_muscle: 'Ganhar massa',
	recomp: 'Recomposicao'
};

export function objectiveLabel(objective: Objective | null): string {
	return objective ? OBJECTIVE_LABEL[objective] : 'Sem perfil';
}

/** Classe da pill do objetivo: cor segue a ENTIDADE, igual no grafico e na tabela. */
export function objectivePill(objective: Objective | null): string {
	if (objective === 'lose_fat') return 'pill-cut';
	if (objective === 'gain_muscle') return 'pill-gain';
	return 'pill-keep';
}

/** Iniciais para o avatar: do nome quando existe, senao do e-mail. */
export function initials(name: string | null, email: string): string {
	const source = name?.trim() || email.split('@')[0];
	const parts = source.split(/[\s.]+/).filter(Boolean);
	const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
	return letters.toUpperCase();
}

/** Rotulos dos modulos do feedback (a API guarda o codigo, o front traduz). */
const FEEDBACK_MODULE_LABEL: Record<string, string> = {
	workout: 'Treino',
	diet: 'Dieta',
	progress: 'Progresso',
	profile: 'Perfil',
	other: 'Outro'
};

export function moduleLabel(module: string): string {
	return FEEDBACK_MODULE_LABEL[module] ?? module;
}

/** Mensagem para o codigo de erro que a API devolve (ela nunca manda texto pronto). */
export function errorMessage(code: string): string {
	switch (code) {
		case 'NETWORK_ERROR':
			return 'Sem conexao com a API. Tente de novo em instantes.';
		case 'INVALID_CREDENTIALS':
			return 'E-mail ou senha incorretos.';
		case 'ADMIN_ONLY':
			return 'Esta conta nao tem acesso administrativo.';
		case 'USER_NOT_FOUND':
			return 'Conta nao encontrada.';
		case 'INVALID_SORT':
			return 'Ordenacao invalida.';
		default:
			return 'Nao foi possivel completar a acao.';
	}
}

/**
 * Mensagem da tela de login. Tem funcao propria porque o bloqueio por excesso de
 * tentativas precisa dizer quanto falta, e esse tempo vem no cabecalho Retry-After
 * (em segundos), nao no codigo do erro.
 */
export function loginErrorMessage(error: unknown): string {
	if (error instanceof ApiError && error.code === 'TOO_MANY_LOGIN_ATTEMPTS') {
		// Arredonda para cima e nunca mostra "0 min": faltando 30s, "1 min" e mais
		// honesto do que dizer que ja liberou.
		const minutos = Math.max(1, Math.ceil((error.retryAfterSeconds ?? 0) / 60));
		return `Muitas tentativas seguidas. Tente de novo em ${minutos} min.`;
	}
	return errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR');
}
