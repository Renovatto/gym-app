import { api } from './api';
import { m } from './paraglide/messages';
import { session } from './session.svelte';
import { showToast } from './toast.svelte';
import { TOURS } from './tourSteps';

/**
 * Motor do tutorial guiado.
 *
 * Guarda qual tour esta aberto e em que passo. Quem desenha e o TourOverlay;
 * quem diz o que cada passo fala e o tourSteps.
 */
export const tour = $state({
	id: '',
	step: 0,
	active: false
});

function totalSteps(id: string): number {
	return TOURS[id]?.length ?? 0;
}

/** Quantos passos deste tour a pessoa ja viu (0 = nunca abriu). */
export function seenSteps(id: string): number {
	return session.profile?.tutorial_progress?.[id] ?? 0;
}

/** Um tour so aparece enquanto sobrar passo novo para mostrar. */
export function isTourPending(id: string): boolean {
	if (!session.profile?.tutorial_enabled) return false;
	return seenSteps(id) < totalSteps(id);
}

/**
 * Salva o estado do tutorial. Escreve na sessao primeiro (a tela nao pode esperar a
 * rede) e manda para a API sem bloquear: um tutorial nunca pode travar o app se a
 * chamada falhar - no maximo a pessoa ve o mesmo passo de novo em outro aparelho.
 */
function persist(enabled: boolean, progress: Record<string, number>): void {
	if (!session.profile) return;
	session.profile.tutorial_enabled = enabled;
	session.profile.tutorial_progress = progress;
	void api.saveTutorial({ enabled, progress }).catch(() => {});
}

/** Marca quantos passos deste tour ja foram vistos; nunca anda para tras. */
function markSeen(id: string, count: number): void {
	const profile = session.profile;
	if (!profile) return;
	const seen = Math.max(seenSteps(id), count);
	persist(profile.tutorial_enabled, { ...profile.tutorial_progress, [id]: seen });
}

export function startTour(id: string): void {
	const total = totalSteps(id);
	if (total === 0) return;
	tour.id = id;
	// Retoma de onde parou. seenSteps nunca chega ao total aqui (isTourPending barra).
	tour.step = Math.min(seenSteps(id), total - 1);
	tour.active = true;
}

function close(): void {
	tour.active = false;
	tour.id = '';
	tour.step = 0;
}

export function nextStep(): void {
	const total = totalSteps(tour.id);
	if (tour.step + 1 >= total) {
		markSeen(tour.id, total);
		close();
		showToast(m.tour_done_toast());
		return;
	}
	tour.step += 1;
	markSeen(tour.id, tour.step);
}

export function prevStep(): void {
	if (tour.step > 0) tour.step -= 1;
}

/** Saiu no meio (clicou no fundo, apertou Esc, trocou de aba): guarda o lugar. */
export function pauseTour(): void {
	if (!tour.active) return;
	markSeen(tour.id, tour.step);
	close();
	showToast(m.tour_paused_toast());
}

/** Nao quer ver este tour: marca como concluido e ensina onde religar. */
export function skipTour(): void {
	markSeen(tour.id, totalSteps(tour.id));
	close();
	showToast(m.tour_skipped_toast());
}

/**
 * Liga/desliga o tutorial inteiro (usado pelo Perfil).
 *
 * Aqui a chamada e aguardada, ao contrario do avanco de passo: e uma escolha
 * explicita da pessoa, entao a tela so pode dizer "desligado" depois que o
 * servidor confirmar. Quem chama trata o erro e desfaz o chip.
 */
export async function setTutorialEnabled(enabled: boolean): Promise<void> {
	const profile = session.profile;
	if (!profile) return;
	await api.saveTutorial({ enabled, progress: profile.tutorial_progress });
	profile.tutorial_enabled = enabled;
	if (!enabled) close();
}

/** Refazer do zero: esquece os passos vistos e liga de novo. */
export async function restartTutorial(): Promise<void> {
	const profile = session.profile;
	if (!profile) return;
	await api.saveTutorial({ enabled: true, progress: {} });
	profile.tutorial_enabled = true;
	profile.tutorial_progress = {};
}

/**
 * O passo do tour esta apontando para esta ancora agora?
 *
 * As telas usam isto para trocar, so nesse instante, um bloco vazio ("sem
 * refeicao lancada", "sem bioimpedancia") pelo mesmo componente ja preenchido
 * com um exemplo - a pessoa ve como a tela fica no uso real, sem esperar ter
 * dado proprio. E seguro: enquanto o balao esta aberto, a camada de clique do
 * TourOverlay bloqueia a tela inteira, entao o exemplo nunca pode ser tocado
 * nem confundido com um registro de verdade. Ao passar o passo isto volta a
 * false sozinho (e um derived em quem usa, nao um estado que precisa desfazer).
 */
export function isShowingAnchor(anchor: string): boolean {
	if (!tour.active) return false;
	return TOURS[tour.id]?.[tour.step]?.anchor === anchor;
}
