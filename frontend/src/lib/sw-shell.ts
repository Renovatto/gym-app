/**
 * Pedidos usados pelo service worker para guardar a casca do app.
 *
 * `cache: 'reload'` faz cada arquivo vir do servidor, ignorando o cache HTTP do
 * navegador. Sem isso o `index.html` podia sair de uma copia velha guardada por
 * heuristica: em 13/11/2026 o service worker novo guardou o HTML do build que ainda
 * chamava a API no dominio antigo, e o login passou a dar "Sem conexao com o servidor".
 *
 * Fica fora do service-worker.ts para poder ser testado sem um navegador rodando o
 * worker de verdade.
 */
export function shellRequests(paths: readonly string[], origin: string): Request[] {
	return paths.map((path) => new Request(new URL(path, origin), { cache: 'reload' }));
}
