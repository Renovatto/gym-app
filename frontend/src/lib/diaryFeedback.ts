import { api, localDay, type DiaryEntry } from '$lib/api';
import { mealTypeLabel } from '$lib/labels';
import { showToast } from '$lib/toast.svelte';
import { m } from '$lib/paraglide/messages';
import { getLocale } from '$lib/paraglide/runtime';

export const DIARY_CHANGED_EVENT = 'gymapp:diary-changed';

// O historico pode restaurar snapshots finalizados, inclusive depois de recarregar a aba.
// Guarda somente IDs no sessionStorage; nomes e valores nutricionais nao entram neste registro.
const COMPLETED_ADDITIONS_KEY = 'gymapp.diary-completed-additions';

function readCompletedAdditions(): Set<number> {
	if (typeof window === 'undefined') return new Set();
	try {
		const stored: unknown = JSON.parse(sessionStorage.getItem(COMPLETED_ADDITIONS_KEY) ?? '[]');
		return new Set(Array.isArray(stored) ? stored.filter((id) => Number.isSafeInteger(id)) : []);
	} catch {
		return new Set();
	}
}

const completedAdditionIds = readCompletedAdditions();

function rememberCompletedAdditions(): void {
	try {
		sessionStorage.setItem(COMPLETED_ADDITIONS_KEY, JSON.stringify([...completedAdditionIds]));
	} catch {
		// Com armazenamento indisponivel, a protecao ainda funciona na memoria da pagina.
	}
}

export function clearDiaryFeedbackHistory(): void {
	completedAdditionIds.clear();
	rememberCompletedAdditions();
}

export interface DiaryAddition {
	entry: DiaryEntry;
	day: string;
}

export function pendingDiaryAdditions(additions: DiaryAddition[]): DiaryAddition[] {
	return additions.filter((addition) => !completedAdditionIds.has(addition.entry.id));
}

export function showDiaryAdditions(additions: DiaryAddition[]): void {
	const groups = new Map<string, DiaryAddition[]>();
	for (const addition of pendingDiaryAdditions(additions)) {
		completedAdditionIds.add(addition.entry.id);
		if (addition.day <= localDay()) continue;
		const key = `${addition.day}:${addition.entry.meal_type}`;
		const group = groups.get(key) ?? [];
		group.push(addition);
		groups.set(key, group);
	}
	rememberCompletedAdditions();
	for (const group of groups.values()) showFutureMealToast(group);
}

function showFutureMealToast(additions: DiaryAddition[]): void {
	const { day, entry } = additions[0];
	const entryIds = additions.map((addition) => addition.entry.id);
	const count = entryIds.length;
	const meal = mealTypeLabel(entry.meal_type);
	const date = new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'short' })
		.format(new Date(`${day}T12:00:00`));
	const message = count === 1
		? m.diary_tomorrow_one_item({ meal })
		: m.diary_tomorrow_items({ count, meal });
	showToast(message, {
		title: m.diary_tomorrow_saved({ date }),
		kind: 'warning',
		duration: 18000,
		action: {
			label: m.diary_undo(),
			confirmation: m.diary_undo_question(),
			description: count === 1
				? m.diary_undo_description({ name: entry.name, meal, date })
				: m.diary_undo_group_description({ count, meal, date }),
			run: async () => {
				// IDs copiados da sessao: a API remove o grupo inteiro em uma transacao.
				await api.undoDiaryAdditions(entryIds);
				window.dispatchEvent(new CustomEvent(DIARY_CHANGED_EVENT, { detail: day }));
				showToast(m.diary_undo_done());
			}
		}
	});
}

export function showDiaryAdded(entry: DiaryEntry, day: string, message = m.toast_added()): void {
	if (day <= localDay()) {
		showToast(message);
		return;
	}
	showDiaryAdditions([{ entry, day }]);
}
