<script lang="ts">
	/*
	 * Tela de abertura do app, entre o splash do sistema e a primeira tela.
	 *
	 * Ela repete a arte e a animacao do splash de proposito: o iOS tira o splash assim
	 * que a pagina pinta o primeiro pixel, e antes a gente pintava um spinner sobre
	 * fundo claro - o que aparecia como um "flash branco" entre a abertura e o app.
	 * Continuando a mesma imagem, a troca fica invisivel e o que sobra na tela e so a
	 * espera da API.
	 *
	 * As classes boot-* e os keyframes vivem no <style> do app.html (fonte unica para
	 * esta tela e para a estatica de la); aqui so entra a marcacao.
	 */

	const CICLO_S = 4.4;

	// Atraso NEGATIVO do tamanho do que ja passou do ciclo: assim a animacao continua
	// de onde a tela estatica estava, em vez de dar um salto ao recomecar do zero.
	// performance.now() conta desde o inicio do carregamento, que e quando a estatica
	// comecou a animar.
	const offset = `${-((performance.now() / 1000) % CICLO_S)}s`;
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-ink"
	style="--boot-offset: {offset}"
>
	<svg viewBox="96 180 320 152" class="boot-mark" aria-hidden="true">
		<g class="boot-lift">
			<g class="boot-beat">
				<g class="boot-plate-oe"><rect class="boot-flex-e" x="96" y="206" width="32" height="100" rx="12" /></g>
				<g class="boot-plate-ie"><rect class="boot-flex-e" x="136" y="180" width="40" height="152" rx="14" /></g>
				<g class="boot-roll"><rect x="176" y="238" width="160" height="36" rx="18" /></g>
				<g class="boot-plate-id"><rect class="boot-flex-d" x="336" y="180" width="40" height="152" rx="14" /></g>
				<g class="boot-plate-od"><rect class="boot-flex-d" x="384" y="206" width="32" height="100" rx="12" /></g>
			</g>
		</g>
	</svg>
</div>
