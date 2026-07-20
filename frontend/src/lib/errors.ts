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
	FOOD_IN_USE_DIARY: () => m.error_food_in_use_diary()
};

export function errorMessage(code: string): string {
	return (ERROR_MESSAGES[code] ?? (() => m.error_generic()))();
}

// Paraglide usa tags minúsculas ("pt-br"); a API guarda o formato BCP-47 ("pt-BR").
export function toBackendLocale(locale: Locale): string {
	return locale === 'pt-br' ? 'pt-BR' : locale;
}
