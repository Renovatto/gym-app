// Fila de celebracoes (gamificacao): mesmo padrao do toast.svelte.ts, mas guarda uma
// FILA (nao so a ultima) porque mais de um gatilho pode disparar no mesmo carregamento
// (ex.: subiu de nivel + desbloqueou uma conquista no mesmo treino).
import type { CelebrationDef } from './celebrationDefs';

export interface CelebrationContent {
	kicker: string;
	emoji: string;
	title: string;
	desc: string;
	// numero exibido em animacoes com contador/numero gigante (streak, marco, nivel).
	number?: number;
}

export interface CelebrationItem {
	def: CelebrationDef;
	content: CelebrationContent;
}

export const celebrationState = $state<{ queue: CelebrationItem[] }>({ queue: [] });

export function celebrate(def: CelebrationDef, content: CelebrationContent): void {
	celebrationState.queue = [...celebrationState.queue, { def, content }];
}

export function dismissCelebration(): void {
	celebrationState.queue = celebrationState.queue.slice(1);
}
