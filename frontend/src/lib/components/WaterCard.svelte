<script lang="ts">
	import { api, localDayParams, type WaterDay } from '$lib/api';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let data = $state<WaterDay | null>(null);
	let busy = $state(false);
	let confirmingUndo = $state(false);

	const nf = new Intl.NumberFormat(getLocale());
	// Cada quick-add tem um icone: copo pela metade, copo cheio e garrafa.
	const QUICK_ADDS: { ml: number; icon: 'half' | 'full' | 'bottle' }[] = [
		{ ml: 250, icon: 'half' },
		{ ml: 500, icon: 'full' },
		{ ml: 1000, icon: 'bottle' }
	];

	// Anel de progresso (SVG). r=52 -> circunferencia ~326.7.
	const RADIUS = 52;
	const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

	const pct = $derived(data ? Math.min(1, data.goal_ml > 0 ? data.total_ml / data.goal_ml : 0) : 0);
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
			confirmingUndo = false;
			await load();
			showToast(m.toast_deleted());
		} finally {
			busy = false;
		}
	}

	function label(ml: number): string {
		return ml >= 1000 ? `${nf.format(ml / 1000)} L` : `${ml} ml`;
	}

	// carrega o consumo do dia ao montar o card
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
						onclick={() => (confirmingUndo = true)}
						disabled={busy}
						class="mt-2 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600 active:bg-slate-200 disabled:opacity-50"
					>
						<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 14l-4-4 4-4M5 10h11a4 4 0 010 8h-1" stroke-linecap="round" stroke-linejoin="round" /></svg>
						{m.undo_last()}
					</button>
				{/if}
			{/if}
		</div>
	</div>

	{#if confirmingUndo}
		<div class="mt-4 rounded-2xl bg-slate-50 p-3">
			<p class="text-sm font-medium text-slate-700">{m.water_undo_confirm()}</p>
			<div class="mt-2 flex gap-2">
				<button
					type="button"
					onclick={() => (confirmingUndo = false)}
					class="h-11 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
				>
					{m.cancel()}
				</button>
				<button
					type="button"
					disabled={busy}
					onclick={undoLast}
					class="h-11 flex-1 rounded-2xl bg-slate-800 font-semibold text-white active:bg-slate-700 disabled:opacity-50"
				>
					{m.undo_last()}
				</button>
			</div>
		</div>
	{:else}
		<div class="mt-5 grid grid-cols-3 gap-2">
			{#each QUICK_ADDS as { ml, icon } (ml)}
				<button
					type="button"
					onclick={() => add(ml)}
					disabled={busy}
					class="flex min-h-20 flex-col items-center justify-center gap-1 rounded-2xl border-2 border-sky-100 bg-sky-50 font-bold text-sky-700 active:bg-sky-100 disabled:opacity-50"
				>
					{#if icon === 'half'}
						<!-- copo pela metade -->
						<svg viewBox="0 0 24 24" class="h-7 w-7">
							<path d="M6 4h12l-1.2 15.1a2 2 0 01-2 1.9H9.2a2 2 0 01-2-1.9L6 4z" fill="none" stroke="currentColor" stroke-width="1.6" />
							<path d="M7.15 12h9.7l-.65 7.1a2 2 0 01-2 1.9H9.8a2 2 0 01-2-1.9L7.15 12z" fill="currentColor" opacity="0.5" />
						</svg>
					{:else if icon === 'full'}
						<!-- copo cheio -->
						<svg viewBox="0 0 24 24" class="h-7 w-7">
							<path d="M6 4h12l-1.2 15.1a2 2 0 01-2 1.9H9.2a2 2 0 01-2-1.9L6 4z" fill="none" stroke="currentColor" stroke-width="1.6" />
							<path d="M6.55 6.5h10.9l-1 12.6a2 2 0 01-2 1.9H9.55a2 2 0 01-2-1.9L6.55 6.5z" fill="currentColor" opacity="0.5" />
						</svg>
					{:else}
						<!-- garrafa -->
						<svg viewBox="0 0 24 24" class="h-7 w-7">
							<path d="M10 2h4v2.3l1.1 1.7c.6.9.9 1.9.9 2.9V19a2 2 0 01-2 2h-4a2 2 0 01-2-2V8.9c0-1 .3-2 .9-2.9L10 4.3V2z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
							<path d="M8 12.5h8V19a2 2 0 01-2 2h-4a2 2 0 01-2-2v-6.5z" fill="currentColor" opacity="0.5" />
							<path d="M10 2.5h4v1.6h-4z" fill="currentColor" />
						</svg>
					{/if}
					<span class="text-sm">+{label(ml)}</span>
				</button>
			{/each}
		</div>
	{/if}
</section>
