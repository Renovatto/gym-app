<script lang="ts">
	import type { EChartsOption } from 'echarts';
	import Chart from '$lib/components/Chart.svelte';
	import { api, ApiError, type AdminActivitySeries } from '$lib/api';
	import { themeState, themeToken } from '$lib/theme.svelte';
	import { errorMessage, num, shortDate } from '$lib/format';
	import { showToast } from '$lib/toast.svelte';

	let periodo = $state(90);
	let series = $state<AdminActivitySeries | null>(null);
	let carregando = $state(true);

	$effect(() => {
		const dias = periodo;
		carregando = true;
		api
			.activity(dias)
			.then((data) => {
				series = data;
			})
			.catch((error) => {
				showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
			})
			.finally(() => {
				carregando = false;
			});
	});

	interface Semana {
		inicio: string;
		ativosPico: number;
		refeicoes: number;
		treinos: number;
	}

	// Agrega a serie diaria em semanas. Feito no cliente de proposito: o mesmo
	// endpoint serve o dashboard e os relatorios, sem rota nova por recorte.
	const semanas = $derived.by<Semana[]>(() => {
		const points = series?.points ?? [];
		const blocos: Semana[] = [];
		for (let inicio = 0; inicio < points.length; inicio += 7) {
			const fatia = points.slice(inicio, inicio + 7);
			if (fatia.length === 0) continue;
			blocos.push({
				inicio: fatia[0].day,
				// Pico de ativos no periodo, e nao a soma: somar contaria a mesma
				// pessoa sete vezes e inventaria uma base que nao existe.
				ativosPico: Math.max(...fatia.map((p) => p.active_users)),
				refeicoes: fatia.reduce((total, p) => total + p.meals, 0),
				treinos: fatia.reduce((total, p) => total + p.workouts, 0)
			});
		}
		return blocos;
	});

	function baseOption(): EChartsOption {
		themeState.current;
		return {
			textStyle: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
			grid: { top: 34, right: 16, bottom: 30, left: 52 },
			tooltip: {
				trigger: 'axis',
				backgroundColor: themeToken('--surface'),
				borderColor: themeToken('--hairline-2'),
				textStyle: { color: themeToken('--ink'), fontSize: 12 },
				axisPointer: { type: 'shadow', shadowStyle: { color: themeToken('--accent-wash') } }
			},
			legend: {
				top: 0,
				icon: 'roundRect',
				itemWidth: 9,
				itemHeight: 9,
				textStyle: { color: themeToken('--ink-2'), fontSize: 12 }
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

	const registrosPorSemana = $derived.by<EChartsOption>(() => ({
		...baseOption(),
		xAxis: {
			type: 'category',
			data: semanas.map((s) => shortDate(s.inicio)),
			...axisStyle(),
			splitLine: { show: false }
		},
		yAxis: { type: 'value', ...axisStyle() },
		series: [
			{
				name: 'Refeicoes',
				type: 'bar',
				stack: 'registros',
				data: semanas.map((s) => s.refeicoes),
				itemStyle: { color: themeToken('--series-1') }
			},
			{
				name: 'Treinos',
				type: 'bar',
				stack: 'registros',
				data: semanas.map((s) => s.treinos),
				itemStyle: { color: themeToken('--series-2'), borderRadius: [4, 4, 0, 0] }
			}
		]
	}));

	const ativosPorSemana = $derived.by<EChartsOption>(() => ({
		...baseOption(),
		xAxis: {
			type: 'category',
			data: semanas.map((s) => shortDate(s.inicio)),
			...axisStyle(),
			splitLine: { show: false }
		},
		yAxis: { type: 'value', ...axisStyle() },
		series: [
			{
				name: 'Pico de ativos na semana',
				type: 'line',
				smooth: true,
				data: semanas.map((s) => s.ativosPico),
				symbolSize: 6,
				lineStyle: { width: 2, color: themeToken('--series-3') },
				itemStyle: { color: themeToken('--series-3') }
			}
		]
	}));

	const totalRefeicoes = $derived(semanas.reduce((total, s) => total + s.refeicoes, 0));
	const totalTreinos = $derived(semanas.reduce((total, s) => total + s.treinos, 0));
</script>

<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px">
	<div class="segmented" role="group" aria-label="Periodo do relatorio">
		{#each [30, 90, 180] as dias (dias)}
			<button
				type="button"
				aria-pressed={periodo === dias}
				onclick={() => (periodo = dias)}
			>
				{dias === 180 ? '6 meses' : `${dias} dias`}
			</button>
		{/each}
	</div>
	<span class="eyebrow">
		{semanas.length} semanas &middot; {num(totalRefeicoes)} refeicoes &middot; {num(totalTreinos)} treinos
	</span>
</div>

{#if carregando}
	<p class="mono" style="color:var(--ink-3)">carregando…</p>
{:else}
	<div class="stack">
		<article class="card">
			<div class="card-head">
				<div>
					<h2 class="card-title">Registros por semana, por tipo</h2>
					<p class="card-note">Mesma unidade nas duas barras: um registro salvo pelo usuario</p>
				</div>
			</div>
			<div class="card-body"><Chart option={registrosPorSemana} height={300} /></div>
		</article>

		<article class="card">
			<div class="card-head">
				<div>
					<h2 class="card-title">Pico de usuarios ativos por semana</h2>
					<p class="card-note">
						O maior dia de cada semana &mdash; somar os dias contaria a mesma pessoa varias vezes
					</p>
				</div>
			</div>
			<div class="card-body"><Chart option={ativosPorSemana} height={280} /></div>
		</article>

		<article class="card">
			<div class="card-head">
				<div>
					<h2 class="card-title">Tabela agregada por semana</h2>
					<p class="card-note">Os mesmos numeros dos graficos acima, em texto</p>
				</div>
			</div>
			<div class="table-wrap" style="border-bottom:0">
				<table>
					<caption class="sr-only">Agregados semanais de uso</caption>
					<thead>
						<tr>
							<th scope="col">Semana de</th>
							<th class="num" scope="col">Pico de ativos</th>
							<th class="num" scope="col">Refeicoes</th>
							<th class="num" scope="col">Treinos</th>
							<th class="num" scope="col">Registros</th>
						</tr>
					</thead>
					<tbody>
						{#each [...semanas].reverse() as semana (semana.inicio)}
							<tr>
								<td class="mono" style="font-size:12.5px">{shortDate(semana.inicio)}</td>
								<td class="num">{num(semana.ativosPico)}</td>
								<td class="num">{num(semana.refeicoes)}</td>
								<td class="num">{num(semana.treinos)}</td>
								<td class="num">{num(semana.refeicoes + semana.treinos)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</article>
	</div>
{/if}
