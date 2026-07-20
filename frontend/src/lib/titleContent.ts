// Titulo evolutivo (o "nivel" do usuario): escada fixa de 8 nomes, ligada SO a
// total_workouts (comportamento, nunca peso/corpo). O backend manda o indice
// (title_tier); aqui traduzimos indice -> nome, nos tres idiomas lado a lado.

import type { Locale } from '$lib/paraglide/runtime';

// Mesma ordem/indice do TITLE_TIERS no backend (services/achievements.py).
const PT_BR = [
	'Iniciante',
	'Comprometido',
	'Consistente',
	'Dedicado',
	'Guerreiro',
	'Veterano',
	'Mestre',
	'Lenda'
];

const EN = [
	'Beginner',
	'Committed',
	'Consistent',
	'Dedicated',
	'Warrior',
	'Veteran',
	'Master',
	'Legend'
];

const ES = [
	'Principiante',
	'Comprometido',
	'Constante',
	'Dedicado',
	'Guerrero',
	'Veterano',
	'Maestro',
	'Leyenda'
];

const BY_LOCALE: Record<Locale, string[]> = { 'pt-br': PT_BR, en: EN, es: ES };

// Icone por nivel (evolucao visual junto com o nome).
const ICONS = ['🌱', '🔰', '🔥', '💪', '⚔️', '🛡️', '🎖️', '👑'];

export function titleName(locale: Locale, tier: number): string {
	const list = BY_LOCALE[locale] ?? PT_BR;
	return list[Math.min(tier, list.length - 1)] ?? list[0];
}

export function titleIcon(tier: number): string {
	return ICONS[Math.min(tier, ICONS.length - 1)] ?? ICONS[0];
}

export const TITLE_TIER_COUNT = PT_BR.length;
