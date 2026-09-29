<script lang="ts">
	import { closeOnBack } from '$lib/modalBack';
	import { ApiError, api, type Connection, type ShareOffer } from '$lib/api';
	import { errorMessage } from '$lib/errors';
	import { mealOfferSummary, mealOfferTitle, refreshSharingPending, sharingPending } from '$lib/sharing.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	/*
	 * Faixa "chegou para voce" da tela inicial + painel com os recebidos.
	 *
	 * Antes o unico aviso era o numerinho no icone de Perfil, e quem recebia uma
	 * refeicao so descobria se reparasse nele. A faixa fica no topo da tela inicial
	 * enquanto houver algo esperando resposta; tocar abre o painel, onde da para
	 * aceitar ou dispensar sem sair da tela.
	 */

	let offers = $state<ShareOffer[]>([]);
	let invites = $state<Connection[]>([]);
	let sheetOpen = $state(false);
	let answering = $state<string | null>(null);

	async function load(): Promise<void> {
		const [allOffers, connections] = await Promise.all([api.getShareOffers(), api.getConnections()]);
		offers = allOffers;
		// so os convites que esperam VOCE responder (os que voce enviou nao pedem acao)
		invites = connections.filter((c) => c.status === 'pending' && !c.i_invited);
	}

	// Recarrega sempre que o contador global muda (abrir o app, voltar para ele,
	// responder algo em outra tela).
	$effect(() => {
		if (sharingPending.total > 0) load();
	});

	$effect(() => {
		if (sheetOpen) return closeOnBack(() => (sheetOpen = false));
	});

	const pendingCount = $derived(offers.length + invites.length);

	// "Marina e Pedro": nomes unicos na ordem em que chegaram, no formato de lista do
	// idioma da pessoa ("Marina y Pedro", "Marina and Pedro").
	const senderNames = $derived.by(() => {
		const names = [...offers.map((o) => o.from_name), ...invites.map((c) => c.person_name)];
		const unique = [...new Set(names)];
		const shown = unique.slice(0, 2);
		if (unique.length > 2) shown.push(m.sharing_banner_others({ count: unique.length - 2 }));
		return new Intl.ListFormat(getLocale(), { type: 'conjunction' }).format(shown);
	});

	// Resumo do que chegou por tipo: "Refeição e convite de conexão"
	const kindsSummary = $derived.by(() => {
		const kinds = new Set<string>();
		for (const offer of offers) kinds.add(offerKindLabel(offer));
		if (invites.length > 0) kinds.add(m.sharing_kind_invite());
		return new Intl.ListFormat(getLocale(), { type: 'conjunction' }).format([...kinds]);
	});

	const avatarNames = $derived(
		[...new Set([...offers.map((o) => o.from_name), ...invites.map((c) => c.person_name)])].slice(0, 3)
	);

	function offerKindLabel(offer: ShareOffer): string {
		if (offer.item_kind === 'meal') return m.sharing_kind_meal();
		return offer.item_kind === 'recipe' ? m.sharing_kind_recipe() : m.sharing_kind_food();
	}

	function initial(name: string): string {
		return name.trim().charAt(0).toUpperCase();
	}

	const nf = new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 1 });

	// Depois de responder: atualiza lista e contador; se nao sobrou nada, fecha o painel.
	async function afterAnswer(): Promise<void> {
		await Promise.all([load(), refreshSharingPending()]);
		if (offers.length + invites.length === 0) sheetOpen = false;
	}

	async function acceptOffer(offer: ShareOffer): Promise<void> {
		answering = `offer-${offer.id}`;
		try {
			await api.acceptShareOffer(offer.id);
			// refeicao vai para o diario, nao para as receitas: o toast diz onde procurar
			showToast(offer.item_kind === 'meal' ? m.sharing_meal_added_toast() : m.sharing_added_toast());
		} catch (e) {
			showToast(errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR'));
		} finally {
			answering = null;
			await afterAnswer();
		}
	}

	async function declineOffer(offer: ShareOffer): Promise<void> {
		answering = `offer-${offer.id}`;
		try {
			await api.declineShareOffer(offer.id);
			showToast(m.sharing_dismissed_toast());
		} finally {
			answering = null;
			await afterAnswer();
		}
	}

	async function acceptInvite(connection: Connection): Promise<void> {
		answering = `invite-${connection.id}`;
		try {
			await api.acceptConnection(connection.id);
			showToast(m.sharing_accepted_toast());
		} finally {
			answering = null;
			await afterAnswer();
		}
	}
</script>

{#if pendingCount > 0}
	<button
		type="button"
		onclick={() => (sheetOpen = true)}
		class="mb-3 flex w-full items-center gap-3 rounded-3xl bg-emerald-600 px-4 py-3 text-left text-[#fff] shadow-lg shadow-emerald-600/25 active:bg-emerald-700"
	>
		<span class="flex shrink-0">
			{#each avatarNames as name, index (name)}
				<span
					class="grid h-9 w-9 place-items-center rounded-full bg-emerald-100 text-sm font-black text-emerald-700 ring-2 ring-emerald-600
						{index > 0 ? '-ml-2.5' : ''}"
				>
					{initial(name)}
				</span>
			{/each}
		</span>
		<span class="min-w-0 flex-1">
			<span class="block truncate font-black">
				{pendingCount === 1
					? m.sharing_banner_title_one({ names: senderNames })
					: m.sharing_banner_title_many({ count: pendingCount, names: senderNames })}
			</span>
			<span class="block truncate text-xs text-[#d1fae5]">{kindsSummary}</span>
		</span>
		<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 text-[#a7f3d0]" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
	</button>
{/if}

{#if sheetOpen}
	<div
		class="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
		role="button"
		tabindex="-1"
		onclick={() => (sheetOpen = false)}
		onkeydown={(e) => e.key === 'Escape' && (sheetOpen = false)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-slate-50 p-4 pb-[calc(1.25rem+env(safe-area-inset-bottom))] sm:rounded-3xl sm:pb-5"
			role="dialog"
			aria-modal="true"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-3 flex items-center justify-between gap-3 px-1">
				<h2 class="text-lg font-bold text-slate-900">{m.sharing_banner_sheet_title()}</h2>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (sheetOpen = false)}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-slate-400 active:bg-slate-100"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
				</button>
			</div>

			<div class="space-y-2.5">
				{#each offers as offer (offer.id)}
					{@const busy = answering === `offer-${offer.id}`}
					<article class="rounded-3xl bg-white p-4 shadow-sm">
						<div class="flex items-center gap-3">
							<span class="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-emerald-100 font-black text-emerald-700">
								{initial(offer.from_name)}
							</span>
							<div class="min-w-0 flex-1">
								<p class="text-[11px] font-black tracking-wide text-emerald-700 uppercase">
									{offerKindLabel(offer)}
								</p>
								<p class="truncate font-bold text-slate-900">
									{offer.item_kind === 'meal' ? mealOfferTitle(offer) : offer.item_name}
								</p>
								<p class="text-xs text-slate-500">{m.sharing_from({ name: offer.from_name })}</p>
							</div>
						</div>

						{#if offer.item_kind === 'meal' && offer.meal_items.length > 0}
							<ul class="mt-3 overflow-hidden rounded-2xl border-2 border-slate-100 text-sm">
								{#each offer.meal_items as item, index (index)}
									<li class="flex items-center justify-between gap-2 px-3 py-2 {index > 0 ? 'border-t border-slate-100' : ''}">
										<span class="min-w-0 truncate text-slate-700">
											{item.name} ·
											{item.source === 'food'
												? m.sharing_meal_item_grams({ grams: nf.format(item.quantity) })
												: m.sharing_meal_item_servings({ servings: nf.format(item.quantity) })}
										</span>
										<span class="shrink-0 font-bold text-slate-900">{Math.round(item.kcal)} kcal</span>
									</li>
								{/each}
								<li class="flex justify-between border-t border-slate-100 bg-slate-50 px-3 py-2">
									<span class="font-bold text-slate-700">{m.sharing_meal_total()}</span>
									<span class="font-black text-slate-900">{mealOfferSummary(offer)}</span>
								</li>
							</ul>
						{/if}

						<div class="mt-3 flex gap-2">
							<button
								type="button"
								disabled={busy}
								onclick={() => acceptOffer(offer)}
								class="h-11 flex-1 rounded-2xl bg-emerald-600 text-sm font-bold text-[#fff] active:bg-emerald-700 disabled:opacity-50"
							>
								{offer.item_kind === 'meal' ? m.sharing_banner_add_to_diary() : m.sharing_add_action()}
							</button>
							<button
								type="button"
								disabled={busy}
								onclick={() => declineOffer(offer)}
								class="h-11 shrink-0 rounded-2xl bg-slate-100 px-4 text-sm font-bold text-slate-600 active:bg-slate-200 disabled:opacity-50"
							>
								{m.sharing_dismiss_action()}
							</button>
						</div>
					</article>
				{/each}

				{#each invites as connection (connection.id)}
					<article class="rounded-3xl bg-white p-4 shadow-sm">
						<div class="flex items-center gap-3">
							<span class="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-sky-100 font-black text-sky-700">
								{initial(connection.person_name)}
							</span>
							<div class="min-w-0 flex-1">
								<p class="text-[11px] font-black tracking-wide text-sky-700 uppercase">{m.sharing_kind_invite()}</p>
								<p class="truncate font-bold text-slate-900">{connection.person_name}</p>
								<p class="text-xs text-slate-500">{m.sharing_banner_invite_hint()}</p>
							</div>
						</div>
						<div class="mt-3 flex gap-2">
							<button
								type="button"
								disabled={answering === `invite-${connection.id}`}
								onclick={() => acceptInvite(connection)}
								class="h-11 flex-1 rounded-2xl bg-emerald-600 text-sm font-bold text-[#fff] active:bg-emerald-700 disabled:opacity-50"
							>
								{m.sharing_accept()}
							</button>
							<a
								href="/perfil/conexoes"
								class="grid h-11 shrink-0 place-items-center rounded-2xl bg-slate-100 px-4 text-sm font-bold text-slate-600 active:bg-slate-200"
							>
								{m.sharing_banner_see_connections()}
							</a>
						</div>
					</article>
				{/each}
			</div>
		</div>
	</div>
{/if}
