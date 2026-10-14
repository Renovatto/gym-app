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
	const blocked = $derived(!estimate.can_adopt || refreshFailed);
	const requirements = $derived([
		{ have: estimate.days_logged, need: estimate.min_days_logged, label: m.adaptive_food_days() },
		{ have: estimate.weigh_ins, need: estimate.min_weigh_ins, label: m.adaptive_weigh_ins() },
		{ have: estimate.span_days, need: estimate.min_span_days, label: m.adaptive_weight_span() }
	]);
	const explanation = $derived.by(() => {
		if (estimate.message_code === 'MEASURED_BELOW_BMR')
			return m.adaptive_below_bmr({ bmr: nf.format(estimate.bmr_kcal) });
		if (estimate.message_code === 'TOO_FAST') return m.adaptive_cannot_adopt();
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
		const labels = {
			included: m.diary_filter_included,
			below_filter: m.diary_filter_below_filter,
			missing: m.diary_filter_missing,
			in_progress: m.diary_filter_in_progress
		};
		return labels[day.filter_status]();
	}
	function reviewLabel(day: AdaptiveDiaryDay): string {
		return day.review_status === 'complete'
			? m.diary_review_complete()
			: day.review_status === 'incomplete'
				? m.diary_review_incomplete()
				: m.diary_review_unreviewed();
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
	<p class="mb-2 text-sm font-bold text-slate-400 uppercase">{m.adaptive_title()}</p>
	{#if estimate.has_enough_data}
		<p
			class="mb-2 inline-block rounded-lg px-2.5 py-1 text-xs font-bold {blocked
				? 'bg-amber-50 text-amber-800'
				: 'bg-emerald-50 text-emerald-700'}"
		>
			{blocked ? m.adaptive_blocked() : m.adaptive_available()}
		</p>
		<h2 class="text-base font-bold">{m.adaptive_data_ready()}</h2>
	{:else}
		<h2 class="text-base font-bold">{m.adaptive_pending()}</h2>
	{/if}
	<p class="mt-2 text-sm text-slate-600">{explanation}</p>
	{#if estimate.message_code === 'MEASURED_BELOW_BMR'}
		<p class="mt-2 rounded-2xl bg-amber-50 p-3 text-sm text-amber-800">
			{m.adaptive_cannot_adopt_below_bmr()}
		</p>
	{/if}
	{#if refreshFailed}<p class="mt-3 text-sm font-semibold text-amber-700" role="alert">
			{m.adaptive_update_failed()}
		</p>{/if}

	{#if estimate.has_enough_data}
		<div class="mt-4 grid grid-cols-2 gap-3">
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black">
					{nf.format(estimate.estimated_maintenance_kcal ?? 0)}<span
						class="text-xs font-medium text-slate-400"
					>
						kcal</span
					>
				</p>
				<p class="mt-1 text-xs font-semibold text-slate-500">{m.adaptive_real_maintenance()}</p>
			</div>
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black">
					{estimate.weekly_change_kg > 0 ? '+' : ''}{nf.format(estimate.weekly_change_kg)}<span
						class="text-xs font-medium text-slate-400"
					>
						kg</span
					>
				</p>
				<p class="mt-1 text-xs font-semibold text-slate-500">{m.adaptive_weekly_change()}</p>
			</div>
		</div>
	{/if}

	<div class="mt-4 space-y-3 border-t border-slate-100 pt-4">
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

	<details class="mt-4 rounded-2xl bg-slate-50 p-3" data-testid="adaptive-days">
		<summary class="cursor-pointer text-sm font-bold text-emerald-700"
			>{m.adaptive_review_days()}</summary
		>
		<p class="mt-3 text-xs text-slate-600">
			{m.adaptive_review_counts({
				missing: estimate.days_missing,
				discarded: estimate.days_discarded
			})}
		</p>
		<p class="mt-2 text-xs font-semibold text-slate-700">
			{m.adaptive_review_progress({
				have: estimate.days_reviewed,
				total: estimate.days_reviewed + estimate.days_to_review
			})}
		</p>
		<p class="mt-2 text-xs text-slate-500">{m.diary_filter_help()}</p>
		<p class="mt-2 text-xs text-slate-500">{m.adaptive_review_policy()}</p>
		<div class="mt-3 divide-y divide-slate-200">
			{#each estimate.diary_days as day (day.date)}
				<a
					href={`/dieta?dia=${day.date}&revisar=1`}
					class="flex min-h-16 items-center justify-between gap-2 py-3 text-left"
				>
					<div class="min-w-0">
						<p class="text-xs font-bold text-slate-700">
							{formatDay(day.date)} · {day.kcal === null
								? m.diary_energy_unknown()
								: `${nf.format(day.kcal)} kcal`}
						</p>
						<p class="mt-1 text-[11px] text-slate-500">{filterLabel(day)}</p>
						<p
							class="mt-1 text-[11px] {day.review_status === 'complete'
								? 'text-emerald-700'
								: 'text-slate-500'}"
						>
							{reviewLabel(day)}
						</p>
						{#if day.estimated_meals > 0}<span class="text-[11px] text-amber-700"
								>{m.diary_approx_badge()}{day.has_unknown_energy
									? ` · ${m.diary_energy_unknown()}`
									: ''}</span
							>{/if}
					</div>
					<span class="shrink-0 text-xs font-bold text-emerald-700">{m.diary_review_date()} ›</span>
				</a>
			{/each}
		</div>
	</details>

	<div class="mt-4 rounded-2xl border-2 border-slate-100 p-3">
		<p class="text-xs font-semibold text-slate-400">{m.adaptive_current_target()}</p>
		<p class="mt-1 text-xl font-black text-slate-700">
			{nf.format(estimate.current_target_kcal)}
			<span class="text-xs font-medium text-slate-400">kcal</span>
		</p>
		<p class="mt-1 text-xs text-slate-500">
			{estimate.adopted_maintenance_kcal === null
				? m.adaptive_formula_base()
				: m.adaptive_adopted_base({ kcal: nf.format(estimate.adopted_maintenance_kcal) })}
		</p>
	</div>
	{#if estimate.suggested_target_kcal !== null}
		{#if blocked}
			<details class="mt-3 text-xs text-slate-500">
				<summary class="cursor-pointer">{m.adaptive_calculated_unavailable()}</summary>
				<p class="mt-2 font-bold">{nf.format(estimate.suggested_target_kcal)} kcal</p>
			</details>
		{:else if estimate.current_target_kcal === estimate.suggested_target_kcal}
			<p class="mt-3 text-xs text-emerald-700">{m.adaptive_same_value()}</p>
		{:else}
			<p class="mt-3 text-sm font-bold text-emerald-700">
				{m.adaptive_suggested_target()}: {nf.format(estimate.suggested_target_kcal)} kcal
			</p>
			{#if confirming}
				<div class="mt-3 rounded-2xl bg-emerald-50 p-3">
					<p class="text-sm font-semibold text-emerald-800">{m.adaptive_adopt_confirm()}</p>
					<div class="mt-3 flex gap-2">
						<button
							type="button"
							onclick={adopt}
							disabled={adopting || refreshing}
							class="h-11 flex-1 rounded-xl bg-emerald-600 px-3 font-bold text-white disabled:opacity-50"
							>{m.confirm()}</button
						><button
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
	{/if}
	<button
		type="button"
		onclick={refresh}
		disabled={refreshing || adopting}
		class="mt-4 min-h-11 w-full rounded-xl border-2 border-slate-200 px-3 py-2 text-sm font-bold text-slate-600 active:bg-slate-50 disabled:opacity-50"
		>{m.adaptive_update()}</button
	>
	{#if checkedAt}<p class="mt-2 text-xs text-slate-400">
			{m.adaptive_query_time({ time: checkedAt.toLocaleString(getLocale()) })}
		</p>{/if}
	<p class="mt-3 text-xs text-slate-500">
		{m.adaptive_dates({
			start: formatDay(estimate.window_start),
			foodEnd: formatDay(estimate.food_window_end),
			weightEnd: formatDay(estimate.weight_window_end)
		})}
	</p>
	<p class="mt-2 text-xs text-slate-400">{m.adaptive_today_rule()}</p>
</section>
