<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api';
	import { signUp } from '$lib/session.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';
	import { errorMessage, toBackendLocale } from '$lib/errors';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		error = '';
		if (password.length < 8) {
			error = errorMessage('PASSWORD_TOO_SHORT');
			return;
		}
		busy = true;
		try {
			await signUp(email, password, toBackendLocale(getLocale()));
			await goto('/onboarding');
		} catch (e) {
			error = errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR');
		} finally {
			busy = false;
		}
	}
</script>

<div class="flex min-h-[80dvh] flex-col justify-center">
	<h1 class="text-center text-3xl font-black tracking-tight">{m.create_account()}</h1>

	<form class="mt-10 space-y-3" onsubmit={submit}>
		<input
			type="email"
			bind:value={email}
			required
			placeholder={m.email()}
			autocomplete="email"
			class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-base outline-none focus:border-emerald-600"
		/>
		<input
			type="password"
			bind:value={password}
			required
			placeholder={m.password_hint()}
			autocomplete="new-password"
			class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-base outline-none focus:border-emerald-600"
		/>
		{#if error}
			<p class="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</p>
		{/if}
		<button
			type="submit"
			disabled={busy}
			class="h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-50"
		>
			{m.register()}
		</button>
	</form>

	<a href="/login" class="mt-6 block text-center font-semibold text-emerald-700">
		{m.have_account()}
	</a>
</div>
