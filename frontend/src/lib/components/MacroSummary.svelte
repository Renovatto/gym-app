<script lang="ts">
	import type { Macros } from '$lib/api';
	import {
		carbsGoalStatus,
		fatGoalStatus,
		kcalGoalStatus,
		proteinGoalStatus,
		worstGoalStatus,
		type GoalStatus
	} from '$lib/macros';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	// addHref: quando informado, mostra um botao "+" no canto superior direito
	// (usado na tela Hoje para levar a adicionar alimento).
	let {
		totals,
		goals,
		addHref
	}: { totals: Macros; goals: Macros | null; addHref?: string } = $props();

	const nf = new Intl.NumberFormat(getLocale());

	const RADIUS = 54;
	const CIRC = 2 * Math.PI * RADIUS;

	const kcalPct = $derived(
		goals && goals.kcal > 0 ? Math.min(1, totals.kcal / goals.kcal) : 0
	);
	const remaining = $derived(goals ? Math.max(0, Math.round(goals.kcal - totals.kcal)) : null);
	const over = $derived(goals ? totals.kcal > goals.kcal : false);

	// Cores do farol (verde/amarelo/vermelho) nos mesmos tons do resto do app.
	const STATUS_COLOR: Record<GoalStatus, string> = {
		ok: '#059669',
		near: '#d97706',
		over: '#dc2626'
	};
	const STATUS_TEXT: Record<GoalStatus, string> = {
		ok: 'text-slate-500',
		near: 'text-amber-600',
		over: 'text-red-600'
	};
	const STATUS_CHIP: Record<GoalStatus, string> = {
		ok: '',
		near: 'bg-amber-100 text-amber-700',
		over: 'bg-red-100 text-red-600'
	};

	const kcalStatus = $derived(goals ? kcalGoalStatus(totals.kcal, goals.kcal) : 'ok');
	const fatStatus = $derived(goals ? fatGoalStatus(totals.fat_g, goals.fat_g) : 'ok');

	// Cor do anel: o pior entre calorias e gordura. A gordura tem voz propria aqui
	// porque e o macro que mais empurra o excedente calorico - estourar gordura com
	// as calorias ainda dentro da tolerancia ja merece o vermelho.
	const ringStatus = $derived(worstGoalStatus(kcalStatus, fatStatus === 'over' ? 'over' : 'ok'));

	// barras de macro: proteína (emerald), carbo (amber), gordura (violet)
	const macros = $derived([
		{
			label: m.protein(),
			value: totals.protein_g,
			goal: goals?.protein_g ?? 0,
			color: '#059669',
			status: goals ? proteinGoalStatus(totals.protein_g, goals.protein_g) : ('ok' as GoalStatus)
		},
		{
			label: m.carbs(),
			value: totals.carbs_g,
			goal: goals?.carbs_g ?? 0,
			color: '#d97706',
			status: goals ? carbsGoalStatus(totals.carbs_g, goals.carbs_g) : ('ok' as GoalStatus)
		},
		{
			label: m.fat(),
			value: totals.fat_g,
			goal: goals?.fat_g ?? 0,
			color: '#7c3aed',
			status: goals ? fatStatus : ('ok' as GoalStatus)
		}
	]);

	// Quando o macro estoura, a barra estica a escala em vez de travar em 100% - assim
	// o excedente fica visivel e um traco marca onde ficou a meta. Ex.: 120% da meta
	// vira uma barra cheia com a marca da meta a 83% (= 1 / 1.2) da largura.
	function barGeometry(value: number, goal: number): { fillPct: number; goalPct: number } {
		if (goal <= 0) return { fillPct: 0, goalPct: 100 };
		const ratio = value / goal;
		const scale = Math.max(1, ratio);
		return { fillPct: (ratio / scale) * 100, goalPct: (1 / scale) * 100 };
	}
</script>

<section class="relative rounded-3xl bg-white p-6 shadow-sm">
	{#if addHref}
		<a
			href={addHref}
			aria-label={m.add_food()}
			title={m.add_food()}
			class="absolute top-4 right-4 grid h-11 w-11 place-items-center rounded-2xl bg-emerald-600 text-white shadow-sm active:bg-emerald-700"
		>
			<svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14" stroke-linecap="round" /></svg>
		</a>
	{/if}
	<div class="flex items-center gap-5">
		<div class="relative shrink-0">
			<svg viewBox="0 0 128 128" class="h-32 w-32 -rotate-90">
				<circle cx="64" cy="64" r={RADIUS} fill="none" stroke="#e2e8f0" stroke-width="11" />
				<circle
					cx="64"
					cy="64"
					r={RADIUS}
					fill="none"
					stroke={STATUS_COLOR[ringStatus]}
					stroke-width="11"
					stroke-linecap="round"
					stroke-dasharray={CIRC}
					stroke-dashoffset={CIRC * (1 - kcalPct)}
					class="transition-[stroke-dashoffset] duration-500"
				/>
			</svg>
			<div class="absolute inset-0 flex flex-col items-center justify-center">
				<span class="text-3xl font-black text-slate-900">{nf.format(Math.round(totals.kcal))}</span>
				<span class="text-xs font-medium text-slate-400">kcal</span>
			</div>
		</div>
		<div class="min-w-0 flex-1">
			{#if goals}
				{#if over}
					<p class="text-sm font-semibold {STATUS_TEXT[ringStatus]}">
						{ringStatus === 'near' ? m.near_goal_limit() : m.over_goal()}
					</p>
					<p class="text-2xl font-bold text-slate-900">
						+{nf.format(Math.round(totals.kcal - goals.kcal))}
						<span class="text-sm font-medium text-slate-400">kcal</span>
					</p>
				{:else}
					<p class="text-sm font-semibold text-slate-500">{m.remaining()}</p>
					<p class="text-2xl font-bold text-slate-900">
						{nf.format(remaining ?? 0)}
						<span class="text-sm font-medium text-slate-400">kcal</span>
					</p>
				{/if}
				<p class="mt-0.5 text-xs text-slate-400">
					{m.goal_label()}: {nf.format(Math.round(goals.kcal))} kcal
				</p>
			{:else}
				<p class="text-sm text-slate-500">{m.no_goal_yet()}</p>
			{/if}
		</div>
	</div>

	<div class="mt-5 space-y-3 border-t border-slate-100 pt-4">
		{#each macros as macro (macro.label)}
			{@const bar = barGeometry(macro.value, macro.goal)}
			<div>
				<div class="mb-1 flex items-baseline justify-between gap-2 text-sm">
					<span class="font-semibold text-slate-600">{macro.label}</span>
					<span class="flex items-center gap-2">
						{#if macro.status !== 'ok'}
							<span class="rounded-md px-1.5 py-0.5 text-xs font-semibold tabular-nums {STATUS_CHIP[macro.status]}">
								+{nf.format(Math.round(macro.value - macro.goal))} g
							</span>
						{/if}
						<span class="text-slate-500">
							{nf.format(Math.round(macro.value))}{#if goals}<span class="text-slate-400"> / {nf.format(Math.round(macro.goal))}</span>{/if} g
						</span>
					</span>
				</div>
				<div class="relative h-2 overflow-hidden rounded-full bg-slate-100">
					<div
						class="h-full rounded-full transition-all duration-500"
						style="width: {bar.fillPct}%; background-color: {macro.status === 'ok'
							? macro.color
							: STATUS_COLOR[macro.status]}"
					></div>
					{#if macro.status !== 'ok'}
						<!-- marca da meta, que desliza pra esquerda conforme a barra estoura -->
						<div
							class="absolute inset-y-0 w-0.5 bg-white/80 transition-all duration-500"
							style="left: {bar.goalPct}%"
						></div>
					{/if}
				</div>
			</div>
		{/each}
	</div>
</section>
