<script lang="ts">
	import { api, localDayParams, type WaterDay } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let data = $state<WaterDay | null>(null);
	let busy = $state(false);

	const nf = new Intl.NumberFormat(getLocale());
	const QUICK_ADDS = [250, 500, 1000];

	// Anel de progresso (SVG). r=52 → circunferência ~326.7.
	const RADIUS = 52;
	const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

	const pct = $derived(
		data ? Math.min(1, data.goal_ml > 0 ? data.total_ml / data.goal_ml : 0) : 0
	);
	const dashOffset = $derived(CIRCUMFERENCE * (1 - pct));

	async function load(): Promise<void> {
		const { day, tzOffset } = localDayParams();
		data = await api.getWaterDay(day, tzOffset);
	}

	async function add(amount: number): Promise<void> {
		if (busy || !data) return;
		busy = true;
		// otimista: soma na hora, confirma com o servidor depois
		data = { ...data, total_ml: data.total_ml + amount };
		try {
			await api.addWater(amount);
			await load();
		} finally {
			busy = false;
		}
	}

	async function undoLast(): Promise<void> {
		if (busy || !data || data.logs.length === 0) return;
		busy = true;
		const last = data.logs[data.logs.length - 1];
		try {
			await api.deleteWater(last.id);
			await load();
		} finally {
			busy = false;
		}
	}

	function label(ml: number): string {
		return ml >= 1000 ? `${nf.format(ml / 1000)} L` : `${ml} ml`;
	}

	$effect(() => {
		load();
	});
</script>

<section class="rounded-3xl bg-white p-6 shadow-sm">
	<div class="flex items-center gap-5">
		<div class="relative shrink-0">
			<svg viewBox="0 0 120 120" class="h-28 w-28 -rotate-90">
				<circle cx="60" cy="60" r={RADIUS} fill="none" stroke="#e2e8f0" stroke-width="10" />
				<circle
					cx="60"
					cy="60"
					r={RADIUS}
					fill="none"
					stroke="#0ea5e9"
					stroke-width="10"
					stroke-linecap="round"
					stroke-dasharray={CIRCUMFERENCE}
					stroke-dashoffset={dashOffset}
					class="transition-[stroke-dashoffset] duration-500"
				/>
			</svg>
			<div class="absolute inset-0 flex flex-col items-center justify-center">
				<span class="text-2xl font-black text-slate-900">{Math.round(pct * 100)}%</span>
			</div>
		</div>
		<div class="min-w-0 flex-1">
			<p class="text-sm font-semibold text-slate-500">{m.water_title()}</p>
			{#if data}
				<p class="mt-0.5 text-2xl font-bold text-slate-900">
					{nf.format(data.total_ml / 1000)}
					<span class="text-base font-medium text-slate-400">
						/ {nf.format(data.goal_ml / 1000)} L
					</span>
				</p>
				{#if data.logs.length > 0}
					<button
						type="button"
						onclick={undoLast}
						disabled={busy}
						class="mt-1 text-sm font-semibold text-slate-400 active:text-slate-600 disabled:opacity-50"
					>
						{m.undo_last()}
					</button>
				{/if}
			{/if}
		</div>
	</div>

	<div class="mt-5 grid grid-cols-3 gap-2">
		{#each QUICK_ADDS as amount (amount)}
			<button
				type="button"
				onclick={() => add(amount)}
				disabled={busy}
				class="flex min-h-16 flex-col items-center justify-center gap-0.5 rounded-2xl border-2 border-sky-100 bg-sky-50 font-bold text-sky-700 active:bg-sky-100 disabled:opacity-50"
			>
				<span class="text-lg">+{label(amount)}</span>
			</button>
		{/each}
	</div>
</section>
