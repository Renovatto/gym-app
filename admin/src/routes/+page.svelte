<script lang="ts">
	import type { EChartsOption } from 'echarts';
	import { base } from '$app/paths';
	import Chart from '$lib/components/Chart.svelte';
	import { api, type AdminActivitySeries, type AdminOverview, type AdminUserRow } from '$lib/api';
	import { themeState, themeToken } from '$lib/theme.svelte';
	import {
		daysSince,
		initials,
		num,
		objectiveLabel,
		objectivePill,
		relativeDays,
		shortDate
	} from '$lib/format';

	let overview = $state<AdminOverview | null>(null);
	let series = $state<AdminActivitySeries | null>(null);
	let recentes = $state<AdminUserRow[]>([]);
	let carregando = $state(true);

	$effect(() => {
		void (async () => {
			try {
				const [kpis, activity, page] = await Promise.all([
					api.overview(),
					api.activity(30),
					api.listUsers({ page: 1, page_size: 8, sort: 'created_at', order: 'desc' })
				]);
				overview = kpis;
				series = activity;
				recentes = page.items;
			} finally {
				carregando = false;
			}
		})();
	});

	// Percentual da base que esteve ativa na semana - o numero que responde
	// "quem esta usando de verdade" melhor que o total absoluto.
	const ativosPct = $derived(
		overview && overview.total_users > 0
			? Math.round((overview.active_7d / overview.total_users) * 100)
			: 0
	);

	/** Base comum dos graficos: grade discreta, tooltip do tema, fonte mono nos eixos. */
	function baseOption(): EChartsOption {
		// Ler o tema aqui e o que faz os graficos se repintarem ao trocar claro/escuro.
		themeState.current;
		return {
			textStyle: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
			grid: { top: 24, right: 16, bottom: 28, left: 48, containLabel: false },
			tooltip: {
				trigger: 'axis',
				backgroundColor: themeToken('--surface'),
				borderColor: themeToken('--hairline-2'),
				textStyle: { color: themeToken('--ink'), fontSize: 12 },
				axisPointer: { lineStyle: { color: themeToken('--axis') } }
			}
		};
	}

	function axisStyle() {
		return {
			axisLine: { lineStyle: { color: themeToken('--axis') } },
			axisTick: { show: false },
			axisLabel: { color: themeToken('--ink-3'), fontSize: 10 },
			splitLine: { lineStyle: { color: themeToken('--grid') } }
		};
	}

	const linhaAtivos = $derived.by<EChartsOption>(() => {
		const points = series?.points ?? [];
		return {
			...baseOption(),
			xAxis: {
				type: 'category',
				data: points.map((p) => shortDate(p.day)),
				...axisStyle(),
				splitLine: { show: false }
			},
			yAxis: { type: 'value', ...axisStyle() },
			series: [
				{
					name: 'Usuarios ativos',
					type: 'line',
					smooth: true,
					showSymbol: false,
					data: points.map((p) => p.active_users),
					lineStyle: { width: 2, color: themeToken('--series-1') },
					itemStyle: { color: themeToken('--series-1') },
					areaStyle: { color: themeToken('--accent-wash') }
				}
			]
		};
	});

	// Treinos por dia da semana: agregado no cliente a partir da mesma serie de 30
	// dias. Nao pede endpoint novo e responde "que dia a academia enche".
	const barrasSemana = $derived.by<EChartsOption>(() => {
		const rotulos = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sab'];
		const soma = [0, 0, 0, 0, 0, 0, 0];
		for (const point of series?.points ?? []) {
			// O dia vem como "AAAA-MM-DD": monta a data local sem fuso para o dia da
			// semana nao escorregar por causa do UTC.
			const [ano, mes, dia] = point.day.split('-').map(Number);
			soma[new Date(ano, mes - 1, dia).getDay()] += point.workouts;
		}
		const pico = Math.max(...soma);
		return {
			...baseOption(),
			grid: { top: 24, right: 16, bottom: 28, left: 40 },
			xAxis: { type: 'category', data: rotulos, ...axisStyle(), splitLine: { show: false } },
			yAxis: { type: 'value', ...axisStyle() },
			series: [
				{
					name: 'Treinos',
					type: 'bar',
					data: soma.map((valor) => ({
						value: valor,
						// So o pico recebe a cor cheia: o resto fica esmaecido para o
						// olho achar o dia mais forte sem ler numero.
						itemStyle: {
							color: themeToken('--series-1'),
							opacity: valor === pico && pico > 0 ? 1 : 0.5,
							borderRadius: [4, 4, 0, 0]
						}
					}))
				}
			]
		};
	});

	const roscaObjetivo = $derived.by<EChartsOption>(() => {
		const cores = [themeToken('--series-1'), themeToken('--series-2'), themeToken('--series-3')];
		const fatias = (overview?.objectives ?? []).map((slice, index) => ({
			name: objectiveLabel(slice.objective),
			value: slice.users,
			itemStyle: { color: cores[index % cores.length] }
		}));
		return {
			textStyle: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
			tooltip: {
				trigger: 'item',
				backgroundColor: themeToken('--surface'),
				borderColor: themeToken('--hairline-2'),
				textStyle: { color: themeToken('--ink'), fontSize: 12 },
				formatter: '{b}: {c} contas ({d}%)'
			},
			legend: {
				bottom: 0,
				icon: 'roundRect',
				itemWidth: 9,
				itemHeight: 9,
				textStyle: { color: themeToken('--ink-2'), fontSize: 12 }
			},
			series: [
				{
					type: 'pie',
					radius: ['58%', '78%'],
					center: ['50%', '44%'],
					// Folga de 2px na cor da superficie entre as fatias, sem contorno.
					itemStyle: { borderColor: themeToken('--surface'), borderWidth: 2 },
					label: { show: false },
					data: fatias
				}
			]
		};
	});
</script>

{#if carregando}
	<p class="mono" style="color:var(--ink-3)">carregando…</p>
{:else if overview}
	<div class="grid kpis" style="margin-bottom:14px">
		<article class="card kpi">
			<div class="eyebrow">Ativos 7 dias</div>
			<div class="kpi-value">{num(overview.active_7d)}</div>
			<div class="kpi-foot">
				<span class="delta flat">{ativosPct}%</span>
				<span class="kpi-note">da base</span>
			</div>
		</article>
		<article class="card kpi">
			<div class="eyebrow">Ativos 30 dias</div>
			<div class="kpi-value">{num(overview.active_30d)}</div>
			<div class="kpi-foot"><span class="kpi-note">registraram algo no mes</span></div>
		</article>
		<article class="card kpi">
			<div class="eyebrow">Novos cadastros</div>
			<div class="kpi-value">{num(overview.new_users_30d)}</div>
			<div class="kpi-foot">
				<span class="delta up">+{num(overview.new_users_7d)}</span>
				<span class="kpi-note">nos ultimos 7 dias</span>
			</div>
		</article>
		<article class="card kpi">
			<div class="eyebrow">Refeicoes 7 dias</div>
			<div class="kpi-value">{num(overview.meals_7d)}</div>
			<div class="kpi-foot"><span class="kpi-note">lancamentos no diario</span></div>
		</article>
		<article class="card kpi">
			<div class="eyebrow">Treinos 7 dias</div>
			<div class="kpi-value">{num(overview.workouts_7d)}</div>
			<div class="kpi-foot"><span class="kpi-note">sessoes iniciadas</span></div>
		</article>
	</div>

	<div class="grid charts-2" style="margin-bottom:14px">
		<article class="card">
			<div class="card-head">
				<div>
					<h2 class="card-title">Usuarios ativos por dia</h2>
					<p class="card-note">
						Quem registrou refeicao, treino ou pesagem &middot; ultimos 30 dias
					</p>
				</div>
			</div>
			<div class="card-body"><Chart option={linhaAtivos} height={260} /></div>
		</article>

		<article class="card">
			<div class="card-head">
				<div>
					<h2 class="card-title">Distribuicao de objetivo</h2>
					<p class="card-note">{num(overview.total_users)} contas &middot; sem perfil fica de fora</p>
				</div>
			</div>
			<div class="card-body"><Chart option={roscaObjetivo} height={260} /></div>
		</article>
	</div>

	<div class="grid charts-2">
		<article class="card">
			<div class="card-head">
				<div>
					<h2 class="card-title">Treinos por dia da semana</h2>
					<p class="card-note">Soma dos ultimos 30 dias</p>
				</div>
			</div>
			<div class="card-body"><Chart option={barrasSemana} height={240} /></div>
		</article>

		<article class="card">
			<div class="card-head">
				<div>
					<h2 class="card-title">Ultimos cadastros</h2>
					<p class="card-note">8 contas mais recentes</p>
				</div>
				<div class="card-head-tools">
					<a class="btn btn-ghost btn-sm" href="{base}/usuarios">Ver todos</a>
				</div>
			</div>
			<div class="card-body">
				<ul class="feed">
					{#each recentes as user (user.id)}
						<li class="feed-item">
							<span class="avatar" aria-hidden="true">{initials(user.name, user.email)}</span>
							<span class="who">
								<span class="name">{user.name ?? user.email.split('@')[0]}</span>
								<span class="mono meta">{user.email}</span>
							</span>
							<span class="pill {objectivePill(user.objective)}">{objectiveLabel(user.objective)}</span
							>
							<span class="mono when">{relativeDays(daysSince(user.created_at))}</span>
						</li>
					{:else}
						<li class="mono" style="color:var(--ink-3);padding:10px 0">nenhuma conta ainda</li>
					{/each}
				</ul>
			</div>
		</article>
	</div>
{:else}
	<div class="card empty">
		<h3>Nao foi possivel carregar as metricas</h3>
		<p>A API nao respondeu. Recarregue a pagina para tentar de novo.</p>
	</div>
{/if}

<style>
	.feed {
		display: flex;
		flex-direction: column;
	}
	.feed-item {
		display: flex;
		align-items: center;
		gap: 11px;
		padding: 10px 0;
		border-bottom: 1px solid var(--hairline);
	}
	.feed-item:last-child {
		border-bottom: 0;
	}
	.who {
		min-width: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
	}
	.name {
		font-size: 13.5px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.meta {
		font-size: 11px;
		color: var(--ink-3);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.when {
		font-size: 11.5px;
		color: var(--ink-3);
		white-space: nowrap;
		flex: none;
	}
</style>
