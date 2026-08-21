<script lang="ts">
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';
	import { news, markNewsRead, refreshNews } from '$lib/news.svelte';

	// Datas vem como dia puro (sem hora) do servidor; montamos ao meio-dia para o fuso
	// nao empurrar a data um dia para tras na hora de formatar.
	const dateFormat = new Intl.DateTimeFormat(getLocale(), { day: 'numeric', month: 'long' });
	function formatDay(isoDay: string): string {
		const [year, month, day] = isoDay.split('-').map(Number);
		return dateFormat.format(new Date(year, month - 1, day, 12));
	}

	// Abrir a tela E ter lido: quem chegou aqui viu tudo o que estava na lista. Marcamos
	// uma vez, na montagem, e nao a cada mudanca do estado - senao o proprio ato de
	// marcar dispararia a marcacao de novo.
	let alreadyMarked = false;
	$effect(() => {
		if (alreadyMarked || news.items.length === 0) return;
		alreadyMarked = true;
		for (const item of news.items) {
			if (!item.read) void markNewsRead(item.id);
		}
	});

	// Se a pessoa chegou por link direto antes do app ter carregado o feed.
	$effect(() => {
		if (news.items.length === 0) void refreshNews();
	});
</script>

<div class="mb-4 flex items-center gap-2">
	<a
		href="/"
		aria-label={m.back()}
		class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
	>
		<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	</a>
	<h1 class="text-2xl font-bold">{m.news_title()}</h1>
</div>

{#if news.items.length === 0}
	<p class="rounded-3xl bg-white p-5 text-sm text-slate-500 shadow-sm">{m.news_empty()}</p>
{:else}
	<div class="space-y-3">
		{#each news.items as item (item.id)}
			<article class="rounded-3xl bg-white p-5 shadow-sm">
				<div class="mb-1 flex items-center gap-2">
					<p class="text-xs font-bold text-slate-400 uppercase">{formatDay(item.published_on)}</p>
					{#if item.importance === 'important'}
						<span class="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700">
							{m.news_important()}
						</span>
					{/if}
				</div>
				<h2 class="font-bold text-slate-900">{item.title}</h2>
				<p class="mt-1 text-sm leading-relaxed whitespace-pre-line text-slate-600">{item.body}</p>
			</article>
		{/each}
	</div>
{/if}
