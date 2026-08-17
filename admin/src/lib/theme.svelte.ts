/**
 * Tema do painel. Escuro e o PADRAO (a direcao visual e um console escuro), mas
 * o claro funciona inteiro e a escolha fica salva - quem opera de dia nao quer
 * rebater o botao toda vez que abre.
 */
const THEME_KEY = 'gymapp.admin.theme';

export type Theme = 'dark' | 'light';

interface ThemeState {
	current: Theme;
}

export const themeState = $state<ThemeState>({ current: 'dark' });

export function initTheme(): void {
	const saved = localStorage.getItem(THEME_KEY);
	themeState.current = saved === 'light' ? 'light' : 'dark';
	document.documentElement.setAttribute('data-theme', themeState.current);
}

export function toggleTheme(): void {
	themeState.current = themeState.current === 'dark' ? 'light' : 'dark';
	localStorage.setItem(THEME_KEY, themeState.current);
	document.documentElement.setAttribute('data-theme', themeState.current);
}

/** Le um token de cor do CSS: os graficos seguem o tema vigente sem duplicar paleta. */
export function themeToken(name: string): string {
	if (typeof document === 'undefined') return '';
	return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
