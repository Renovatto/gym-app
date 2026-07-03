export type ThemePref = 'light' | 'dark' | 'system';

const THEME_KEY = 'gymapp.theme';

export const theme = $state({ pref: 'system' as ThemePref });

function systemDark(): boolean {
	return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function apply(): void {
	const dark = theme.pref === 'dark' || (theme.pref === 'system' && systemDark());
	document.documentElement.classList.toggle('dark', dark);
}

export function initTheme(): void {
	const saved = localStorage.getItem(THEME_KEY);
	if (saved === 'light' || saved === 'dark' || saved === 'system') {
		theme.pref = saved;
	}
	apply();
	window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
		if (theme.pref === 'system') apply();
	});
}

export function setTheme(pref: ThemePref): void {
	theme.pref = pref;
	localStorage.setItem(THEME_KEY, pref);
	apply();
}
