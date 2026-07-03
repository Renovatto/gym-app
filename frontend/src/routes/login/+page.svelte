<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api';
	import { signIn } from '$lib/session.svelte';
	import { m } from '$lib/paraglide/messages';
	import { errorMessage } from '$lib/errors';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		error = '';
		busy = true;
		try {
			await signIn(email, password);
			await goto('/');
		} catch (e) {
			error = errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR');
		} finally {
			busy = false;
		}
	}
</script>

<div class="flex min-h-[80dvh] flex-col justify-center">
	<h1 class="text-center text-4xl font-black tracking-tight text-emerald-600">
		{m.app_name()}
	</h1>
	<p class="mt-2 text-center text-slate-500">{m.tagline()}</p>

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
			placeholder={m.password()}
			autocomplete="current-password"
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
			{m.login()}
		</button>
	</form>

	<a href="/registro" class="mt-6 block text-center font-semibold text-emerald-700">
		{m.no_account()}
	</a>
</div>
