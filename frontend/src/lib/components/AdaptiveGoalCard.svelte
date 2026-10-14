<script lang="ts">
	import { api, ApiError, localDay, type AdaptiveTdee, type AdaptiveDiaryDay } from '$lib/api';
	import { bootstrap } from '$lib/session.svelte';
	import { errorMessage } from '$lib/errors';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let {
		estimate,
		onchange
	}: { estimate: AdaptiveTdee; onchange: (estimate: AdaptiveTdee) => void } = $props();
	let refreshing = $state(false);
	let adopting = $state(false);
	let confirming = $state(false);
	let refreshFailed = $state(false);
	let checkedAt = $state<Date | null>(null);
	const nf = new Intl.NumberFormat(getLocale());
	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });
	// Durante deploy ou reversao, a API pode responder com o contrato anterior.
	const hasDayDetails = $derived(Array.isArray(estimate.diary_days));
	const blocked = $derived(!hasDayDetails || !estimate.can_adopt || refreshFailed);
	const pendingDays = $derived(
		(estimate.diary_days ?? []).filter(
			(day) =>
				day.filter_status !== 'in_progress' &&
				(day.filter_status === 'missing' ||
					day.filter_status === 'below_filter' ||
					day.has_unknown_energy)
		)
	);
	const requirements = $derived([
		{ have: estimate.days_logged, need: estimate.min_days_logged, label: m.adaptive_food_days() },
		{ have: estimate.weigh_ins, need: estimate.min_weigh_ins, label: m.adaptive_weigh_ins() },
		{ have: estimate.span_days, need: estimate.min_span_days, label: m.adaptive_weight_span() }
	]);
	const explanation = $derived.by(() => {
		if (estimate.message_code === 'MEASURED_BELOW_BMR')
			return m.adaptive_below_bmr({ bmr: nf.format(estimate.bmr_kcal) });
		if (estimate.message_code === 'TOO_FAST') return m.adaptive_cannot_adopt();
		if (estimate.message_code === 'DIARY_CALORIES_MISSING') return m.adaptive_calories_missing();
		if (estimate.message_code === 'REVIEW_DIARY') return m.adaptive_review_policy();
		const messages: Record<string, () => string> = {
			ON_TRACK: m.adaptive_on_track,
			TOO_SLOW: m.adaptive_too_slow,
			STALLED: m.adaptive_stalled,
			ESTIMATE_READY: m.adaptive_estimate_ready
		};
		return messages[estimate.message_code]?.() ?? m.adaptive_need_data();
	});

	function formatDay(day: string): string {
		return df.format(new Date(day + 'T12:00:00'));
	}
	function filterLabel(day: AdaptiveDiaryDay): string {
		if (day.has_unknown_energy) return m.diary_energy_unknown();
		const labels = {
			included: m.diary_filter_included,
			below_filter: m.diary_filter_below_filter,
			missing: m.diary_filter_missing,
			in_progress: m.diary_filter_in_progress
		};
		return labels[day.filter_status]();
	}

	async function refresh(): Promise<void> {
		if (refreshing || adopting) return;
		refreshing = true;
		confirming = false;
		try {
			const updated = await api.getAdaptiveTdee(localDay(), new Date().getTimezoneOffset());
			onchange(updated);
			checkedAt = new Date();
			refreshFailed = false;
			showToast(m.adaptive_updated());
		} catch (error) {
			refreshFailed = true;
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			refreshing = false;
		}
	}

	async function adopt(): Promise<void> {
		if (blocked || adopting || refreshing || estimate.estimated_maintenance_kcal === null) return;
		adopting = true;
		confirming = false;
		try {
			await api.renewDietPeriod(localDay(), estimate.estimated_maintenance_kcal);
			showToast(m.diet_period_renewed());
			await bootstrap();
			onchange(await api.getAdaptiveTdee(localDay(), new Date().getTimezoneOffset()));
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			adopting = false;
		}
	}
</script>

<section class="mb-4 rounded-3xl bg-white p-5 shadow-sm" data-tour="progress-adaptive">
	<p class="mb-3 text-sm font-bold text-slate-400 uppercase">{m.adaptive_title()}</p>
	{#if estimate.has_enough_data}
		<div class="grid grid-cols-2 gap-3">
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">
					{nf.format(estimate.estimated_maintenance_kcal ?? 0)}<span
						class="text-sm font-medium text-slate-400"
					>
						kcal</span
					>
				</p>
				<p class="mt-1 text-xs font-semibold text-slate-500">{m.adaptive_real_maintenance()}</p>
			</div>
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">
					{estimate.weekly_change_kg > 0 ? '+' : ''}{nf.format(estimate.weekly_change_kg)}<span
						class="text-sm font-medium text-slate-400"
					>
						kg</span
					>
				</p>
				<p class="mt-1 text-xs font-semibold text-slate-500">{m.adaptive_weekly_change()}</p>
			</div>
		</div>
	{/if}

	<div
		class="mt-3 flex items-center justify-between gap-3 rounded-2xl border-2 border-slate-100 px-4 py-3"
		data-testid="adaptive-current-target"
	>
		<div>
			<p class="text-xs font-semibold text-slate-400">{m.adaptive_current_target()}</p>
			<p class="mt-1 text-2xl font-black text-slate-700">
				{nf.format(estimate.current_target_kcal)}<span class="text-xs font-medium text-slate-400">
					kcal</span
				>
			</p>
		</div>
		{#if !blocked && estimate.suggested_target_kcal !== null}
			<svg
				viewBox="0 0 24 24"
				class="h-5 w-5 shrink-0 text-slate-300"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				aria-hidden="true"
				><path d="M5 12h14M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg
			>
			<div class="text-right">
				<p class="text-xs font-semibold text-emerald-600">{m.adaptive_suggested_target()}</p>
				<p class="mt-1 text-2xl font-black text-emerald-700">
					{nf.format(estimate.suggested_target_kcal)}
				</p>
			</div>
		{/if}
	</div>

	{#if !estimate.has_enough_data}
		<p class="mt-3 text-sm text-slate-500">{m.adaptive_pending()}</p>
	{:else}
		<p
			class="mt-3 rounded-2xl px-4 py-3 text-sm font-semibold {blocked
				? 'bg-amber-50 text-amber-800'
				: 'bg-emerald-50 text-emerald-800'}"
		>
			{explanation}
		</p>
	{/if}
	{#if refreshFailed}<p class="mt-3 text-sm font-semibold text-amber-700" role="alert">
			{m.adaptive_update_failed()}
		</p>{/if}

	{#if !blocked && estimate.suggested_target_kcal !== null}
		{#if estimate.current_target_kcal === estimate.suggested_target_kcal}
			<p class="mt-3 text-xs text-emerald-700">{m.adaptive_same_value()}</p>
		{:else if confirming}
			<div class="mt-3 rounded-2xl bg-emerald-50 p-3">
				<p class="text-sm font-semibold text-emerald-800">{m.adaptive_adopt_confirm()}</p>
				<div class="mt-3 flex gap-2">
					<button
						type="button"
						onclick={adopt}
						disabled={adopting || refreshing}
						class="h-11 flex-1 rounded-xl bg-emerald-600 px-3 font-bold text-white disabled:opacity-50"
						>{m.confirm()}</button
					>
					<button
						type="button"
						onclick={() => (confirming = false)}
						class="h-11 flex-1 rounded-xl px-3 font-semibold text-slate-500">{m.cancel()}</button
					>
				</div>
			</div>
		{:else}
			<button
				type="button"
				onclick={() => (confirming = true)}
				disabled={adopting || refreshing}
				class="mt-3 min-h-12 w-full rounded-2xl bg-emerald-600 px-3 py-3 text-sm font-bold text-white disabled:opacity-50"
				>{m.adaptive_adopt_button()}</button
			>
		{/if}
	{/if}

	<details class="group mt-4 border-t border-slate-100 pt-2" data-testid="adaptive-details">
		<summary
			class="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-emerald-700 [&::-webkit-details-marker]:hidden"
		>
			{m.adaptive_more_information()}
			<svg
				viewBox="0 0 24 24"
				class="h-4 w-4 transition-transform group-open:rotate-180"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				aria-hidden="true"
				><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg
			>
		</summary>
		<div class="mt-3 space-y-3">
			<p class="text-xs font-bold text-slate-500">{m.adaptive_requirements()}</p>
			{#each requirements as requirement (requirement.label)}
				{@const met = requirement.have >= requirement.need}
				<div class="flex items-start justify-between gap-3 text-xs">
					<span class="text-slate-600">{requirement.label}</span>
					<div class="shrink-0 text-right">
						<strong class={met ? 'text-emerald-700' : 'text-slate-700'}
							>{requirement.have}/{requirement.need}</strong
						>
						<!-- Falta = minimo menos quantidade, limitada a zero para nao mostrar saldo negativo. -->
						<p class="mt-0.5 text-[11px] text-slate-500">
							{met
								? m.adaptive_requirement_met()
								: m.adaptive_remaining_count({
										count: Math.max(0, requirement.need - requirement.have)
									})}
						</p>
					</div>
				</div>
			{/each}
			<p class="text-xs text-slate-500">{m.adaptive_span_help()}</p>
		</div>

		{#if hasDayDetails}
			<div class="mt-4 rounded-2xl bg-slate-50 p-3" data-testid="adaptive-days">
				<h2 class="text-xs font-bold text-slate-600">{m.adaptive_pending_days()}</h2>
				<p class="mt-2 text-xs text-slate-500">
					{m.adaptive_review_counts({
						missing: estimate.days_missing,
						discarded: estimate.days_discarded
					})}
				</p>
				<p class="mt-2 text-xs text-slate-500">{m.diary_filter_help()}</p>
				{#if pendingDays.length > 0}
					<div class="mt-3 divide-y divide-slate-200">
						{#each pendingDays as day (day.date)}
							<a
								href={`/dieta?dia=${day.date}`}
								class="flex min-h-16 items-center justify-between gap-2 py-3 text-left"
							>
								<div class="min-w-0">
									<p class="text-xs font-bold text-slate-700">
										{formatDay(day.date)}{day.kcal === null ? '' : ` · ${nf.format(day.kcal)} kcal`}
									</p>
									<p class="mt-1 text-[11px] text-slate-500">{filterLabel(day)}</p>
								</div>
								<span class="shrink-0 text-xs font-bold text-emerald-700"
									>{m.diary_open_day()} ›</span
								>
							</a>
						{/each}
					</div>
				{:else}
					<p class="mt-3 text-xs text-slate-500">{m.adaptive_no_pending_days()}</p>
				{/if}
			</div>
			<p class="mt-3 text-xs text-slate-500">
				{estimate.adopted_maintenance_kcal === null
					? m.adaptive_formula_base()
					: m.adaptive_adopted_base({ kcal: nf.format(estimate.adopted_maintenance_kcal) })}
			</p>
			<p class="mt-3 text-xs text-slate-500">
				{m.adaptive_dates({
					start: formatDay(estimate.window_start),
					foodEnd: formatDay(estimate.food_window_end),
					weightEnd: formatDay(estimate.weight_window_end)
				})}
			</p>
		{/if}
		{#if estimate.message_code === 'MEASURED_BELOW_BMR'}<p class="mt-3 text-xs text-amber-700">
				{m.adaptive_cannot_adopt_below_bmr()}
			</p>{/if}
		{#if blocked && estimate.suggested_target_kcal !== null}<p class="mt-3 text-xs text-slate-500">
				{m.adaptive_calculated_unavailable()}: {nf.format(estimate.suggested_target_kcal)} kcal
			</p>{/if}
		<button
			type="button"
			onclick={refresh}
			disabled={refreshing || adopting}
			class="mt-4 min-h-11 w-full rounded-xl border-2 border-slate-200 px-3 py-2 text-sm font-bold text-slate-600 active:bg-white disabled:opacity-50"
			>{m.adaptive_update()}</button
		>
		{#if checkedAt}<p class="mt-2 text-xs text-slate-400">
				{m.adaptive_query_time({ time: checkedAt.toLocaleString(getLocale()) })}
			</p>{/if}
		<p class="mt-3 text-xs text-slate-400">{m.adaptive_today_rule()}</p>
	</details>
</section>
