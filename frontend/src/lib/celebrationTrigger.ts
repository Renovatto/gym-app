// Decide QUAL celebracao disparar a partir de um resultado fresco de /me/achievements.
// Subiu de nivel tem prioridade sobre desbloqueio comum (evita empilhar duas telas
// cheias no mesmo carregamento). O conteudo mostrado e sempre real: nome/descricao/
// icone da propria conquista, ou o nome/numero do nivel atingido.
import { celebrate } from './celebration.svelte';
import {
	MILESTONE_CODES,
	POOL_GENERAL,
	POOL_LEVELUP,
	POOL_MILESTONE,
	POOL_STREAK,
	pickRandom
} from './celebrationDefs';
import { achievementText } from './achievementsContent';
import { titleIcon, titleName } from './titleContent';
import { m } from './paraglide/messages';
import { getLocale, type Locale } from './paraglide/runtime';
import type { AchievementItem, AchievementsResult } from './api';

const TITLE_TIER_SEEN_KEY = 'gymapp.titleTierSeen';

/** Dispara a celebracao cheia de uma conquista JA desbloqueada, sob demanda (botao
 * "ver de novo" em /conquistas) - mesma selecao de pool/conteudo do desbloqueio
 * original, so que reutilizavel para qualquer item unlocked, nao so o mais recente. */
export function celebrateAchievement(item: AchievementItem, locale: Locale): void {
	const text = achievementText(locale, item.code);
	const pool = MILESTONE_CODES.has(item.code)
		? POOL_MILESTONE
		: item.category === 'streak'
			? POOL_STREAK
			: POOL_GENERAL;
	celebrate(pickRandom(pool), {
		kicker: m.achievement_unlocked_kicker(),
		emoji: item.icon,
		title: text.name,
		desc: text.description,
		number: item.progress_goal
	});
}

/** Avalia um resultado fresco de /me/achievements e dispara a celebracao adequada.
 * Retorna true se algo foi disparado (o chamador pode pular o toast generico nesse caso). */
export function triggerAchievementCelebrations(data: AchievementsResult): boolean {
	const locale = getLocale();

	// Titulo evolutivo: so celebra um SALTO real de nivel. Na primeira checagem em cada
	// aparelho so estabelece a base (sem celebrar) - sem isso, quem ja tinha treinos
	// antes desta funcionalidade existir veria um "subiu de nivel" falso no 1o carregamento.
	const rawSeen = localStorage.getItem(TITLE_TIER_SEEN_KEY);
	const isFirstEverCheck = rawSeen === null;
	const seenTier = rawSeen ? parseInt(rawSeen, 10) : 0;

	if (isFirstEverCheck) {
		localStorage.setItem(TITLE_TIER_SEEN_KEY, String(data.title_tier));
	} else if (data.title_tier > seenTier) {
		localStorage.setItem(TITLE_TIER_SEEN_KEY, String(data.title_tier));
		celebrate(pickRandom(POOL_LEVELUP), {
			kicker: m.levelup_kicker(),
			emoji: titleIcon(data.title_tier),
			title: titleName(locale, data.title_tier),
			desc: m.levelup_desc({ n: Math.round(data.title_progress_current) }),
			number: data.title_tier + 1
		});
		return true;
	}

	if (data.newly_unlocked.length > 0) {
		const code = data.newly_unlocked[0];
		const item = data.achievements.find((a) => a.code === code);
		if (!item) return false;
		celebrateAchievement(item, locale);
		return true;
	}
	return false;
}
