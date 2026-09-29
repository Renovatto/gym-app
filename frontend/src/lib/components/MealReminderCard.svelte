<script lang="ts">
	import { api, type OverdueMeal } from '$lib/api';
	import { mealTypeLabel } from '$lib/labels';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	/*
	 * Refeicao atrasada: ja passou do horario em que a pessoa costuma lancar (aprendido
	 * do proprio diario pelo backend) e ainda nao tem nada lancado hoje.
	 *
	 * "Pulei hoje" existe para quem pulou a refeicao ou faz jejum: um toque cala o
	 * cartao (e o push) daquela refeicao so neste dia, em vez de o app insistir.
	 */

	let { meals, today }: { meals: OverdueMeal[]; today: string } = $props();

	let skipped = $state<string[]>([]);
	let skipping = $state(false);

	// Mostra uma por vez: a de horario mais recente, que e a que esta atrasada agora.
	const meal = $derived(
		[...meals].filter((item) => !skipped.includes(item.meal_type)).sort((a, b) => b.usual_minutes - a.usual_minutes)[0] ??
			null
	);

	const timeFormat = new Intl.DateTimeFormat(getLocale(), { hour: 'numeric', minute: '2-digit' });

	// minutos desde a meia-noite -> "13:00" no formato de hora do idioma
	function formatMinutes(minutes: number): string {
		const date = new Date();
		date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
		return timeFormat.format(date);
	}

	async function skipToday(): Promise<void> {
		if (!meal) return;
		const mealType = meal.meal_type;
		skipping = true;
		try {
			await api.skipMealReminder(mealType, today);
			skipped = [...skipped, mealType];
			showToast(m.meal_reminder_skipped_toast({ meal: mealTypeLabel(mealType) }));
		} finally {
			skipping = false;
		}
	}
</script>

{#if meal}
	<section class="mb-3 rounded-3xl border-2 border-amber-200 bg-amber-50 p-4">
		<div class="flex gap-3">
			<span class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-amber-100 text-amber-700">
				<svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2M9 2h6" /></svg>
			</span>
			<div class="min-w-0 flex-1">
				<p class="font-extrabold text-amber-900">
					{m.meal_reminder_title({ meal: mealTypeLabel(meal.meal_type) })}
				</p>
				<p class="text-sm text-amber-800">
					{m.meal_reminder_hint({ time: formatMinutes(meal.usual_minutes) })}
				</p>
			</div>
		</div>
		<div class="mt-3 flex gap-2">
			<a
				href="/dieta/adicionar?meal={meal.meal_type}"
				class="grid h-11 flex-1 place-items-center rounded-2xl bg-emerald-600 text-sm font-bold text-[#fff] active:bg-emerald-700"
			>
				{m.meal_reminder_log({ meal: mealTypeLabel(meal.meal_type).toLowerCase() })}
			</a>
			<button
				type="button"
				disabled={skipping}
				onclick={skipToday}
				class="h-11 shrink-0 rounded-2xl bg-white px-4 text-sm font-bold text-amber-800 active:bg-amber-100 disabled:opacity-50"
			>
				{m.meal_reminder_skip()}
			</button>
		</div>
	</section>
{/if}
