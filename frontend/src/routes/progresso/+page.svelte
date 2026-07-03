<script lang="ts">
	import { api, localDay, type WeekSummary, type WeightHistory } from '$lib/api';
	import Stepper from '$lib/components/Stepper.svelte';
	import WeightChart from '$lib/components/WeightChart.svelte';
	import { bootstrap, session } from '$lib/session.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let history = $state<WeightHistory | null>(null);
	let week = $state<WeekSummary | null>(null);
	let newWeight = $state(session.profile?.weight_kg ?? 75);
	let busy = $state(false);
	let adding = $state(false);

	const dietOn = $derived(session.profile?.diet_enabled ?? false);
	const nf = new Intl.NumberFormat(getLocale());
	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });

	async function load(): Promise<void> {
		history = await api.getWeightHistory();
		if (history.current_kg !== null) newWeight = history.current_kg;
		week = await api.getWeekSummary(localDay(), new Date().getTimezoneOffset());
	}

	async function save(): Promise<void> {
		busy = true;
		try {
			await api.addWeight(newWeight);
			await load();
			await bootstrap(); // metas dependem do peso mais recente
			adding = false;
		} finally {
			busy = false;
		}
	}

	async function remove(id: number): Promise<void> {
		await api.deleteWeight(id);
		await load();
		await bootstrap();
	}

	$effect(() => {
		load();
	});

	const reversedLogs = $derived(history ? [...history.logs].reverse() : []);
</script>

<h1 class="mb-4 text-2xl font-bold">{m.tab_progress()}</h1>

{#if week}
	<section class="mb-4 rounded-3xl bg-white p-5 shadow-sm">
		<p class="mb-3 text-sm font-bold text-slate-400 uppercase">{m.this_week()}</p>
		<div class="grid grid-cols-2 gap-3">
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">{week.workouts}</p>
				<p class="text-xs font-semibold text-slate-500">{m.workouts_label()}</p>
			</div>
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">
					{nf.format(week.total_volume_kg)}<span class="text-sm font-medium text-slate-400"> kg</span>
				</p>
				<p class="text-xs font-semibold text-slate-500">{m.volume_label()}</p>
			</div>
			{#if dietOn}
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{week.days_logged_diet > 0 ? nf.format(week.avg_kcal) : '—'}
						{#if week.days_logged_diet > 0}<span class="text-sm font-medium text-slate-400"> kcal</span>{/if}
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.avg_calories()}</p>
				</div>
			{/if}
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">
					{week.days_with_water > 0 ? nf.format(week.avg_water_ml / 1000) : '—'}
					{#if week.days_with_water > 0}<span class="text-sm font-medium text-slate-400"> L</span>{/if}
				</p>
				<p class="text-xs font-semibold text-slate-500">{m.avg_water()}</p>
			</div>
		</div>
	</section>
{/if}

{#if history}
	<section class="rounded-3xl bg-white p-6 shadow-sm">
		<div class="flex items-end justify-between">
			<div>
				<p class="text-sm font-semibold text-slate-500">{m.current_weight()}</p>
				<p class="mt-1 text-4xl font-black tracking-tight">
					{history.current_kg !== null ? nf.format(history.current_kg) : '—'}
					<span class="text-lg font-semibold text-slate-400">kg</span>
				</p>
			</div>
			{#if history.delta_kg !== null && history.delta_kg !== 0}
				{@const down = history.delta_kg < 0}
				<div
					class="rounded-full px-3 py-1 text-sm font-bold {down
						? 'bg-emerald-50 text-emerald-700'
						: 'bg-amber-50 text-amber-700'}"
				>
					{down ? '▼' : '▲'}
					{nf.format(Math.abs(history.delta_kg))} kg
				</div>
			{/if}
		</div>

		{#if history.logs.length >= 2}
			<div class="mt-4">
				<WeightChart logs={history.logs} />
			</div>
		{:else}
			<p class="mt-4 text-sm text-slate-400">{m.weight_need_more()}</p>
		{/if}
	</section>

	{#if adding}
		<section class="mt-3 rounded-3xl bg-white p-6 shadow-sm">
			<p class="mb-3 font-semibold text-slate-600">{m.new_weight()}</p>
			<Stepper bind:value={newWeight} min={30} max={300} step={0.1} decimals={1} unit="kg" />
			<div class="mt-5 flex gap-3">
				<button
					type="button"
					onclick={() => (adding = false)}
					class="h-14 flex-1 rounded-2xl border-2 border-slate-200 font-bold text-slate-700 active:bg-slate-100"
				>
					{m.cancel()}
				</button>
				<button
					type="button"
					disabled={busy}
					onclick={save}
					class="h-14 flex-[2] rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-50"
				>
					{m.save()}
				</button>
			</div>
		</section>
	{:else}
		<button
			type="button"
			onclick={() => (adding = true)}
			class="mt-3 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700"
		>
			{m.register_weight()}
		</button>
	{/if}

	{#if reversedLogs.length > 0}
		<section class="mt-3 overflow-hidden rounded-3xl bg-white shadow-sm">
			{#each reversedLogs as log, i (log.id)}
				<div
					class="flex items-center justify-between px-5 py-3.5 {i > 0
						? 'border-t border-slate-100'
						: ''}"
				>
					<div>
						<span class="font-bold text-slate-900">{nf.format(log.weight_kg)} kg</span>
						{#if log.source === 'ble'}
							<span class="ml-2 rounded bg-sky-50 px-1.5 py-0.5 text-xs font-semibold text-sky-600"
								>Bluetooth</span
							>
						{/if}
					</div>
					<div class="flex items-center gap-3">
						<span class="text-sm text-slate-400">{df.format(new Date(log.logged_at))}</span>
						<button
							type="button"
							aria-label={m.delete_account()}
							onclick={() => remove(log.id)}
							class="text-slate-300 active:text-red-500"
						>
							<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" />
							</svg>
						</button>
					</div>
				</div>
			{/each}
		</section>
	{/if}
{:else}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{/if}
