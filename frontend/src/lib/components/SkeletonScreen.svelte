<script lang="ts">
	import Skeleton from '$lib/components/Skeleton.svelte';

	// Desenho em cinza do que esta chegando, no lugar do spinner em tela vazia.
	//
	// De proposito uma APROXIMACAO e nao uma copia da tela: replicar o layout de
	// verdade criaria duas versoes de cada tela para manter em sincronia, e na
	// primeira mudanca de layout o esqueleto viraria mentira. Ninguem compara pixel
	// a pixel - o que importa e o formato geral aparecer no lugar certo.
	//
	// Isso pesa mais neste app que na media: a API roda no plano gratuito do Render,
	// que hiberna quando fica ociosa, e a primeira chamada depois disso leva alguns
	// segundos. O esqueleto nao acelera nada; muda o que essa espera parece.
	let {
		hero = false, // bloco grande no topo (resumo do dia, macros, anel de meta)
		chart = false, // cartao com numero em destaque e a area de um grafico
		cards = 3, // quantos cartoes vem depois
		cardLines = 2 // linhas de texto dentro de cada cartao
	}: { hero?: boolean; chart?: boolean; cards?: number; cardLines?: number } = $props();
</script>

<div class="space-y-3" aria-busy="true">
	{#if chart}
		<div class="rounded-3xl bg-white p-6 shadow-sm">
			<Skeleton class="h-3 w-28" />
			<Skeleton class="mt-2 h-10 w-36" />
			<!-- bloco liso, nao barras: o grafico real e de linha, e um desenho de
				 barras "pularia" quando o conteudo de verdade chegasse -->
			<Skeleton class="mt-5 h-32 w-full rounded-2xl" />
		</div>
	{/if}

	{#if hero}
		<div class="rounded-3xl bg-white p-5 shadow-sm">
			<Skeleton class="h-3 w-24" />
			<Skeleton class="mt-3 h-9 w-40" />
			<div class="mt-4 flex gap-2">
				<Skeleton class="h-12 flex-1 rounded-2xl" />
				<Skeleton class="h-12 flex-1 rounded-2xl" />
				<Skeleton class="h-12 flex-1 rounded-2xl" />
			</div>
		</div>
	{/if}

	{#each Array(cards) as _, index (index)}
		<div class="rounded-3xl bg-white p-4 shadow-sm">
			<div class="flex items-center gap-3">
				<Skeleton class="h-9 w-9 shrink-0 rounded-xl" />
				<Skeleton class="h-4 flex-1" />
				<Skeleton class="h-4 w-12 shrink-0" />
			</div>
			{#each Array(cardLines) as _, line (line)}
				<!-- a ultima linha sai mais curta: texto corrido raramente fecha a linha -->
				<Skeleton class="mt-2.5 h-3 {line === cardLines - 1 ? 'w-2/5' : 'w-4/5'}" />
			{/each}
		</div>
	{/each}
</div>
