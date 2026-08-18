import { ApiError } from '$lib/api';
import { m } from '$lib/paraglide/messages';
import type { Locale } from '$lib/paraglide/runtime';

const ERROR_MESSAGES: Record<string, () => string> = {
	EMAIL_ALREADY_REGISTERED: () => m.error_email_taken(),
	INVALID_CREDENTIALS: () => m.error_invalid_credentials(),
	NETWORK_ERROR: () => m.error_network(),
	PASSWORD_TOO_SHORT: () => m.error_password_short(),
	WRONG_PASSWORD: () => m.error_wrong_password(),
	INVALID_TOKEN: () => m.error_invalid_token(),
	TOKEN_EXPIRED: () => m.error_token_expired(),
	FOOD_IN_USE_RECIPE: () => m.error_food_in_use_recipe(),
	FOOD_IN_USE_DIARY: () => m.error_food_in_use_diary(),
	// compartilhar entre contas
	USER_NOT_FOUND: () => m.error_user_not_found(),
	CANNOT_INVITE_SELF: () => m.error_cannot_invite_self(),
	CONNECTION_EXISTS: () => m.error_connection_exists(),
	SOURCE_ITEM_GONE: () => m.error_source_item_gone(),
	ALREADY_ANSWERED: () => m.error_already_answered(),
	// ciclo menstrual: a tela ja evita os tres casos, mas mensagem generica num
	// erro de data deixaria a pessoa sem saber o que corrigir
	CYCLE_PHASE_REQUIRED: () => m.error_cycle_phase_required(),
	CYCLE_DATE_REQUIRED: () => m.error_cycle_date_required(),
	CYCLE_DATE_FUTURE: () => m.error_cycle_date_future()
};

export function errorMessage(code: string): string {
	return (ERROR_MESSAGES[code] ?? (() => m.error_generic()))();
}

// Erro da tela de login. Tem funcao propria porque o bloqueio por excesso de
// tentativas precisa dizer quanto falta, e esse tempo vem no cabecalho
// Retry-After (em segundos), nao no codigo do erro.
export function loginErrorMessage(error: unknown): string {
	if (error instanceof ApiError && error.code === 'TOO_MANY_LOGIN_ATTEMPTS') {
		// Arredonda para cima e nunca mostra "0 min": faltando 30s, "1 min" e
		// mais honesto do que dizer que ja liberou.
		const minutes = Math.max(1, Math.ceil((error.retryAfterSeconds ?? 0) / 60));
		return m.error_too_many_attempts({ minutes });
	}
	return errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR');
}

// Paraglide usa tags minúsculas ("pt-br"); a API guarda o formato BCP-47 ("pt-BR").
export function toBackendLocale(locale: Locale): string {
	return locale === 'pt-br' ? 'pt-BR' : locale;
}
