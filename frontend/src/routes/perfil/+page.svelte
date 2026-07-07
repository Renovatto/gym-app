<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError, type ActivityLevel, type CutIntensity, type Objective } from '$lib/api';
	import ChoiceChips from '$lib/components/ChoiceChips.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { bootstrap, session, signOut } from '$lib/session.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale, setLocale, type Locale } from '$lib/paraglide/runtime';
	import { setTheme, theme, type ThemePref } from '$lib/theme.svelte';
	import { errorMessage, toBackendLocale } from '$lib/errors';

	let firstName = $state(session.profile?.first_name ?? '');
	let lastName = $state(session.profile?.last_name ?? '');
	let birthdate = $state(session.profile?.birthdate ?? '');
	let height = $state(session.profile?.height_cm ?? 170);
	let weight = $state(session.profile?.weight_kg ?? 75);
	let activity = $state<ActivityLevel | null>(session.profile?.activity_level ?? null);
	let objective = $state<Objective | null>(session.profile?.objective ?? null);
	let cutIntensity = $state<CutIntensity>(session.profile?.cut_intensity ?? 'moderate');
	let dietEnabled = $state<'yes' | 'no' | null>(session.profile?.diet_enabled ? 'yes' : 'no');
	let saved = $state(false);
	let busy = $state(false);
	let confirmingDelete = $state(false);

	// Idade calculada a partir da data de nascimento (mesma regra do backend).
	const age = $derived.by(() => {
		if (!birthdate) return null;
		const d = new Date(birthdate + 'T12:00:00');
		const today = new Date();
		let years = today.getFullYear() - d.getFullYear();
		const monthDayBefore =
			today.getMonth() < d.getMonth() ||
			(today.getMonth() === d.getMonth() && today.getDate() < d.getDate());
		if (monthDayBefore) years -= 1;
		return years;
	});

	let language = $state<Locale>(getLocale());

	// Grupos recolhiveis do perfil. Conta comeca sempre minimizado (e vem primeiro).
	let openGroups = $state<Record<string, boolean>>({
		account: false,
		data: false,
		preferences: false,
		privacy: false
	});
	function toggleGroup(key: string): void {
		openGroups[key] = !openGroups[key];
	}

	// troca de e-mail (sem senha): mostra o e-mail atual; o lapis abre a edicao
	let editingEmail = $state(false);
	let newEmail = $state('');
	let emailError = $state('');
	let emailBusy = $state(false);

	function startEditEmail(): void {
		newEmail = session.user?.email ?? '';
		emailError = '';
		editingEmail = true;
	}

	async function changeEmail(): Promise<void> {
		emailError = '';
		emailBusy = true;
		try {
			await api.changeEmail(newEmail.trim());
			await bootstrap();
			editingEmail = false;
			showToast(m.email_changed());
		} catch (e) {
			emailError = errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR');
		} finally {
			emailBusy = false;
		}
	}

	// troca de senha: um botao revela os campos de senha atual e nova
	let showPasswordFields = $state(false);
	let currentPassword = $state('');
	let newPassword = $state('');
	let passwordError = $state('');
	let passwordBusy = $state(false);

	async function changePassword(): Promise<void> {
		passwordError = '';
		if (newPassword.length < 8) {
			passwordError = errorMessage('PASSWORD_TOO_SHORT');
			return;
		}
		passwordBusy = true;
		try {
			await api.changePassword(currentPassword, newPassword);
			currentPassword = '';
			newPassword = '';
			showPasswordFields = false;
			showToast(m.password_changed());
		} catch (e) {
			passwordError = errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR');
		} finally {
			passwordBusy = false;
		}
	}

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
				first_name: firstName.trim() || null,
				last_name: lastName.trim() || null,
				height_cm: height,
				weight_kg: weight,
				birthdate: birthdate || session.profile.birthdate,
				sex: session.profile.sex,
				activity_level: activity,
				objective,
				cut_intensity: cutIntensity,
				diet_enabled: dietEnabled === 'yes',
				scale_mac: session.profile.scale_mac
			});
			await bootstrap();
			saved = true;
			showToast(m.toast_saved());
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
		showToast(m.toast_exported());
	}

	async function deleteAccount(): Promise<void> {
		await api.deleteAccount();
		showToast(m.toast_deleted());
		signOut();
		await goto('/login');
	}

	async function logout(): Promise<void> {
		signOut();
		await goto('/login');
	}
</script>

<h1 class="mb-4 text-2xl font-bold">{m.tab_profile()}</h1>

<a
	href="/guia"
	class="mb-4 flex items-center justify-between rounded-3xl bg-white p-4 shadow-sm active:bg-slate-50"
>
	<div class="flex items-center gap-3">
		<span class="grid h-10 w-10 place-items-center rounded-2xl bg-emerald-50 text-emerald-600">
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 6.5A5.5 5.5 0 0117.5 12M4 19.5V6a2 2 0 012-2h11a1 1 0 011 1v11H6a2 2 0 00-2 2zm2 0a2 2 0 002 2h11" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</span>
		<span class="font-semibold text-slate-800">{m.guide_link()}</span>
	</div>
	<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
</a>

<!-- Cabecalho recolhivel reutilizado por todos os grupos do perfil. -->
{#snippet groupHeader(key: string, title: string)}
	<button
		type="button"
		onclick={() => toggleGroup(key)}
		class="flex w-full items-center justify-between px-5 py-4 text-left"
	>
		<span class="font-bold text-slate-800">{title}</span>
		<svg
			viewBox="0 0 24 24"
			class="h-5 w-5 text-slate-400 transition-transform {openGroups[key] ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
		>
			<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	</button>
{/snippet}

<div class="space-y-3">
	<!-- CONTA (primeiro e minimizado por padrao) -->
	<section class="overflow-hidden rounded-3xl bg-white shadow-sm">
		{@render groupHeader('account', m.section_account())}
		{#if openGroups.account}
			<div class="space-y-5 px-5 pb-5">
				<!-- E-mail: mostrado como texto; o lapis abre a edicao -->
				<div>
					<p class="mb-2 text-xs font-semibold text-slate-400 uppercase">{m.email_label()}</p>
					{#if editingEmail}
						<div class="space-y-3">
							<input
								type="email"
								bind:value={newEmail}
								placeholder={m.new_email()}
								autocomplete="email"
								class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
							/>
							{#if emailError}
								<p class="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{emailError}</p>
							{/if}
							<div class="flex gap-2">
								<button
									type="button"
									onclick={() => (editingEmail = false)}
									class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
								>
									{m.cancel()}
								</button>
								<button
									type="button"
									disabled={emailBusy || !newEmail}
									onclick={changeEmail}
									class="h-12 flex-1 rounded-2xl bg-emerald-600 font-semibold text-white active:bg-emerald-700 disabled:opacity-40"
								>
									{m.save()}
								</button>
							</div>
						</div>
					{:else}
						<div class="flex items-center justify-between gap-2">
							<span class="min-w-0 flex-1 truncate font-semibold text-slate-800">{session.user?.email}</span>
							<button
								type="button"
								aria-label={m.change_email()}
								onclick={startEditEmail}
								class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
							>
								<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" stroke-linecap="round" stroke-linejoin="round" /></svg>
							</button>
						</div>
					{/if}
				</div>

				<!-- Senha: um botao revela os campos -->
				<div class="border-t border-slate-100 pt-5">
					{#if showPasswordFields}
						<p class="mb-3 font-semibold text-slate-600">{m.change_password()}</p>
						<div class="space-y-3">
							<input
								type="password"
								bind:value={currentPassword}
								placeholder={m.current_password()}
								autocomplete="current-password"
								class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
							/>
							<input
								type="password"
								bind:value={newPassword}
								placeholder={m.new_password()}
								autocomplete="new-password"
								class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
							/>
							{#if passwordError}
								<p class="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{passwordError}</p>
							{/if}
							<div class="flex gap-2">
								<button
									type="button"
									onclick={() => (showPasswordFields = false)}
									class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
								>
									{m.cancel()}
								</button>
								<button
									type="button"
									disabled={passwordBusy || !currentPassword || !newPassword}
									onclick={changePassword}
									class="h-12 flex-1 rounded-2xl bg-emerald-600 font-semibold text-white active:bg-emerald-700 disabled:opacity-40"
								>
									{m.save()}
								</button>
							</div>
						</div>
					{:else}
						<button
							type="button"
							onclick={() => (showPasswordFields = true)}
							class="flex h-12 w-full items-center justify-center gap-2 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
						>
							<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" stroke-linecap="round" /></svg>
							{m.change_password()}
						</button>
					{/if}
				</div>
			</div>
		{/if}
	</section>

	<!-- MEUS DADOS -->
	<section class="overflow-hidden rounded-3xl bg-white shadow-sm">
		{@render groupHeader('data', m.section_my_data())}
		{#if openGroups.data}
			<div class="space-y-6 px-5 pb-5">
				<div class="grid grid-cols-2 gap-3">
					<div>
						<p class="mb-2 text-xs font-semibold text-slate-500">{m.first_name()}</p>
						<input
							type="text"
							bind:value={firstName}
							autocomplete="given-name"
							class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
						/>
					</div>
					<div>
						<p class="mb-2 text-xs font-semibold text-slate-500">{m.last_name()}</p>
						<input
							type="text"
							bind:value={lastName}
							autocomplete="family-name"
							class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
						/>
					</div>
				</div>
				<div>
					<div class="mb-2 flex items-baseline justify-between">
						<p class="text-xs font-semibold text-slate-500">{m.birthdate_label()}</p>
						{#if age !== null}
							<span class="text-sm font-bold text-emerald-700">{age} {m.years_old()}</span>
						{/if}
					</div>
					<input
						type="date"
						bind:value={birthdate}
						max={new Date().toISOString().slice(0, 10)}
						class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
					/>
				</div>
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
				{#if objective === 'lose_fat'}
					<div>
						<p class="mb-1 font-semibold text-slate-600">{m.cut_intensity_title()}</p>
						<p class="mb-3 text-xs text-slate-400">{m.cut_intensity_hint()}</p>
						<ChoiceChips
							bind:value={cutIntensity}
							options={[
								{ value: 'light', label: m.cut_light(), hint: m.cut_light_hint() },
								{ value: 'moderate', label: m.cut_moderate(), hint: m.cut_moderate_hint() },
								{ value: 'aggressive', label: m.cut_aggressive(), hint: m.cut_aggressive_hint() }
							]}
						/>
					</div>
				{/if}
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
			</div>
		{/if}
	</section>

	<!-- PREFERENCIAS -->
	<section class="overflow-hidden rounded-3xl bg-white shadow-sm">
		{@render groupHeader('preferences', m.section_preferences())}
		{#if openGroups.preferences}
			<div class="space-y-5 px-5 pb-5">
				<div>
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
				</div>
				<div class="border-t border-slate-100 pt-5">
					<p class="mb-3 font-semibold text-slate-600">{m.theme_label()}</p>
					<ChoiceChips
						columns={3}
						value={theme.pref}
						onselect={(v: ThemePref) => setTheme(v)}
						options={[
							{ value: 'light', label: m.theme_light() },
							{ value: 'dark', label: m.theme_dark() },
							{ value: 'system', label: m.theme_system() }
						]}
					/>
				</div>
			</div>
		{/if}
	</section>

	<!-- DADOS E PRIVACIDADE -->
	<section class="overflow-hidden rounded-3xl bg-white shadow-sm">
		{@render groupHeader('privacy', m.data_privacy())}
		{#if openGroups.privacy}
			<div class="space-y-3 px-5 pb-5">
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
			</div>
		{/if}
	</section>
</div>

<button
	type="button"
	onclick={logout}
	class="mt-4 h-12 w-full rounded-2xl border-2 border-slate-200 font-semibold text-slate-500 active:bg-slate-100"
>
	{m.logout()}
</button>
