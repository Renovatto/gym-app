import { pushState } from '$app/navigation';
import { page } from '$app/state';

/**
 * Faz o botao Voltar do aparelho (e o gesto de deslizar do iOS) FECHAR a modal
 * aberta, em vez de sair da tela.
 *
 * Sem isso a modal e so estado de componente: o historico nao sabe que ela
 * existe, entao o Voltar volta a rota de verdade e a pessoa cai na tela
 * anterior - normalmente a home - perdendo o que estava fazendo.
 *
 * Uso dentro do componente da modal (o retorno e a limpeza do $effect):
 *
 *     $effect(() => closeOnBack(onClose));                          // modal em componente proprio
 *     $effect(() => { if (open) return closeOnBack(() => (open = false)); }); // modal inline
 *
 * O pushState e o do SvelteKit, nao o do navegador: ele mantem o indice interno
 * de navegacao do framework consistente, coisa que um history.pushState cru
 * quebraria.
 */

// Pilha das modais abertas. Com duas empilhadas (uma confirmacao dentro de uma
// modal, por exemplo), o Voltar fecha SO a de cima - sem a pilha, o popstate
// chegaria em todas ao mesmo tempo e o app fecharia as duas de uma vez.
type Trap = { close: () => void };
const abertas: Trap[] = [];

function aoVoltar(): void {
	abertas.pop()?.close();
}

export function closeOnBack(close: () => void): () => void {
	const trap: Trap = { close };
	if (abertas.length === 0) window.addEventListener('popstate', aoVoltar);
	abertas.push(trap);
	const profundidade = abertas.length;
	pushState('', { modalDepth: profundidade });

	return () => {
		const posicao = abertas.indexOf(trap);
		const fechouSemVoltar = posicao !== -1;
		if (fechouSemVoltar) abertas.splice(posicao, 1);
		if (abertas.length === 0) window.removeEventListener('popstate', aoVoltar);
		// Fechou pelo X ou pelo salvar: a entrada que empurramos continua no
		// historico, e sem consumir aqui o proximo Voltar nao faria nada - a pessoa
		// teria de apertar duas vezes. Quando quem fechou foi o proprio Voltar, a
		// entrada ja saiu e chamar back() de novo pularia uma tela a mais.
		//
		// A checagem do modalDepth cobre o caso em que o proprio onClose NAVEGA (um
		// goto): a entrada da navegacao fica por cima da nossa, e o back() desfaria
		// justamente essa navegacao - devolvendo a pessoa para a tela que ela acabou
		// de fechar. Se a marca nao e mais a atual, alguem ja saiu daqui: nao ha o
		// que consumir.
		if (fechouSemVoltar && page.state.modalDepth === profundidade) history.back();
	};
}
