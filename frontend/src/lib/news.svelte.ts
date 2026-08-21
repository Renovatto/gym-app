import { api, type NewsFeed, type NewsItem } from './api';

/**
 * Novidades do app: o que mudou e por que isso importa para quem usa.
 *
 * Mora fora das telas pelo mesmo motivo do contador de compartilhamento: o sino aparece
 * no topo da tela inicial e a modal pode abrir em qualquer entrada no app, entao o
 * estado nao pode depender de alguem ja ter visitado a tela de novidades.
 *
 * Sem polling, igual ao resto do app: atualizamos na abertura e quando a pessoa volta
 * para o app. Novidade nao e mensagem - alguns minutos de atraso nao custam nada.
 */
export const news = $state({
	items: [] as NewsItem[],
	unreadCount: 0,
	// Novidade importante ainda nao lida. Quem decide qual e o servidor, para o cliente
	// nao precisar saber o que conta como "a proxima".
	pendingImportant: null as NewsItem | null
});

function apply(feed: NewsFeed): void {
	news.items = feed.items;
	news.unreadCount = feed.unread_count;
	news.pendingImportant = feed.pending_important;
}

export async function refreshNews(): Promise<void> {
	try {
		apply(await api.getNews());
	} catch {
		// novidade e acessorio: se a chamada falhar, o app segue sem sino
		clearNews();
	}
}

export function clearNews(): void {
	news.items = [];
	news.unreadCount = 0;
	news.pendingImportant = null;
}

/**
 * Marca uma novidade como lida. Atualiza o estado local antes da rede: o sino precisa
 * sumir no toque, nao no fim da requisicao. O servidor e idempotente, entao repetir a
 * chamada (a tela marca ao abrir, a modal marca ao fechar) nao faz mal.
 */
export async function markNewsRead(id: number): Promise<void> {
	const item = news.items.find((entry) => entry.id === id);
	if (!item || item.read) return;
	item.read = true;
	news.unreadCount = Math.max(0, news.unreadCount - 1);
	if (news.pendingImportant?.id === id) news.pendingImportant = null;
	try {
		await api.markNewsRead(id);
	} catch {
		// se falhar, o item volta a aparecer como nao lido na proxima atualizacao
	}
}
