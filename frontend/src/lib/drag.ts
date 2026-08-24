/**
 * Trava de selecao durante arrasto por ponteiro.
 *
 * `touch-action: none` so desliga rolagem e zoom - nao tem efeito nenhum sobre
 * selecao de texto. Sem isso, o `pointerdown` segue com o comportamento padrao do
 * navegador (mouse: comeca uma selecao no ponto de contato; toque: dispara o
 * segurar-para-selecionar) e o dedo, ao se mover, pinta a tela inteira de azul -
 * o arrasto parece travado. Chamar `preventDefault` no `pointerdown` resolve a
 * metade do problema; a outra metade e que a selecao e do documento, entao a
 * trava tambem precisa valer para o `body` enquanto o arrasto acontece.
 */

const BODY_CLASS = 'dragging-no-select';

/** Comeca um arrasto: mata a selecao padrao do navegador e trava o documento. */
export function beginPointerDrag(event: PointerEvent): void {
	event.preventDefault();
	document.body.classList.add(BODY_CLASS);
}

/** Encerra o arrasto (soltar ou cancelar): destrava o documento. */
export function endPointerDrag(): void {
	document.body.classList.remove(BODY_CLASS);
}
