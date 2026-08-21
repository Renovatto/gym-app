<script lang="ts">
	import { m } from '$lib/paraglide/messages';
	import { news, markNewsRead } from '$lib/news.svelte';
	import { page } from '$app/state';

	// So a novidade IMPORTANTE nao lida interrompe, e o servidor ja escolheu qual e.
	// Novidade normal fica no sino e espera a pessoa querer ver - depois de duas ou tres
	// modais seguidas, todo mundo aprende a fechar sem ler.
	// Na propria tela de novidades a modal nao faz sentido - a pessoa ja esta lendo. Isso
	// tambem e o que faz o link "Ver todas" funcionar: se o clique marcasse como lida na
	// hora, o proprio <a> sairia do DOM no meio do clique e a navegacao seria cancelada.
	// Aqui a modal so some depois que a rota mudou, e quem marca como lida e a lista.
	const pending = $derived(page.url.pathname === '/novidades' ? null : news.pendingImportant);

	async function dismiss(): Promise<void> {
		const item = pending;
		if (!item) return;
		await markNewsRead(item.id);
	}

</script>

{#if pending}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={dismiss}
		onkeydown={(e) => e.key === 'Escape' && dismiss()}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<p class="text-xs font-bold tracking-wide text-emerald-600 uppercase">{m.news_eyebrow()}</p>
			<h2 class="mt-1 text-lg font-bold text-slate-900">{pending.title}</h2>
			<p class="mt-2 text-sm leading-relaxed whitespace-pre-line text-slate-600">{pending.body}</p>

			<div class="mt-4 flex gap-2">
				<a
					href="/novidades"
					class="grid h-12 flex-1 place-items-center rounded-2xl bg-slate-100 text-sm font-bold text-slate-600 active:bg-slate-200"
				>
					{m.news_see_all()}
				</a>
				<button
					type="button"
					onclick={dismiss}
					class="h-12 flex-1 rounded-2xl bg-emerald-600 text-sm font-bold text-white active:bg-emerald-700"
				>
					{m.news_got_it()}
				</button>
			</div>
		</div>
	</div>
{/if}
