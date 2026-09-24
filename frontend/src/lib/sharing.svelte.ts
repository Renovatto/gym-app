import { api, type SentMealOffer, type ShareOffer } from './api';
import { mealTypeLabel } from './labels';
import { m } from './paraglide/messages';
import { getLocale } from './paraglide/runtime';

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

// --- Refeicao compartilhada ------------------------------------------------
// Textos montados num lugar so porque o convite aparece em duas telas (Dieta e
// Conexoes) e precisa dizer a mesma coisa nas duas.

/** "Almoco de 23/09" */
export function mealOfferTitle(offer: ShareOffer): string {
	if (!offer.meal_type || !offer.meal_date) return offer.item_name;
	const date = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: '2-digit' }).format(
		// meio-dia: evita o fuso empurrar a data para o dia anterior
		new Date(offer.meal_date + 'T12:00:00')
	);
	return m.sharing_meal_offer_title({ meal: mealTypeLabel(offer.meal_type), date });
}

/** "3 itens - 640 kcal" */
export function mealOfferSummary(offer: ShareOffer): string {
	const kcal = new Intl.NumberFormat(getLocale()).format(Math.round(offer.kcal));
	return m.sharing_meal_offer_summary({ count: offer.item_count, kcal });
}

/** Selo de quem enviou: "Enviada a Ana - aceitou" */
export function sentMealLabel(sent: SentMealOffer): string {
	const name = sent.to_name;
	return {
		pending: m.sharing_meal_sent_pending({ name }),
		accepted: m.sharing_meal_sent_accepted({ name }),
		declined: m.sharing_meal_sent_declined({ name })
	}[sent.status];
}
