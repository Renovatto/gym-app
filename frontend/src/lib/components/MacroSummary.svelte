<script lang="ts">
	import type { Macros } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let { totals, goals }: { totals: Macros; goals: Macros | null } = $props();

	const nf = new Intl.NumberFormat(getLocale());

	const RADIUS = 54;
	const CIRC = 2 * Math.PI * RADIUS;

	const kcalPct = $derived(
		goals && goals.kcal > 0 ? Math.min(1, totals.kcal / goals.kcal) : 0
	);
	const remaining = $derived(goals ? Math.max(0, Math.round(goals.kcal - totals.kcal)) : null);
	const over = $derived(goals ? totals.kcal > goals.kcal : false);

	// barras de macro: proteína (emerald), carbo (amber), gordura (violet)
	const macros = $derived([
		{ label: m.protein(), value: totals.protein_g, goal: goals?.protein_g ?? 0, color: '#059669' },
		{ label: m.carbs(), value: totals.carbs_g, goal: goals?.carbs_g ?? 0, color: '#d97706' },
		{ label: m.fat(), value: totals.fat_g, goal: goals?.fat_g ?? 0, color: '#7c3aed' }
	]);

	function pct(value: number, goal: number): number {
		return goal > 0 ? Math.min(100, (value / goal) * 100) : 0;
	}
</script>

<section class="rounded-3xl bg-white p-6 shadow-sm">
	<div class="flex items-center gap-5">
		<div class="relative shrink-0">
			<svg viewBox="0 0 128 128" class="h-32 w-32 -rotate-90">
				<circle cx="64" cy="64" r={RADIUS} fill="none" stroke="#e2e8f0" stroke-width="11" />
				<circle
					cx="64"
					cy="64"
					r={RADIUS}
					fill="none"
					stroke={over ? '#dc2626' : '#059669'}
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
					<p class="text-sm font-semibold text-red-600">{m.over_goal()}</p>
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
			<div>
				<div class="mb-1 flex justify-between text-sm">
					<span class="font-semibold text-slate-600">{macro.label}</span>
					<span class="text-slate-500">
						{nf.format(Math.round(macro.value))}{#if goals}<span class="text-slate-400"> / {nf.format(Math.round(macro.goal))}</span>{/if} g
					</span>
				</div>
				<div class="h-2 overflow-hidden rounded-full bg-slate-100">
					<div
						class="h-full rounded-full transition-all duration-500"
						style="width: {pct(macro.value, macro.goal)}%; background-color: {macro.color}"
					></div>
				</div>
			</div>
		{/each}
	</div>
</section>
