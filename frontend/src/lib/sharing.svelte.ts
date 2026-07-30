import { api } from './api';

/**
 * Quantas coisas de compartilhamento esperam uma acao sua.
 *
 * Vive fora das telas porque o aviso precisa aparecer na barra de abas, que nunca
 * desmonta - se o contador morasse na tela de compartilhamento, so quem ja abriu essa
 * tela descobriria que recebeu algo.
 *
 * Nao ha polling de proposito: o app inteiro nao faz nenhum, e a API hiberna no plano
 * gratuito do Render. Acordar o servidor de tempos em tempos so para contar zero
 * custaria mais que o problema resolve. Atualizamos na abertura do app, ao voltar para
 * ele e depois de qualquer acao de compartilhamento.
 */
export const sharingPending = $state({
	invites: 0,
	offers: 0,
	total: 0
});

export async function refreshSharingPending(): Promise<void> {
	try {
		const count = await api.getSharingPendingCount();
		sharingPending.invites = count.invites;
		sharingPending.offers = count.offers;
		sharingPending.total = count.total;
	} catch {
		// contador e informacao acessoria: se falhar, a tela nao pode quebrar por isso
		clearSharingPending();
	}
}

export function clearSharingPending(): void {
	sharingPending.invites = 0;
	sharingPending.offers = 0;
	sharingPending.total = 0;
}
