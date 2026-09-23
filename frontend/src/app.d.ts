// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		interface PageState {
			// Marca a entrada de historico empurrada por uma modal aberta, para o
			// Voltar fechar a modal em vez de sair da tela (ver lib/modalBack.ts).
			modalDepth?: number;
		}
		// interface Platform {}
	}
}

export {};
