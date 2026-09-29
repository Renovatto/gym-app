<script lang="ts">
	import { ApiError, api, localDay, type ReminderSettings } from '$lib/api';
	import ChoiceChips from '$lib/components/ChoiceChips.svelte';
	import { errorMessage } from '$lib/errors';
	import { ensurePushSubscription, isPushSupported } from '$lib/push';
	import { session } from '$lib/session.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { mealTypeLabel } from '$lib/labels';
	import type { MealType } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	/*
	 * Perfil > Lembretes: push de refeicao atrasada, de pesagem e de sequencia em risco.
	 *
	 * Tudo nasce desligado (notificacao nao pedida faz a pessoa desinstalar o app). Ligar
	 * o primeiro lembrete e o momento de pedir a permissao do sistema - sempre dentro do
	 * toque, que e o unico jeito do navegador aceitar o pedido.
	 */

	type ReminderKind = 'meals' | 'weigh_in' | 'streak';
	type OnOff = 'on' | 'off';

	let settings = $state<ReminderSettings | null>(null);
	let choices = $state<Record<ReminderKind, OnOff>>({ meals: 'off', weigh_in: 'off', streak: 'off' });
	let saving = $state(false);

	const pushSupported = isPushSupported();
	const dietOn = $derived(session.profile?.diet_enabled ?? false);
	const tzOffset = new Date().getTimezoneOffset();

	async function load(): Promise<void> {
		settings = await api.getReminderSettings(localDay(), tzOffset);
		choices = {
			meals: settings.meals ? 'on' : 'off',
			weigh_in: settings.weigh_in ? 'on' : 'off',
			streak: settings.streak ? 'on' : 'off'
		};
	}

	$effect(() => {
		load();
	});

	// Permissao + assinatura deste aparelho. Devolve false (e explica) se nao deu.
	async function ensurePermission(): Promise<boolean> {
		if (!pushSupported) return false;
		if (Notification.permission !== 'granted') {
			const answer = await Notification.requestPermission();
			if (answer !== 'granted') {
				showToast(m.reminders_permission_denied());
				return false;
			}
		}
		return ensurePushSubscription();
	}

	// liga/desliga e leve e reversivel em 1 toque: sem confirmacao, com toast
	async function toggle(kind: ReminderKind, value: OnOff): Promise<void> {
		if (!settings) return;
		const previous: OnOff = settings[kind] ? 'on' : 'off';
		if (previous === value) return;
		if (value === 'on' && !(await ensurePermission())) {
			choices[kind] = previous; // o chip trocou antes: volta para nao mentir
			return;
		}
		saving = true;
		try {
			settings = await api.saveReminderSettings(localDay(), tzOffset, {
				meals: choices.meals === 'on',
				weigh_in: choices.weigh_in === 'on',
				streak: choices.streak === 'on',
				time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone
			});
			showToast(value === 'on' ? m.reminders_saved_on() : m.reminders_saved_off());
		} catch (e) {
			choices[kind] = previous;
			showToast(errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR'));
		} finally {
			saving = false;
		}
	}

	const timeFormat = new Intl.DateTimeFormat(getLocale(), { hour: 'numeric', minute: '2-digit' });

	// minutos desde a meia-noite -> "13:00" no formato de hora do idioma
	function formatMinutes(minutes: number): string {
		const date = new Date();
		date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
		return timeFormat.format(date);
	}

	const ON_OFF_OPTIONS = [
		{ value: 'on' as const, label: m.reminders_on() },
		{ value: 'off' as const, label: m.reminders_off() }
	];
	const MEALS_WITH_REMINDER: MealType[] = ['breakfast', 'lunch', 'dinner'];
</script>

<div class="mb-4 flex items-center gap-2">
	<a
		href="/perfil"
		aria-label={m.back()}
		class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
	>
		<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
	</a>
	<h1 class="text-2xl font-bold">{m.reminders_title()}</h1>
</div>

<p class="mb-4 text-sm text-slate-500">{m.reminders_subtitle()}</p>

{#if !pushSupported}
	<!-- iPhone fora do app instalado (Safari em aba) nao tem push -->
	<div class="mb-4 rounded-3xl bg-sky-50 p-4">
		<p class="text-sm font-bold text-sky-900">{m.reminders_unsupported_title()}</p>
		<p class="mt-1 text-sm text-sky-800">{m.reminders_unsupported_hint()}</p>
	</div>
{/if}

{#if !settings}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<fieldset disabled={!pushSupported || saving} class="space-y-3">
		<section class="rounded-3xl bg-white p-5 shadow-sm">
			<p class="font-bold text-slate-900">{m.reminders_meals_label()}</p>
			<p class="mb-3 text-xs text-slate-500">{m.reminders_meals_hint()}</p>
			{#if dietOn}
				<ChoiceChips
					columns={2}
					bind:value={choices.meals}
					onselect={(v) => toggle('meals', v)}
					options={ON_OFF_OPTIONS}
				/>
				<ul class="mt-4 overflow-hidden rounded-2xl border-2 border-slate-100 text-sm">
					{#each MEALS_WITH_REMINDER as meal, index (meal)}
						{@const usual = settings.usual_meal_minutes[meal] ?? null}
						<li class="flex justify-between gap-2 px-3 py-2.5 {index > 0 ? 'border-t border-slate-100' : ''}">
							<span class="text-slate-700">{mealTypeLabel(meal)}</span>
							{#if usual !== null}
								<span class="font-bold text-emerald-700">{m.reminders_usual_time({ time: formatMinutes(usual) })}</span>
							{:else}
								<span class="font-semibold text-slate-400">{m.reminders_learning()}</span>
							{/if}
						</li>
					{/each}
				</ul>
			{:else}
				<p class="rounded-2xl bg-slate-50 px-3 py-2.5 text-sm text-slate-500">{m.reminders_meals_need_diet()}</p>
			{/if}
		</section>

		<section class="rounded-3xl bg-white p-5 shadow-sm">
			<p class="font-bold text-slate-900">{m.reminders_weigh_label()}</p>
			<p class="mb-3 text-xs text-slate-500">{m.reminders_weigh_hint()}</p>
			<ChoiceChips
				columns={2}
				bind:value={choices.weigh_in}
				onselect={(v) => toggle('weigh_in', v)}
				options={ON_OFF_OPTIONS}
			/>
		</section>

		<section class="rounded-3xl bg-white p-5 shadow-sm">
			<p class="font-bold text-slate-900">{m.reminders_streak_label()}</p>
			<p class="mb-3 text-xs text-slate-500">{m.reminders_streak_hint()}</p>
			<ChoiceChips
				columns={2}
				bind:value={choices.streak}
				onselect={(v) => toggle('streak', v)}
				options={ON_OFF_OPTIONS}
			/>
		</section>
	</fieldset>

	<p class="mt-4 rounded-3xl bg-slate-100 px-4 py-3 text-sm text-slate-600">{m.reminders_quiet_note()}</p>
{/if}
