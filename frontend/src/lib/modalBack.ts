import { pushState } from '$app/navigation';
import { page } from '$app/state';
import { untrack } from 'svelte';

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

/**
 * `lembrete` vai junto na entrada de historico da modal. Serve para a tela
 * reabrir a modal quando a pessoa sai por um link de dentro dela e depois volta
 * (ver AddEntryModal e a tela de Dieta).
 */
export function closeOnBack(close: () => void, lembrete: App.PageState = {}): () => void {
	const trap: Trap = { close };
	if (abertas.length === 0) window.addEventListener('popstate', aoVoltar);
	abertas.push(trap);
	const profundidade = abertas.length;
	// untrack: o pushState do SvelteKit le page.url por dentro, e sem isso o $effect
	// que chamou esta funcao passaria a depender da URL - qualquer mudanca nela
	// (um Voltar que so troca o estado, por exemplo) re-executaria o efeito e
	// empurraria uma entrada extra no historico.
	untrack(() => {
		// A pessoa voltou para a entrada que esta mesma modal tinha empurrado antes
		// de sair por um link (e a tela reabriu a modal). A marca ja esta no
		// historico: empurrar outra deixaria um Voltar a mais, que nao faz nada.
		const reabrindoNaPropriaEntrada = page.state.modalDepth === profundidade;
		if (!reabrindoNaPropriaEntrada) pushState('', { ...lembrete, modalDepth: profundidade });
	});
	const enderecoAoAbrir = location.href;

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
		//
		// So a marca nao basta quando a saida e um LINK dentro da modal (o "+" de
		// cadastrar alimento, por exemplo): o SvelteKit desmonta a tela antiga antes
		// de trocar o page.state, entao aqui a marca ainda parece a nossa - e o back()
		// desfazia o link, a pessoa tocava no "+" e nao saia do lugar. O endereco ja
		// mudou nesse momento, entao comparar com o de quando a modal abriu pega o caso.
		const aindaNaMesmaTela = location.href === enderecoAoAbrir;
		if (fechouSemVoltar && aindaNaMesmaTela && page.state.modalDepth === profundidade) {
			history.back();
		}
	};
}
