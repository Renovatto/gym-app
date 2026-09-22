<script lang="ts">
	/*
	 * Tela de abertura do app, entre o splash do sistema e a primeira tela.
	 *
	 * Ela repete a arte do splash (mesma marca, mesmo fundo ink) de proposito: o iOS
	 * tira o splash assim que a pagina pinta o primeiro pixel, e antes a gente pintava
	 * um spinner sobre fundo claro - o que aparecia como um "flash branco" entre a
	 * abertura e o app. Continuando a mesma imagem, a troca fica invisivel e o que
	 * sobra na tela e so a espera da API.
	 */
</script>

<div class="fixed inset-0 z-50 flex flex-col items-center justify-center gap-8 bg-ink">
	<svg
		viewBox="96 180 320 152"
		class="w-[39vw] max-w-[200px] animate-pulse motion-reduce:animate-none"
		fill="#10b981"
		aria-hidden="true"
	>
		<rect x="96" y="206" width="32" height="100" rx="12" />
		<rect x="136" y="180" width="40" height="152" rx="14" />
		<rect x="176" y="238" width="160" height="36" rx="18" />
		<rect x="336" y="180" width="40" height="152" rx="14" />
		<rect x="384" y="206" width="32" height="100" rx="12" />
	</svg>
</div>
