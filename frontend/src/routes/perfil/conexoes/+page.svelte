<script lang="ts">
	import { ApiError, api, type Connection, type ShareOffer } from '$lib/api';
	import { errorMessage } from '$lib/errors';
	import { refreshSharingPending } from '$lib/sharing.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';

	let connections = $state<Connection[]>([]);
	// Itens esperando aceite moram AQUI tambem, e nao so em Minhas receitas: e para
	// onde o aviso da barra de abas aponta, entao tudo que espera uma acao sua precisa
	// estar num lugar so.
	let offers = $state<ShareOffer[]>([]);
	let answering = $state<number | null>(null);
	let loading = $state(true);

	let email = $state('');
	let inviting = $state(false);
	let inviteError = $state('');

	// Desfazer conexao mexe no que a outra pessoa ve: confirma antes, como todo
	// delete do app.
	let confirmingRemove = $state<number | null>(null);

	async function load(): Promise<void> {
		[connections, offers] = await Promise.all([api.getConnections(), api.getShareOffers()]);
		await refreshSharingPending();
		loading = false;
	}

	$effect(() => {
		load();
	});

	async function acceptOffer(offer: ShareOffer): Promise<void> {
		answering = offer.id;
		try {
			await api.acceptShareOffer(offer.id);
			await load();
			showToast(m.sharing_added_toast());
		} catch (e) {
			showToast(errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR'));
			await load();
		} finally {
			answering = null;
		}
	}

	async function declineOffer(offer: ShareOffer): Promise<void> {
		answering = offer.id;
		try {
			await api.declineShareOffer(offer.id);
			await load();
			showToast(m.sharing_dismissed_toast());
		} finally {
			answering = null;
		}
	}

	const accepted = $derived(connections.filter((c) => c.status === 'accepted'));
	const waitingMe = $derived(connections.filter((c) => c.status === 'pending' && !c.i_invited));
	const waitingThem = $derived(connections.filter((c) => c.status === 'pending' && c.i_invited));

	async function invite(): Promise<void> {
		const address = email.trim();
		if (!address) return;
		inviting = true;
		inviteError = '';
		try {
			await api.inviteConnection(address);
			email = '';
			await load();
			showToast(m.sharing_invite_sent());
		} catch (e) {
			inviteError = errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR');
		} finally {
			inviting = false;
		}
	}

	async function accept(connection: Connection): Promise<void> {
		await api.acceptConnection(connection.id);
		await load();
		showToast(m.sharing_accepted_toast());
	}

	async function remove(connection: Connection): Promise<void> {
		confirmingRemove = null;
		await api.removeConnection(connection.id);
		await load();
		showToast(m.toast_deleted());
	}

	function initials(name: string): string {
		const parts = name.trim().split(/\s+/);
		const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : parts[0].slice(0, 2);
		return letters.toUpperCase();
	}
</script>

<div class="mb-4 flex items-center gap-2">
	<a
		href="/perfil"
		aria-label={m.back()}
		class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
	>
		<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
	</a>
	<h1 class="text-2xl font-bold">{m.sharing_title()}</h1>
</div>

<p class="mb-4 text-sm text-slate-500">{m.sharing_subtitle()}</p>

<!-- Itens esperando aceite vem PRIMEIRO: e o que o aviso da barra de abas prometeu. -->
{#if offers.length > 0}
	<section class="mb-3 overflow-hidden rounded-3xl bg-white shadow-sm ring-2 ring-emerald-400">
		<p class="px-5 pt-4 pb-2 text-xs font-black tracking-wide text-emerald-700 uppercase">
			{m.sharing_inbox_title()}
		</p>
		<div class="space-y-2 px-3 pb-3">
			{#each offers as offer (offer.id)}
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-[10px] font-bold tracking-wide text-slate-400 uppercase">
						{offer.item_kind === 'recipe' ? m.sharing_kind_recipe() : m.sharing_kind_food()}
					</p>
					<p class="truncate font-bold text-slate-900">{offer.item_name}</p>
					<p class="text-xs font-semibold text-emerald-700">
						{m.sharing_from({ name: offer.from_name })}
					</p>
					<div class="mt-2.5 flex gap-2">
						<button
							type="button"
							disabled={answering === offer.id}
							onclick={() => acceptOffer(offer)}
							class="h-10 flex-1 rounded-xl bg-emerald-600 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
						>
							{m.sharing_add_action()}
						</button>
						<button
							type="button"
							disabled={answering === offer.id}
							onclick={() => declineOffer(offer)}
							class="h-10 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100 disabled:opacity-50"
						>
							{m.sharing_dismiss_action()}
						</button>
					</div>
				</div>
			{/each}
		</div>
	</section>
{/if}

<!-- Convidar por e-mail: a pessoa precisa ja ter conta no app -->
<section class="mb-3 rounded-3xl bg-white p-5 shadow-sm">
	<label class="mb-1.5 block text-xs font-bold text-slate-500" for="invite-email">
		{m.sharing_invite_label()}
	</label>
	<div class="flex gap-2">
		<input
			id="invite-email"
			type="email"
			autocomplete="email"
			bind:value={email}
			onkeydown={(e) => e.key === 'Enter' && invite()}
			placeholder="email@exemplo.com"
			class="h-12 min-w-0 flex-1 rounded-2xl border-2 border-slate-200 px-3 outline-none focus:border-emerald-600"
		/>
		<button
			type="button"
			disabled={inviting || !email.trim()}
			onclick={invite}
			class="h-12 shrink-0 rounded-2xl bg-emerald-600 px-5 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
		>
			{m.sharing_invite_action()}
		</button>
	</div>
	{#if inviteError}
		<p class="mt-2 text-sm font-semibold text-red-600">{inviteError}</p>
	{/if}
</section>

{#snippet personRow(connection: Connection, hint: string, accentClass: string)}
	<div class="flex items-center gap-3 p-4">
		<span class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-sm font-black {accentClass}">
			{initials(connection.person_name)}
		</span>
		<div class="min-w-0 flex-1">
			<p class="truncate font-bold text-slate-900">{connection.person_name}</p>
			<p class="truncate text-xs text-slate-500">{hint}</p>
		</div>
		{#if connection.status === 'pending' && !connection.i_invited}
			<button
				type="button"
				onclick={() => accept(connection)}
				class="h-10 shrink-0 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white active:bg-emerald-700"
			>
				{m.sharing_accept()}
			</button>
		{/if}
		<button
			type="button"
			aria-label={m.confirm_delete()}
			onclick={() => (confirmingRemove = connection.id)}
			class="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-slate-300 active:bg-red-50 active:text-red-500"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
	</div>
	{#if confirmingRemove === connection.id}
		<div class="mx-3 mb-3 rounded-2xl bg-red-50 p-3">
			<p class="text-sm font-semibold text-red-700">{m.sharing_remove_confirm()}</p>
			<p class="mt-0.5 text-xs text-red-600/80">{m.sharing_remove_hint()}</p>
			<div class="mt-2.5 flex gap-2">
				<button
					type="button"
					onclick={() => remove(connection)}
					class="h-10 flex-1 rounded-xl bg-red-600 px-4 text-sm font-bold text-white active:bg-red-700"
				>
					{m.confirm_delete()}
				</button>
				<button
					type="button"
					onclick={() => (confirmingRemove = null)}
					class="h-10 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
				>
					{m.cancel()}
				</button>
			</div>
		</div>
	{/if}
{/snippet}

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else if connections.length === 0}
	<div class="rounded-3xl border-2 border-dashed border-slate-200 p-8 text-center">
		<p class="font-semibold text-slate-600">{m.sharing_empty()}</p>
	</div>
{:else}
	<div class="space-y-3">
		<!-- quem espera voce responder vem primeiro: e a unica linha com acao pendente -->
		{#each waitingMe as connection (connection.id)}
			<section class="overflow-hidden rounded-3xl bg-white shadow-sm ring-2 ring-emerald-400">
				{@render personRow(connection, m.sharing_pending_received(), 'bg-emerald-100 text-emerald-700')}
			</section>
		{/each}
		{#each accepted as connection (connection.id)}
			<section class="overflow-hidden rounded-3xl bg-white shadow-sm">
				{@render personRow(connection, connection.person_email, 'bg-slate-100 text-slate-600')}
			</section>
		{/each}
		{#each waitingThem as connection (connection.id)}
			<section class="overflow-hidden rounded-3xl bg-white shadow-sm opacity-70">
				{@render personRow(connection, m.sharing_pending_sent(), 'bg-slate-100 text-slate-500')}
			</section>
		{/each}
	</div>
{/if}
