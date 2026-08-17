<script lang="ts">
	import {
		api,
		ApiError,
		type AdminUserDetail,
		type AdminUserPage,
		type AdminUserRow,
		type UserQuery
	} from '$lib/api';
	import { showToast } from '$lib/toast.svelte';
	import {
		daysSince,
		errorMessage,
		fullDate,
		initials,
		num,
		objectiveLabel,
		objectivePill,
		relativeDays,
		shortDate
	} from '$lib/format';

	// Estado da consulta. Tudo daqui vira query string: quem pagina, filtra e
	// ordena e o servidor - a tela so pede a fatia.
	let query = $state<UserQuery>({
		page: 1,
		page_size: 20,
		q: '',
		objective: '',
		active_within_days: '',
		inactive_for_days: '',
		signed_up_within_days: '',
		sort: 'created_at',
		order: 'desc'
	});

	let resultado = $state<AdminUserPage | null>(null);
	let carregando = $state(false);
	let buscaTexto = $state('');

	let detalhe = $state<AdminUserDetail | null>(null);
	let gavetaAberta = $state(false);
	let confirmandoReset = $state(false);
	let enviandoReset = $state(false);

	let buscaTimer: ReturnType<typeof setTimeout> | null = null;

	// Uma consulta por mudanca de estado. O $effect le `query` inteiro, entao
	// qualquer filtro/ordenacao/pagina dispara o refetch sozinho.
	$effect(() => {
		const atual = { ...query };
		carregando = true;
		api
			.listUsers(atual)
			.then((page) => {
				resultado = page;
			})
			.catch((error) => {
				showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
			})
			.finally(() => {
				carregando = false;
			});
	});

	// Digitar filtra com atraso curto: sem isso cada tecla vira uma ida ao servidor.
	function aoDigitar(event: Event): void {
		buscaTexto = (event.target as HTMLInputElement).value;
		if (buscaTimer) clearTimeout(buscaTimer);
		buscaTimer = setTimeout(() => {
			query = { ...query, q: buscaTexto, page: 1 };
		}, 300);
	}

	function ordenarPor(coluna: UserQuery['sort']): void {
		const mesmaColuna = query.sort === coluna;
		query = {
			...query,
			sort: coluna,
			order: mesmaColuna && query.order === 'desc' ? 'asc' : 'desc',
			page: 1
		};
	}

	function ariaSort(coluna: UserQuery['sort']): 'ascending' | 'descending' | undefined {
		if (query.sort !== coluna) return undefined;
		return query.order === 'asc' ? 'ascending' : 'descending';
	}

	function limparFiltros(): void {
		buscaTexto = '';
		query = {
			...query,
			q: '',
			objective: '',
			active_within_days: '',
			inactive_for_days: '',
			signed_up_within_days: '',
			page: 1
		};
		showToast('Filtros limpos');
	}

	function removerFiltro(chave: keyof UserQuery): void {
		if (chave === 'q') buscaTexto = '';
		query = { ...query, [chave]: '', page: 1 };
	}

	const ATIVIDADE_LABEL: Record<string, string> = {
		'7': 'Ativo em 7 dias',
		'14': 'Ativo em 14 dias',
		'30': 'Ativo em 30 dias'
	};
	const CADASTRO_LABEL: Record<string, string> = {
		'30': 'Cadastro em 30 dias',
		'90': 'Cadastro em 90 dias',
		'180': 'Cadastro em 6 meses'
	};

	const chips = $derived.by(() => {
		const lista: { chave: keyof UserQuery; rotulo: string; valor: string }[] = [];
		if (query.q) lista.push({ chave: 'q', rotulo: 'Busca', valor: query.q });
		if (query.objective)
			lista.push({ chave: 'objective', rotulo: 'Objetivo', valor: objectiveLabel(query.objective) });
		if (query.active_within_days)
			lista.push({
				chave: 'active_within_days',
				rotulo: 'Atividade',
				valor: ATIVIDADE_LABEL[String(query.active_within_days)]
			});
		if (query.inactive_for_days)
			lista.push({
				chave: 'inactive_for_days',
				rotulo: 'Parados',
				valor: `sem registro ha ${query.inactive_for_days}+ dias`
			});
		if (query.signed_up_within_days)
			lista.push({
				chave: 'signed_up_within_days',
				rotulo: 'Cadastro',
				valor: CADASTRO_LABEL[String(query.signed_up_within_days)]
			});
		return lista;
	});

	const totalPaginas = $derived(
		resultado ? Math.max(1, Math.ceil(resultado.total / resultado.page_size)) : 1
	);
	const primeiroDaPagina = $derived(
		resultado && resultado.total > 0 ? (resultado.page - 1) * resultado.page_size + 1 : 0
	);
	const ultimoDaPagina = $derived(
		resultado ? Math.min(resultado.page * resultado.page_size, resultado.total) : 0
	);

	// Paginas visiveis: primeira, ultima e as vizinhas da atual. As reticencias
	// evitam uma regua de 40 botoes quando a base cresce.
	const paginasVisiveis = $derived.by(() => {
		const paginas: (number | 'gap')[] = [];
		for (let p = 1; p <= totalPaginas; p++) {
			if (p === 1 || p === totalPaginas || Math.abs(p - query.page) <= 1) paginas.push(p);
			else if (paginas[paginas.length - 1] !== 'gap') paginas.push('gap');
		}
		return paginas;
	});

	/** Situacao pela ultima atividade - comportamento, nunca dado de saude. */
	function situacao(user: AdminUserRow): { classe: string; texto: string } {
		if (user.days_since_activity === null) return { classe: 'pill-cold', texto: 'nunca registrou' };
		if (user.days_since_activity <= 7) return { classe: 'pill-good', texto: 'ativo' };
		if (user.days_since_activity <= 30) return { classe: 'pill-warn', texto: 'esfriando' };
		return { classe: 'pill-cold', texto: 'parado' };
	}

	async function abrirDetalhe(id: number): Promise<void> {
		gavetaAberta = true;
		detalhe = null;
		confirmandoReset = false;
		try {
			detalhe = await api.getUser(id);
		} catch (error) {
			gavetaAberta = false;
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		}
	}

	function fecharGaveta(): void {
		gavetaAberta = false;
		confirmandoReset = false;
	}

	// Acao de impacto: confirma antes, toast depois. Nunca dispara no primeiro clique.
	async function confirmarReset(): Promise<void> {
		if (!detalhe) return;
		enviandoReset = true;
		try {
			await api.sendPasswordReset(detalhe.id);
			showToast(`Link de redefinicao enviado para ${detalhe.email}`);
			confirmandoReset = false;
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			enviandoReset = false;
		}
	}

	/** Uso do mes numa barra de 0 a 30: um registro por dia ja enche a barra. */
	function usoPct(valor: number): number {
		return Math.min(100, Math.round((valor / 30) * 100));
	}
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && fecharGaveta()} />

<article class="card">
	<div class="card-head" style="flex-wrap:wrap;gap:10px">
		<div>
			<h2 class="card-title">Base de usuarios</h2>
			<p class="card-note">
				{resultado ? num(resultado.total) : '—'} contas com os filtros atuais &middot; {query.page_size}
				por requisicao
			</p>
		</div>
	</div>

	<div class="card-body" style="padding-bottom:12px">
		<div class="filtros">
			<label class="field field-search">
				<svg
					width="15"
					height="15"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg
				>
				<input
					type="search"
					placeholder="Buscar por nome ou e-mail"
					aria-label="Buscar por nome ou e-mail"
					value={buscaTexto}
					oninput={aoDigitar}
				/>
			</label>

			<label class="field">
				<span class="eyebrow">Objetivo</span>
				<select
					aria-label="Filtrar por objetivo"
					value={query.objective}
					onchange={(event) =>
						(query = {
							...query,
							objective: event.currentTarget.value as UserQuery['objective'],
							page: 1
						})}
				>
					<option value="">Todos</option>
					<option value="lose_fat">Perder gordura</option>
					<option value="maintain">Manter</option>
					<option value="gain_muscle">Ganhar massa</option>
					<option value="recomp">Recomposicao</option>
				</select>
			</label>

			<label class="field">
				<span class="eyebrow">Ativo em</span>
				<select
					aria-label="Filtrar por atividade recente"
					value={query.active_within_days}
					onchange={(event) =>
						(query = {
							...query,
							active_within_days: event.currentTarget.value === '' ? '' : Number(event.currentTarget.value),
							inactive_for_days: '',
							page: 1
						})}
				>
					<option value="">Qualquer periodo</option>
					<option value="7">Ultimos 7 dias</option>
					<option value="14">Ultimos 14 dias</option>
					<option value="30">Ultimos 30 dias</option>
				</select>
			</label>

			<label class="field">
				<span class="eyebrow">Parados ha</span>
				<select
					aria-label="Filtrar por inatividade"
					value={query.inactive_for_days}
					onchange={(event) =>
						(query = {
							...query,
							inactive_for_days: event.currentTarget.value === '' ? '' : Number(event.currentTarget.value),
							active_within_days: '',
							page: 1
						})}
				>
					<option value="">Nao filtrar</option>
					<option value="14">14+ dias</option>
					<option value="30">30+ dias</option>
					<option value="90">90+ dias</option>
				</select>
			</label>

			<label class="field">
				<span class="eyebrow">Cadastro</span>
				<select
					aria-label="Filtrar por data de cadastro"
					value={query.signed_up_within_days}
					onchange={(event) =>
						(query = {
							...query,
							signed_up_within_days:
								event.currentTarget.value === '' ? '' : Number(event.currentTarget.value),
							page: 1
						})}
				>
					<option value="">Qualquer data</option>
					<option value="30">Ultimos 30 dias</option>
					<option value="90">Ultimos 90 dias</option>
					<option value="180">Ultimos 6 meses</option>
				</select>
			</label>
		</div>

		<div class="chips" style="margin-top:11px">
			{#each chips as chip (chip.chave)}
				<span class="chip">
					{chip.rotulo}: <b>{chip.valor}</b>
					<button
						type="button"
						aria-label="Remover filtro {chip.rotulo}"
						onclick={() => removerFiltro(chip.chave)}>&times;</button
					>
				</span>
			{:else}
				<span class="chips-empty">Nenhum filtro aplicado &middot; mostrando a base inteira</span>
			{/each}
			{#if chips.length > 0}
				<button class="btn btn-ghost btn-sm" type="button" onclick={limparFiltros}>
					Limpar filtros
				</button>
			{/if}
		</div>
	</div>

	<div class="query-bar" class:is-loading={carregando}></div>

	{#if resultado && resultado.total === 0}
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
					><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /><path d="M9 11h4" /></svg
				>
			</div>
			<h3>Nenhum usuario com esses filtros</h3>
			<p>
				Tente um termo mais curto na busca ou amplie o periodo. Os filtros aplicados aparecem em
				chips acima da tabela.
			</p>
			<button class="btn btn-sm" type="button" onclick={limparFiltros}>Limpar filtros</button>
		</div>
	{:else}
		<div class="table-wrap" class:is-loading={carregando}>
			<table>
				<caption class="sr-only">Usuarios cadastrados, com objetivo e ultima atividade</caption>
				<thead>
					<tr>
						<th class="sortable" scope="col" aria-sort={ariaSort('email')}>
							<button type="button" onclick={() => ordenarPor('email')}>
								Usuario {query.sort === 'email' ? (query.order === 'asc' ? '▲' : '▼') : ''}
							</button>
						</th>
						<th scope="col">Objetivo</th>
						<th class="sortable" scope="col" aria-sort={ariaSort('created_at')}>
							<button type="button" onclick={() => ordenarPor('created_at')}>
								Cadastro {query.sort === 'created_at' ? (query.order === 'asc' ? '▲' : '▼') : ''}
							</button>
						</th>
						<th class="sortable" scope="col" aria-sort={ariaSort('last_activity')}>
							<button type="button" onclick={() => ordenarPor('last_activity')}>
								Ultima atividade {query.sort === 'last_activity'
									? query.order === 'asc'
										? '▲'
										: '▼'
									: ''}
							</button>
						</th>
						<th scope="col">Situacao</th>
						<th scope="col">Dieta</th>
						<th class="num" scope="col">Acoes</th>
					</tr>
				</thead>
				<tbody>
					{#each resultado?.items ?? [] as user (user.id)}
						{@const estado = situacao(user)}
						<tr>
							<td>
								<span class="cell-user">
									<span class="avatar" aria-hidden="true">{initials(user.name, user.email)}</span>
									<span class="who">
										<span class="name">{user.name ?? user.email.split('@')[0]}</span>
										<span class="mail">{user.email}</span>
									</span>
								</span>
							</td>
							<td>
								<span class="pill {objectivePill(user.objective)}">{objectiveLabel(user.objective)}</span
								>
							</td>
							<td class="mono" style="font-size:12.5px;color:var(--ink-2);white-space:nowrap">
								{shortDate(user.created_at)}
							</td>
							<td style="white-space:nowrap">{relativeDays(user.days_since_activity)}</td>
							<td><span class="pill {estado.classe}">{estado.texto}</span></td>
							<td class="mono" style="font-size:12px;color:var(--ink-3)">
								{user.diet_enabled ? 'ligada' : '—'}
							</td>
							<td class="num">
								<span class="row-actions">
									<button class="btn btn-sm" type="button" onclick={() => abrirDetalhe(user.id)}>
										Detalhe
									</button>
								</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="pager">
			<div class="pager-range">
				<b>{num(primeiroDaPagina)}–{num(ultimoDaPagina)}</b> de {num(resultado?.total ?? 0)}
			</div>

			<label class="field" style="padding:4px 9px">
				<span class="eyebrow">Por pagina</span>
				<select
					aria-label="Registros por pagina"
					value={query.page_size}
					onchange={(event) =>
						(query = { ...query, page_size: Number(event.currentTarget.value), page: 1 })}
				>
					<option value={10}>10</option>
					<option value={20}>20</option>
					<option value={50}>50</option>
					<option value={100}>100</option>
				</select>
			</label>

			<div class="pager-right">
				<button
					class="page-btn"
					type="button"
					disabled={query.page <= 1}
					onclick={() => (query = { ...query, page: query.page - 1 })}
				>
					‹ Anterior
				</button>
				<div class="pager-pages">
					{#each paginasVisiveis as pagina, indice (typeof pagina === 'number' ? pagina : `gap-${indice}`)}
						{#if pagina === 'gap'}
							<span class="page-gap">…</span>
						{:else}
							<button
								class="page-btn"
								type="button"
								aria-current={pagina === query.page ? 'true' : undefined}
								onclick={() => (query = { ...query, page: pagina })}
							>
								{pagina}
							</button>
						{/if}
					{/each}
				</div>
				<button
					class="page-btn"
					type="button"
					disabled={query.page >= totalPaginas}
					onclick={() => (query = { ...query, page: query.page + 1 })}
				>
					Proxima ›
				</button>
			</div>
		</div>
	{/if}
</article>

<!-- Gaveta de detalhe -->
<div
	class="scrim"
	class:is-open={gavetaAberta}
	onclick={fecharGaveta}
	role="presentation"
	aria-hidden="true"
></div>

<aside class="drawer" class:is-open={gavetaAberta} aria-label="Detalhe do usuario">
	{#if detalhe}
		<div class="drawer-head">
			<div
				class="avatar"
				style="width:40px;height:40px;border-radius:11px;font-size:13px"
				aria-hidden="true"
			>
				{initials(detalhe.name, detalhe.email)}
			</div>
			<div style="min-width:0">
				<h2 class="card-title" style="font-size:16px">
					{detalhe.name ?? detalhe.email.split('@')[0]}
				</h2>
				<p class="mono" style="font-size:11.5px;color:var(--ink-3)">{detalhe.email}</p>
			</div>
			<button class="btn btn-ghost btn-sm" type="button" onclick={fecharGaveta} style="margin-left:auto">
				Fechar
			</button>
		</div>

		<div class="drawer-body">
			<section>
				<div class="section-label">Conta</div>
				<div class="datagrid">
					<div><div class="k">Conta</div><div class="v mono">#{detalhe.id}</div></div>
					<div>
						<div class="k">Objetivo</div>
						<div class="v">
							<span class="pill {objectivePill(detalhe.objective)}">
								{objectiveLabel(detalhe.objective)}
							</span>
						</div>
					</div>
					<div><div class="k">Plano</div><div class="v">{detalhe.plan === 'premium' ? 'Premium' : 'Gratuito'}</div></div>
					<div><div class="k">Idioma</div><div class="v mono">{detalhe.locale}</div></div>
					<div><div class="k">Dieta</div><div class="v">{detalhe.diet_enabled ? 'Ligada' : 'Desligada'}</div></div>
					<div><div class="k">Ciclo</div><div class="v">{detalhe.cycle_enabled ? 'Acompanha' : 'Nao usa'}</div></div>
					<div>
						<div class="k">Cadastro</div>
						<div class="v" style="font-size:13px">{fullDate(detalhe.created_at)}</div>
					</div>
					<div>
						<div class="k">Ha</div>
						<div class="v" style="font-size:13px">{daysSince(detalhe.created_at)} dias</div>
					</div>
				</div>
			</section>

			<section>
				<div class="section-label">Uso nos ultimos 30 dias</div>
				<div class="usage-box">
					<div class="usage-row">
						<span class="k">Refeicoes lancadas</span>
						<span class="meter">
							<span class="meter-track"
								><span class="meter-fill" style="width:{usoPct(detalhe.meals_30d)}%"></span></span
							>
							<span class="v">{num(detalhe.meals_30d)}</span>
						</span>
					</div>
					<div class="usage-row">
						<span class="k">Treinos concluidos</span>
						<span class="meter">
							<span class="meter-track"
								><span class="meter-fill" style="width:{usoPct(detalhe.workouts_30d)}%"></span></span
							>
							<span class="v">{num(detalhe.workouts_30d)}</span>
						</span>
					</div>
					<div class="usage-row">
						<span class="k">Pesagens registradas</span>
						<span class="meter">
							<span class="meter-track"
								><span class="meter-fill" style="width:{usoPct(detalhe.weigh_ins_30d)}%"></span></span
							>
							<span class="v">{num(detalhe.weigh_ins_30d)}</span>
						</span>
					</div>
					<div class="usage-row">
						<span class="k">Conexoes aceitas</span>
						<span class="v">{num(detalhe.connections)}</span>
					</div>
					<div class="usage-row">
						<span class="k">Ultima atividade</span>
						<span class="v">{relativeDays(detalhe.days_since_activity)}</span>
					</div>
				</div>
				<p class="nota">
					O painel mostra comportamento, nunca dado de saude: quantas vezes a pessoa pesou aparece
					aqui, quanto ela pesa nao.
				</p>
			</section>

			<section>
				<div class="section-label">Acoes administrativas</div>
				{#if confirmandoReset}
					<div class="confirm">
						<p>
							Enviar o link de redefinicao para <b>{detalhe.email}</b>? A senha atual continua
							valendo ate o link ser usado.
						</p>
						<div class="actions">
							<button
								class="btn btn-sm btn-ghost"
								type="button"
								onclick={() => (confirmandoReset = false)}
							>
								Cancelar
							</button>
							<button
								class="btn btn-sm btn-accent"
								type="button"
								disabled={enviandoReset}
								onclick={confirmarReset}
							>
								{enviandoReset ? 'Enviando…' : 'Confirmar'}
							</button>
						</div>
					</div>
				{:else}
					<button class="btn" type="button" onclick={() => (confirmandoReset = true)}>
						<svg
							width="15"
							height="15"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.9"
							stroke-linecap="round"
							stroke-linejoin="round"
							><rect x="4" y="10" width="16" height="10" rx="2.4" /><path
								d="M8 10V7.5a4 4 0 0 1 8 0V10"
							/></svg
						>
						Enviar redefinicao de senha
					</button>
				{/if}
			</section>
		</div>
	{:else if gavetaAberta}
		<div class="drawer-body"><p class="mono" style="color:var(--ink-3)">carregando…</p></div>
	{/if}
</aside>

<style>
	.filtros {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
	}
	.nota {
		font-size: 11.5px;
		color: var(--ink-3);
		line-height: 1.5;
		margin-top: 9px;
	}
</style>
