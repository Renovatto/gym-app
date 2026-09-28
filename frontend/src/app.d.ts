// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
import type { MealType } from '$lib/api';

declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		interface PageState {
			// Marca a entrada de historico empurrada por uma modal aberta, para o
			// Voltar fechar a modal em vez de sair da tela (ver lib/modalBack.ts).
			modalDepth?: number;
			// Refeicao e dia da modal de adicionar alimento. Quem sai dela por um link
			// (cadastrar/editar alimento) e volta encontra a modal aberta de novo.
			addEntry?: { meal: MealType; day: string };
		}
		// interface Platform {}
	}
}

export {};
