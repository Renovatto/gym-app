/**
 * Trava de rolagem e de selecao durante arrasto por ponteiro.
 *
 * Duas armadilhas do iOS Safari, nesta ordem:
 *
 * 1. ROLAGEM. `touch-action: none` no elemento nao basta no WebKit: quando o dedo
 *    sobe ou desce numa pagina que rola, o Safari assume a rolagem, MATA o gesto
 *    (chega um `pointercancel`) e o item nao sai do lugar - so o movimento
 *    horizontal, que nao disputa com nada, funcionava. O unico jeito que segura e
 *    um listener de `touchmove` NAO passivo com `preventDefault` enquanto o
 *    arrasto durar.
 *
 * 2. SELECAO. Barrar a rolagem deixa o navegador livre para cair na outra
 *    interpretacao do gesto: selecionar texto, que pinta a tela inteira de azul.
 *    Barramos a selecao pelo `selectstart` (mouse) e por `user-select` desligado
 *    no documento (toque, ver `.dragging-no-select` em layout.css).
 *
 * O que NAO pode: `preventDefault` no `pointerdown`. No WebKit o ponteiro vem do
 * toque, e cancelar o padrao do toque inicial faz o navegador desistir do gesto
 * antes mesmo dele comecar - foi o que travou o FAB de feedback e as refeicoes.
 */

const BODY_CLASS = 'dragging-no-select';

function blockSelectStart(event: Event): void {
	event.preventDefault();
}

// precisa ser passive: false, senao o navegador ignora o preventDefault
function blockTouchMove(event: TouchEvent): void {
	event.preventDefault();
}

// Rede de seguranca: se por algum motivo o `pointerup` nao chegar, o fim do toque
// destrava a pagina do mesmo jeito. So quando NENHUM dedo resta na tela, para um
// segundo toque acidental nao liberar a rolagem no meio do arrasto.
function releaseOnLastTouchEnd(event: TouchEvent): void {
	if (event.touches.length === 0) endPointerDrag();
}

/** Comeca um arrasto: segura a rolagem e a selecao ate soltar. */
export function beginPointerDrag(): void {
	// selecao que ja exista continuaria pintada durante o gesto inteiro
	document.getSelection()?.removeAllRanges();
	document.body.classList.add(BODY_CLASS);
	document.addEventListener('selectstart', blockSelectStart);
	document.addEventListener('touchmove', blockTouchMove, { passive: false });
	document.addEventListener('touchend', releaseOnLastTouchEnd);
	document.addEventListener('touchcancel', releaseOnLastTouchEnd);
}

/** Encerra o arrasto (soltar ou cancelar): devolve rolagem e selecao. */
export function endPointerDrag(): void {
	document.body.classList.remove(BODY_CLASS);
	document.removeEventListener('selectstart', blockSelectStart);
	document.removeEventListener('touchmove', blockTouchMove);
	document.removeEventListener('touchend', releaseOnLastTouchEnd);
	document.removeEventListener('touchcancel', releaseOnLastTouchEnd);
}
