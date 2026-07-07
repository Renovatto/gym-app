<script lang="ts">
	import {
		api,
		localDay,
		type AchievementsResult,
		type AdaptiveTdee,
		type BodyComposition,
		type WeekSummary,
		type WeighInInput,
		type WeightHistory,
		type WeightLog
	} from '$lib/api';
	import Stepper from '$lib/components/Stepper.svelte';
	import WeightChart from '$lib/components/WeightChart.svelte';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { bootstrap, session } from '$lib/session.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let history = $state<WeightHistory | null>(null);
	let week = $state<WeekSummary | null>(null);
	let adaptive = $state<AdaptiveTdee | null>(null);
	let achievements = $state<AchievementsResult | null>(null);
	let newWeight = $state(session.profile?.weight_kg ?? 75);
	let busy = $state(false);
	let adding = $state(false);

	// Campos opcionais da balanca de bioimpedancia. A ordem aqui e a ordem na tela.
	// O usuario le esses valores na propria balanca e digita; por isso sao inputs de
	// texto (mais rapido para valor exato) e nao steppers.
	const bodyCompositionInputs: { key: keyof BodyComposition; label: string; unit: string }[] = [
		{ key: 'fat_percentage', label: m.bc_fat_pct(), unit: '%' },
		{ key: 'fat_mass_kg', label: m.bc_fat_mass(), unit: 'kg' },
		{ key: 'visceral_fat_index', label: m.bc_visceral(), unit: '' },
		{ key: 'muscle_percentage', label: m.bc_muscle_pct(), unit: '%' },
		{ key: 'muscle_mass_kg', label: m.bc_muscle_mass(), unit: 'kg' },
		{ key: 'skeletal_muscle_percentage', label: m.bc_skeletal_pct(), unit: '%' },
		{ key: 'skeletal_muscle_kg', label: m.bc_skeletal_mass(), unit: 'kg' },
		{ key: 'water_percentage', label: m.bc_water_pct(), unit: '%' },
		{ key: 'water_mass_kg', label: m.bc_water_mass(), unit: 'kg' },
		{ key: 'scale_bmr_kcal', label: m.bc_scale_bmr(), unit: 'kcal' }
	];
	// valor digitado (texto) de cada campo da balanca, indexado pela chave
	let scaleValues = $state<Record<string, string>>({});
	let showScaleFields = $state(false);

	const dietOn = $derived(session.profile?.diet_enabled ?? false);
	const nf = new Intl.NumberFormat(getLocale());
	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });

	async function load(): Promise<void> {
		const tzOffset = new Date().getTimezoneOffset();
		history = await api.getWeightHistory();
		if (history.current_kg !== null) newWeight = history.current_kg;
		week = await api.getWeekSummary(localDay(), tzOffset);
		achievements = await api.getAchievements(localDay(), tzOffset);
		// TDEE adaptativo so faz sentido com o modulo de dieta (precisa da ingestao)
		if (dietOn) adaptive = await api.getAdaptiveTdee(localDay(), tzOffset);
	}

	// Mensagem do TDEE adaptativo: texto traduzido + tom (cor) conforme o ritmo real.
	const adaptiveMessage = $derived.by(() => {
		if (!adaptive || !adaptive.has_enough_data) return null;
		const byCode: Record<string, { text: string; tone: 'good' | 'warn' | 'info' }> = {
			ON_TRACK: { text: m.adaptive_on_track(), tone: 'good' },
			TOO_SLOW: { text: m.adaptive_too_slow(), tone: 'warn' },
			STALLED: { text: m.adaptive_stalled(), tone: 'warn' },
			TOO_FAST: { text: m.adaptive_too_fast(), tone: 'info' },
			ESTIMATE_READY: { text: m.adaptive_estimate_ready(), tone: 'info' }
		};
		return byCode[adaptive.message_code] ?? byCode.ESTIMATE_READY;
	});

	// Monta o payload da pesagem: peso obrigatorio + campos da balanca preenchidos.
	// Campos vazios ou invalidos sao ignorados (ficam nulos no banco).
	function buildWeighIn(): WeighInInput {
		const weighIn: WeighInInput = { weight_kg: newWeight };
		for (const field of bodyCompositionInputs) {
			const raw = (scaleValues[field.key] ?? '').replace(',', '.').trim();
			if (raw === '') continue;
			const parsed = Number(raw);
			if (!Number.isNaN(parsed)) weighIn[field.key] = parsed;
		}
		return weighIn;
	}

	async function save(): Promise<void> {
		busy = true;
		try {
			await api.addWeight(buildWeighIn());
			scaleValues = {};
			showScaleFields = false;
			await load();
			await bootstrap(); // metas dependem do peso mais recente
			adding = false;
			showToast(m.weigh_in_saved());
		} finally {
			busy = false;
		}
	}

	// Detalhes de uma pesagem (modal ao clicar no item do historico).
	let selectedLog = $state<WeightLog | null>(null);
	let confirmingDeleteWeight = $state(false);

	function openWeightDetail(log: WeightLog): void {
		selectedLog = log;
		confirmingDeleteWeight = false;
	}

	async function deleteSelectedWeight(): Promise<void> {
		if (!selectedLog) return;
		await api.deleteWeight(selectedLog.id);
		selectedLog = null;
		confirmingDeleteWeight = false;
		await load();
		await bootstrap();
		showToast(m.weigh_in_deleted());
	}

	$effect(() => {
		load();
	});

	// Vindo do atalho "Pesar" da tela inicial (/progresso?novo=1): ja abre o formulario.
	onMount(() => {
		if (page.url.searchParams.get('novo')) adding = true;
	});

	// Historico do mais recente para o mais antigo, com a variacao (peso e gordura)
	// em relacao a pesagem anterior.
	const reversedLogs = $derived.by(() => {
		if (!history) return [];
		const desc = [...history.logs].reverse();
		return desc.map((log, i) => {
			const previous = desc[i + 1]; // proxima na lista = anterior no tempo
			const delta = previous ? Math.round((log.weight_kg - previous.weight_kg) * 10) / 10 : null;
			const fatDelta =
				previous && log.fat_percentage !== null && previous.fat_percentage !== null
					? Math.round((log.fat_percentage - previous.fat_percentage) * 10) / 10
					: null;
			return { log, delta, fatDelta };
		});
	});

	// Formata hora local (HH:MM) a partir do timestamp da pesagem.
	function formatClock(iso: string): string {
		return new Date(iso).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' });
	}

	// Campos de composicao presentes na pesagem selecionada (para o modal de detalhes).
	const selectedBodyComposition = $derived.by(() => {
		if (!selectedLog) return [];
		return bodyCompositionInputs
			.map((field) => ({ label: field.label, unit: field.unit, value: selectedLog![field.key] }))
			.filter((row) => row.value !== null && row.value !== undefined);
	});
</script>

<h1 class="mb-4 text-2xl font-bold">{m.tab_progress()}</h1>

{#if achievements}
	<a
		href="/conquistas"
		class="mb-4 flex items-center justify-between rounded-3xl bg-white p-4 shadow-sm active:bg-slate-50"
	>
		<div class="flex items-center gap-3">
			<span class="text-3xl">🔥</span>
			<div>
				<p class="text-lg font-black text-slate-900">
					{achievements.weekly_streak}
					<span class="text-sm font-semibold text-slate-500">{m.weeks_streak()}</span>
				</p>
				<p class="text-xs text-slate-500">{m.see_achievements()}</p>
			</div>
		</div>
		<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
	</a>
{/if}

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

{#if dietOn && adaptive}
	<section class="mb-4 rounded-3xl bg-white p-5 shadow-sm">
		<p class="mb-1 text-sm font-bold text-slate-400 uppercase">{m.adaptive_title()}</p>
		{#if !adaptive.has_enough_data}
			<p class="text-sm text-slate-500">{m.adaptive_need_data()}</p>
			<p class="mt-2 text-xs text-slate-400">
				{m.adaptive_progress_label()}: {adaptive.days_logged} {m.adaptive_days_logged()} ·
				{adaptive.span_days} {m.adaptive_days_span()}
			</p>
		{:else}
			<!-- manutencao real estimada vs estimativa da formula -->
			<div class="grid grid-cols-2 gap-3">
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{nf.format(adaptive.estimated_maintenance_kcal ?? 0)}<span class="text-sm font-medium text-slate-400"> kcal</span>
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.adaptive_real_maintenance()}</p>
				</div>
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{adaptive.weekly_change_kg > 0 ? '+' : ''}{nf.format(adaptive.weekly_change_kg)}<span class="text-sm font-medium text-slate-400"> kg</span>
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.adaptive_weekly_change()}</p>
				</div>
			</div>

			<!-- comparacao de metas: atual (formula) vs sugerida (dados reais) -->
			<div class="mt-3 flex items-center justify-between rounded-2xl border-2 border-slate-100 px-4 py-3">
				<div>
					<p class="text-xs font-semibold text-slate-400">{m.adaptive_current_target()}</p>
					<p class="text-lg font-bold text-slate-500">{nf.format(adaptive.current_target_kcal)}</p>
				</div>
				<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
				<div class="text-right">
					<p class="text-xs font-semibold text-emerald-600">{m.adaptive_suggested_target()}</p>
					<p class="text-lg font-black text-emerald-700">{nf.format(adaptive.suggested_target_kcal ?? 0)}</p>
				</div>
			</div>

			{#if adaptiveMessage}
				<div
					class="mt-3 rounded-2xl px-4 py-3 text-sm font-semibold
						{adaptiveMessage.tone === 'good'
						? 'bg-emerald-50 text-emerald-800'
						: adaptiveMessage.tone === 'warn'
							? 'bg-amber-50 text-amber-800'
							: 'bg-sky-50 text-sky-800'}"
				>
					{adaptiveMessage.text}
				</div>
			{/if}
			<p class="mt-2 text-xs text-slate-400">{m.adaptive_footnote()}</p>
		{/if}
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

	{#if history.latest_body_composition}
		{@const bc = history.latest_body_composition}
		<section class="mt-3 rounded-3xl bg-white p-5 shadow-sm">
			<p class="mb-3 text-sm font-bold text-slate-400 uppercase">{m.body_composition()}</p>
			<div class="grid grid-cols-2 gap-3">
				{#if bc.fat_percentage !== null}
					<div class="rounded-2xl bg-slate-50 p-3">
						<p class="text-2xl font-black text-slate-900">{nf.format(bc.fat_percentage)}<span class="text-sm font-medium text-slate-400"> %</span></p>
						<p class="text-xs font-semibold text-slate-500">{m.bc_fat_pct()}</p>
					</div>
				{/if}
				{#if bc.visceral_fat_index !== null}
					<div class="rounded-2xl bg-slate-50 p-3">
						<p class="text-2xl font-black text-slate-900">{nf.format(bc.visceral_fat_index)}</p>
						<p class="text-xs font-semibold text-slate-500">{m.bc_visceral()}</p>
					</div>
				{/if}
				{#if bc.muscle_mass_kg !== null}
					<div class="rounded-2xl bg-slate-50 p-3">
						<p class="text-2xl font-black text-slate-900">{nf.format(bc.muscle_mass_kg)}<span class="text-sm font-medium text-slate-400"> kg</span></p>
						<p class="text-xs font-semibold text-slate-500">{m.bc_muscle_mass()}</p>
					</div>
				{/if}
				{#if bc.water_percentage !== null}
					<div class="rounded-2xl bg-slate-50 p-3">
						<p class="text-2xl font-black text-slate-900">{nf.format(bc.water_percentage)}<span class="text-sm font-medium text-slate-400"> %</span></p>
						<p class="text-xs font-semibold text-slate-500">{m.bc_water_pct()}</p>
					</div>
				{/if}
			</div>
			<p class="mt-3 text-xs text-slate-400">{m.bc_measured_on()} {df.format(new Date(bc.logged_at))}</p>
		</section>
	{/if}

	<button
		type="button"
		onclick={() => (adding = true)}
		class="mt-3 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700"
	>
		{m.register_weight()}
	</button>

	{#if reversedLogs.length > 0}
		<section class="mt-3 overflow-hidden rounded-3xl bg-white shadow-sm">
			<!-- cabecalho de colunas -->
			<div class="flex items-center gap-3 border-b border-slate-100 px-5 py-2.5">
				<span class="w-20 shrink-0 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.col_date()}</span>
				<span class="flex-1 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.col_weight()}</span>
				<span class="w-16 text-right text-xs font-bold tracking-wide text-slate-400 uppercase">{m.col_fat()}</span>
				<span class="w-4 shrink-0"></span>
			</div>

			{#each reversedLogs as { log, delta, fatDelta } (log.id)}
				<button
					type="button"
					onclick={() => openWeightDetail(log)}
					class="flex w-full items-center gap-3 border-l-4 border-t border-slate-100 px-5 py-3 text-left active:bg-slate-50
						{delta === null || delta === 0
						? 'border-l-transparent'
						: delta < 0
							? 'border-l-emerald-400'
							: 'border-l-amber-400'}"
				>
					<!-- data + hora -->
					<div class="w-20 shrink-0">
						<p class="text-sm font-bold text-slate-700">{df.format(new Date(log.logged_at))}</p>
						<p class="text-xs text-slate-400">{formatClock(log.logged_at)}</p>
					</div>

					<!-- peso + variacao -->
					<div class="flex-1">
						<p class="font-bold text-slate-900">
							{nf.format(log.weight_kg)}<span class="ml-0.5 text-xs font-medium text-slate-400">kg</span>
						</p>
						{#if delta !== null && delta !== 0}
							<p class="text-xs font-semibold {delta < 0 ? 'text-emerald-600' : 'text-amber-600'}">
								{delta < 0 ? '▼' : '▲'} {nf.format(Math.abs(delta))}
							</p>
						{/if}
					</div>

					<!-- gordura % + variacao (quando ha dado da balanca) -->
					<div class="w-16 text-right">
						{#if log.fat_percentage !== null}
							<p class="font-bold text-slate-900">
								{nf.format(log.fat_percentage)}<span class="ml-0.5 text-xs font-medium text-slate-400">%</span>
							</p>
							{#if fatDelta !== null && fatDelta !== 0}
								<p class="text-xs font-semibold {fatDelta < 0 ? 'text-emerald-600' : 'text-amber-600'}">
									{fatDelta < 0 ? '▼' : '▲'} {nf.format(Math.abs(fatDelta))}
								</p>
							{/if}
						{:else}
							<span class="text-slate-300">—</span>
						{/if}
					</div>

					<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
				</button>
			{/each}
		</section>
	{/if}
{:else}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{/if}

<!-- Modal de registro de pesagem -->
{#if adding}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (adding = false)}
		onkeydown={(e) => e.key === 'Escape' && (adding = false)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<p class="mb-3 font-semibold text-slate-600">{m.new_weight()}</p>
			<Stepper bind:value={newWeight} min={30} max={300} step={0.1} decimals={1} unit="kg" />

			<!-- Dados opcionais da balanca de bioimpedancia (BIA) -->
			<button
				type="button"
				onclick={() => (showScaleFields = !showScaleFields)}
				class="mt-4 flex w-full items-center justify-between text-sm font-semibold text-emerald-700"
			>
				<span>{m.scale_data()}</span>
				<svg viewBox="0 0 24 24" class="h-5 w-5 transition-transform {showScaleFields ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</button>

			{#if showScaleFields}
				<p class="mt-1 mb-3 text-xs text-slate-400">{m.scale_data_hint()}</p>
				<div class="grid grid-cols-2 gap-3">
					{#each bodyCompositionInputs as field (field.key)}
						<label class="block">
							<span class="mb-1 block text-xs font-semibold text-slate-500">{field.label}</span>
							<div class="flex items-center gap-1 rounded-2xl border-2 border-slate-200 bg-white px-3">
								<input
									inputmode="decimal"
									value={scaleValues[field.key] ?? ''}
									oninput={(e) =>
										(scaleValues[field.key] = e.currentTarget.value.replace(/[^0-9.,]/g, ''))}
									placeholder="—"
									class="h-11 w-full min-w-0 bg-transparent text-base outline-none"
								/>
								{#if field.unit}<span class="shrink-0 text-xs text-slate-400">{field.unit}</span>{/if}
							</div>
						</label>
					{/each}
				</div>
			{/if}

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
		</div>
	</div>
{/if}

<!-- Modal de detalhes de uma pesagem -->
{#if selectedLog}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (selectedLog = null)}
		onkeydown={(e) => e.key === 'Escape' && (selectedLog = null)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="flex items-start justify-between">
				<div>
					<p class="text-3xl font-black text-slate-900">{nf.format(selectedLog.weight_kg)} kg</p>
					<p class="text-sm text-slate-500">
						{df.format(new Date(selectedLog.logged_at))} ·
						{new Date(selectedLog.logged_at).toLocaleTimeString(getLocale(), {
							hour: '2-digit',
							minute: '2-digit'
						})}
					</p>
				</div>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (selectedLog = null)}
					class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			{#if selectedBodyComposition.length > 0}
				<div class="mt-4 grid grid-cols-2 gap-3">
					{#each selectedBodyComposition as row (row.label)}
						<div class="rounded-2xl bg-slate-50 p-3">
							<p class="text-lg font-bold text-slate-900">
								{nf.format(row.value ?? 0)}{row.unit ? ` ${row.unit}` : ''}
							</p>
							<p class="text-xs font-semibold text-slate-500">{row.label}</p>
						</div>
					{/each}
				</div>
			{:else}
				<p class="mt-4 text-sm text-slate-400">{m.no_body_composition()}</p>
			{/if}

			<!-- Exclusao sempre com confirmacao -->
			{#if confirmingDeleteWeight}
				<p class="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
					{m.delete_weigh_in_confirm()}
				</p>
				<div class="mt-2 flex gap-2">
					<button
						type="button"
						onclick={() => (confirmingDeleteWeight = false)}
						class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
					>
						{m.cancel()}
					</button>
					<button
						type="button"
						onclick={deleteSelectedWeight}
						class="h-12 flex-1 rounded-2xl bg-red-600 font-semibold text-white active:bg-red-700"
					>
						{m.delete_confirm_button()}
					</button>
				</div>
			{:else}
				<button
					type="button"
					onclick={() => (confirmingDeleteWeight = true)}
					class="mt-5 h-12 w-full rounded-2xl border-2 border-red-200 font-semibold text-red-600 active:bg-red-50"
				>
					{m.delete_weigh_in()}
				</button>
			{/if}
		</div>
	</div>
{/if}
