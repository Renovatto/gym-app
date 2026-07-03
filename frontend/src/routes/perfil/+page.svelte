<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, type ActivityLevel, type Objective } from '$lib/api';
	import ChoiceChips from '$lib/components/ChoiceChips.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { bootstrap, session, signOut } from '$lib/session.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale, setLocale, type Locale } from '$lib/paraglide/runtime';
	import { toBackendLocale } from '$lib/errors';

	let height = $state(session.profile?.height_cm ?? 170);
	let weight = $state(session.profile?.weight_kg ?? 75);
	let activity = $state<ActivityLevel | null>(session.profile?.activity_level ?? null);
	let objective = $state<Objective | null>(session.profile?.objective ?? null);
	let dietEnabled = $state<'yes' | 'no' | null>(session.profile?.diet_enabled ? 'yes' : 'no');
	let saved = $state(false);
	let busy = $state(false);
	let confirmingDelete = $state(false);

	let language = $state<Locale>(getLocale());

	async function changeLanguage(locale: Locale): Promise<void> {
		language = locale;
		try {
			await api.updateLocale(toBackendLocale(locale));
		} catch {
			// preferência local ainda vale mesmo se a API falhar
		}
		setLocale(locale); // recarrega a página com o novo idioma
	}

	async function save(): Promise<void> {
		if (!session.profile || !activity || !objective) return;
		busy = true;
		saved = false;
		try {
			await api.saveProfile({
				height_cm: height,
				weight_kg: weight,
				birthdate: session.profile.birthdate,
				sex: session.profile.sex,
				activity_level: activity,
				objective,
				diet_enabled: dietEnabled === 'yes',
				scale_mac: session.profile.scale_mac
			});
			await bootstrap();
			saved = true;
			setTimeout(() => (saved = false), 2500);
		} finally {
			busy = false;
		}
	}

	async function exportData(): Promise<void> {
		const data = await api.exportData();
		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = 'gymapp-dados.json';
		link.click();
		URL.revokeObjectURL(url);
	}

	async function deleteAccount(): Promise<void> {
		await api.deleteAccount();
		signOut();
		await goto('/login');
	}

	async function logout(): Promise<void> {
		signOut();
		await goto('/login');
	}
</script>

<h1 class="mb-1 text-2xl font-bold">{m.tab_profile()}</h1>
<p class="mb-6 text-slate-500">{session.user?.email}</p>

<section class="space-y-6 rounded-3xl bg-white p-5 shadow-sm">
	<div>
		<p class="mb-3 font-semibold text-slate-600">{m.height()}</p>
		<Stepper bind:value={height} min={100} max={230} unit="cm" />
	</div>
	<div>
		<p class="mb-3 font-semibold text-slate-600">{m.weight()}</p>
		<Stepper bind:value={weight} min={30} max={300} step={0.5} decimals={1} unit="kg" />
	</div>
	<div>
		<p class="mb-3 font-semibold text-slate-600">{m.ob_activity_title()}</p>
		<ChoiceChips
			bind:value={activity}
			options={[
				{ value: 'sedentary', label: m.activity_sedentary() },
				{ value: 'light', label: m.activity_light() },
				{ value: 'moderate', label: m.activity_moderate() },
				{ value: 'active', label: m.activity_active() },
				{ value: 'very_active', label: m.activity_very_active() }
			]}
		/>
	</div>
	<div>
		<p class="mb-3 font-semibold text-slate-600">{m.ob_objective_title()}</p>
		<ChoiceChips
			bind:value={objective}
			options={[
				{ value: 'gain_muscle', label: m.objective_gain_muscle() },
				{ value: 'lose_fat', label: m.objective_lose_fat() },
				{ value: 'recomp', label: m.objective_recomp() },
				{ value: 'maintain', label: m.objective_maintain() }
			]}
		/>
	</div>
	<div>
		<p class="mb-3 font-semibold text-slate-600">{m.ob_diet_title()}</p>
		<ChoiceChips
			columns={2}
			bind:value={dietEnabled}
			options={[
				{ value: 'yes', label: m.yes() },
				{ value: 'no', label: m.later() }
			]}
		/>
	</div>
	<button
		type="button"
		disabled={busy}
		onclick={save}
		class="h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-50"
	>
		{saved ? m.saved() : m.save()}
	</button>
</section>

<section class="mt-4 rounded-3xl bg-white p-5 shadow-sm">
	<p class="mb-3 font-semibold text-slate-600">{m.language()}</p>
	<ChoiceChips
		columns={3}
		bind:value={language}
		onselect={changeLanguage}
		options={[
			{ value: 'pt-br', label: 'Português' },
			{ value: 'en', label: 'English' },
			{ value: 'es', label: 'Español' }
		]}
	/>
</section>

<section class="mt-4 space-y-3 rounded-3xl bg-white p-5 shadow-sm">
	<p class="font-semibold text-slate-600">{m.data_privacy()}</p>
	<button
		type="button"
		onclick={exportData}
		class="h-12 w-full rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
	>
		{m.export_data()}
	</button>
	{#if confirmingDelete}
		<p class="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
			{m.delete_confirm_text()}
		</p>
		<div class="flex gap-2">
			<button
				type="button"
				onclick={() => (confirmingDelete = false)}
				class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700"
			>
				{m.cancel()}
			</button>
			<button
				type="button"
				onclick={deleteAccount}
				class="h-12 flex-1 rounded-2xl bg-red-600 font-semibold text-white active:bg-red-700"
			>
				{m.delete_confirm_button()}
			</button>
		</div>
	{:else}
		<button
			type="button"
			onclick={() => (confirmingDelete = true)}
			class="h-12 w-full rounded-2xl border-2 border-red-200 font-semibold text-red-600 active:bg-red-50"
		>
			{m.delete_account()}
		</button>
	{/if}
</section>

<button
	type="button"
	onclick={logout}
	class="mt-4 h-12 w-full rounded-2xl border-2 border-slate-200 font-semibold text-slate-500 active:bg-slate-100"
>
	{m.logout()}
</button>
