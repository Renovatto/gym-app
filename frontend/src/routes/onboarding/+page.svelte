<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, type ActivityLevel, type Objective, type Sex } from '$lib/api';
	import ChoiceChips from '$lib/components/ChoiceChips.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { bootstrap } from '$lib/session.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale, setLocale, localStorageKey, type Locale } from '$lib/paraglide/runtime';
	import { toBackendLocale } from '$lib/errors';

	// Idioma e a PRIMEIRA pergunta do cadastro e o padrao e ingles: se o usuario
	// ainda nao escolheu explicitamente (sem chave no localStorage), forca 'en'
	// antes de tudo (setLocale recarrega a pagina ja em ingles, uma unica vez).
	const hasExplicitLocale =
		typeof localStorage !== 'undefined' && localStorage.getItem(localStorageKey) !== null;
	if (!hasExplicitLocale && getLocale() !== 'en') {
		setLocale('en');
	}

	let language = $state<Locale>(getLocale());

	function pickLanguage(locale: Locale): void {
		language = locale;
		// persiste no perfil do usuario; a preferencia local vale mesmo se a API falhar
		api.updateLocale(toBackendLocale(locale)).catch(() => {});
		if (locale !== getLocale()) setLocale(locale); // recarrega ja no novo idioma
	}

	let step = $state(0);
	let firstName = $state('');
	let lastName = $state('');
	let sex = $state<Sex | null>(null);
	let birthdate = $state('');
	let height = $state(170);
	let weight = $state(75);
	let activity = $state<ActivityLevel | null>(null);
	let objective = $state<Objective | null>(null);
	let dietEnabled = $state<'yes' | 'no' | null>(null);
	let busy = $state(false);
	let error = $state('');

	const TOTAL_STEPS = 8;

	const canAdvance = $derived(
		[
			language !== null,
			firstName.trim() !== '',
			sex !== null,
			birthdate !== '',
			height > 0 && weight > 0,
			activity !== null,
			objective !== null,
			dietEnabled !== null
		][step]
	);

	async function next(): Promise<void> {
		if (step < TOTAL_STEPS - 1) {
			step += 1;
			return;
		}
		busy = true;
		error = '';
		try {
			await api.saveProfile({
				first_name: firstName.trim() || null,
				last_name: lastName.trim() || null,
				height_cm: height,
				weight_kg: weight,
				birthdate,
				sex: sex!,
				activity_level: activity!,
				objective: objective!,
				cut_intensity: 'moderate', // padrao; ajustavel depois no perfil
				diet_enabled: dietEnabled === 'yes',
				scale_mac: null
			});
			await bootstrap();
			await goto('/');
		} catch {
			error = m.error_generic();
		} finally {
			busy = false;
		}
	}
</script>

<div class="flex min-h-[85dvh] flex-col">
	<div class="mb-6 flex gap-1.5">
		{#each Array(TOTAL_STEPS) as _, i (i)}
			<div class="h-1.5 flex-1 rounded-full {i <= step ? 'bg-emerald-600' : 'bg-slate-200'}"></div>
		{/each}
	</div>

	<div class="flex-1">
		{#if step === 0}
			<h1 class="mb-6 text-2xl font-bold">{m.ob_language_title()}</h1>
			<ChoiceChips
				bind:value={language}
				onselect={pickLanguage}
				options={[
					{ value: 'en' as Locale, label: 'English' },
					{ value: 'pt-br' as Locale, label: 'Português (Brasil)' },
					{ value: 'es' as Locale, label: 'Español' }
				]}
			/>
		{:else if step === 1}
			<h1 class="mb-6 text-2xl font-bold">{m.ob_name_title()}</h1>
			<div class="space-y-3">
				<input
					type="text"
					bind:value={firstName}
					placeholder={m.first_name()}
					autocomplete="given-name"
					class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-lg outline-none focus:border-emerald-600"
				/>
				<input
					type="text"
					bind:value={lastName}
					placeholder={m.last_name()}
					autocomplete="family-name"
					class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-lg outline-none focus:border-emerald-600"
				/>
			</div>
		{:else if step === 2}
			<h1 class="mb-6 text-2xl font-bold">{m.ob_sex_title()}</h1>
			<ChoiceChips
				columns={2}
				bind:value={sex}
				options={[
					{ value: 'male', label: m.sex_male() },
					{ value: 'female', label: m.sex_female() }
				]}
			/>
		{:else if step === 3}
			<h1 class="mb-6 text-2xl font-bold">{m.ob_birthdate_title()}</h1>
			<input
				type="date"
				bind:value={birthdate}
				max={new Date().toISOString().slice(0, 10)}
				class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-lg outline-none focus:border-emerald-600"
			/>
		{:else if step === 4}
			<h1 class="mb-6 text-2xl font-bold">{m.ob_measures_title()}</h1>
			<div class="space-y-8">
				<div>
					<p class="mb-3 font-semibold text-slate-600">{m.height()}</p>
					<Stepper bind:value={height} min={100} max={230} unit="cm" />
				</div>
				<div>
					<p class="mb-3 font-semibold text-slate-600">{m.weight()}</p>
					<Stepper bind:value={weight} min={30} max={300} step={0.5} decimals={1} unit="kg" />
				</div>
			</div>
		{:else if step === 5}
			<h1 class="mb-6 text-2xl font-bold">{m.ob_activity_title()}</h1>
			<ChoiceChips
				bind:value={activity}
				options={[
					{ value: 'sedentary', label: m.activity_sedentary(), hint: m.activity_sedentary_hint() },
					{ value: 'light', label: m.activity_light(), hint: m.activity_light_hint() },
					{ value: 'moderate', label: m.activity_moderate(), hint: m.activity_moderate_hint() },
					{ value: 'active', label: m.activity_active(), hint: m.activity_active_hint() },
					{
						value: 'very_active',
						label: m.activity_very_active(),
						hint: m.activity_very_active_hint()
					}
				]}
			/>
		{:else if step === 6}
			<h1 class="mb-6 text-2xl font-bold">{m.ob_objective_title()}</h1>
			<ChoiceChips
				bind:value={objective}
				options={[
					{ value: 'gain_muscle', label: m.objective_gain_muscle(), hint: m.objective_gain_muscle_hint() },
					{ value: 'lose_fat', label: m.objective_lose_fat(), hint: m.objective_lose_fat_hint() },
					{ value: 'recomp', label: m.objective_recomp(), hint: m.objective_recomp_hint() },
					{ value: 'maintain', label: m.objective_maintain(), hint: m.objective_maintain_hint() }
				]}
			/>
		{:else}
			<h1 class="mb-2 text-2xl font-bold">{m.ob_diet_title()}</h1>
			<p class="mb-6 text-slate-500">{m.ob_diet_text()}</p>
			<ChoiceChips
				bind:value={dietEnabled}
				options={[
					{ value: 'yes', label: m.yes(), hint: m.ob_diet_yes_hint() },
					{ value: 'no', label: m.later(), hint: m.ob_diet_no_hint() }
				]}
			/>
		{/if}

		{#if error}
			<p class="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</p>
		{/if}
	</div>

	<div class="mt-8 flex gap-3">
		{#if step > 0}
			<button
				type="button"
				class="h-14 flex-1 rounded-2xl border-2 border-slate-200 bg-white font-bold text-slate-700 active:bg-slate-100"
				onclick={() => (step -= 1)}
			>
				{m.back()}
			</button>
		{/if}
		<button
			type="button"
			disabled={!canAdvance || busy}
			class="h-14 flex-[2] rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-40"
			onclick={next}
		>
			{step === TOTAL_STEPS - 1 ? m.finish() : m.next()}
		</button>
	</div>
</div>
