<script lang="ts">
	import { api, ApiError, type FeedbackReport } from '$lib/api';
	import { showToast } from '$lib/toast.svelte';
	import { errorMessage, moduleLabel, shortDate } from '$lib/format';

	type Filtro = 'todos' | 'nao_lidos' | 'lidos';

	let reports = $state<FeedbackReport[]>([]);
	let filtro = $state<Filtro>('todos');
	let carregando = $state(true);

	$effect(() => {
		void api
			.listFeedback()
			.then((lista) => {
				reports = lista;
			})
			.catch((error) => {
				showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
			})
			.finally(() => {
				carregando = false;
			});
	});

	const naoLidos = $derived(reports.filter((report) => !report.read).length);
	const visiveis = $derived(
		reports.filter((report) => {
			if (filtro === 'nao_lidos') return !report.read;
			if (filtro === 'lidos') return report.read;
			return true;
		})
	);

	// Marcar como lido e reversivel em um toque e ja tem retorno visual pelo
	// proprio estado - por isso nao pede confirmacao, so o toast.
	async function alternarLeitura(report: FeedbackReport): Promise<void> {
		const novoEstado = !report.read;
		try {
			const atualizado = await api.setFeedbackRead(report.id, novoEstado);
			reports = reports.map((item) => (item.id === report.id ? atualizado : item));
			showToast(novoEstado ? 'Mensagem marcada como lida' : 'Mensagem marcada como nao lida');
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		}
	}
</script>

<article class="card">
	<div class="card-head" style="flex-wrap:wrap;gap:10px">
		<div>
			<h2 class="card-title">Feedbacks recebidos</h2>
			<p class="card-note">
				{naoLidos} nao {naoLidos === 1 ? 'lido' : 'lidos'} de {reports.length}
				{reports.length === 1 ? 'mensagem' : 'mensagens'}
			</p>
		</div>
		<div class="card-head-tools">
			<div class="segmented" role="group" aria-label="Filtrar feedbacks">
				<button type="button" aria-pressed={filtro === 'todos'} onclick={() => (filtro = 'todos')}>
					Todos
				</button>
				<button
					type="button"
					aria-pressed={filtro === 'nao_lidos'}
					onclick={() => (filtro = 'nao_lidos')}
				>
					Nao lidos
				</button>
				<button type="button" aria-pressed={filtro === 'lidos'} onclick={() => (filtro = 'lidos')}>
					Lidos
				</button>
			</div>
		</div>
	</div>

	{#if carregando}
		<div class="card-body"><p class="mono" style="color:var(--ink-3)">carregando…</p></div>
	{:else if visiveis.length === 0}
		<div class="empty">
			<div class="empty-mark" aria-hidden="true">
				<svg
					width="20"
					height="20"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
					stroke-linejoin="round"
					><path
						d="M20 14.5a2.5 2.5 0 0 1-2.5 2.5H9l-4 3V6.5A2.5 2.5 0 0 1 7.5 4h10A2.5 2.5 0 0 1 20 6.5z"
					/></svg
				>
			</div>
			<h3>Caixa limpa</h3>
			<p>Nenhuma mensagem neste filtro. Volte para "Todos" para rever o que ja foi lido.</p>
		</div>
	{:else}
		<div class="lista">
			{#each visiveis as report (report.id)}
				<button
					class="fb-item"
					class:is-unread={!report.read}
					type="button"
					onclick={() => alternarLeitura(report)}
				>
					<span class="fb-flag" aria-hidden="true"></span>
					<span class="fb-main">
						<span class="fb-top">
							<span class="fb-who">{report.user_email}</span>
							<span class="pill pill-cut">{moduleLabel(report.module)}</span>
							{#if !report.read}
								<span class="pill pill-cold">Nao lido</span>
							{/if}
							<span class="fb-when">{shortDate(report.created_at)}</span>
						</span>
						<span class="fb-text">{report.description}</span>
					</span>
				</button>
			{/each}
		</div>
	{/if}
</article>

<style>
	.lista {
		display: flex;
		flex-direction: column;
		border-top: 1px solid var(--hairline);
	}
</style>
