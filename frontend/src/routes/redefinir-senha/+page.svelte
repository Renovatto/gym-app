<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { errorMessage } from '$lib/errors';

	const token = $derived(page.url.searchParams.get('token') ?? '');

	let newPassword = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		error = '';
		if (newPassword.length < 8) {
			error = errorMessage('PASSWORD_TOO_SHORT');
			return;
		}
		busy = true;
		try {
			await api.resetPassword(token, newPassword);
			showToast(m.password_changed());
			await goto('/login');
		} catch (e) {
			error = errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR');
		} finally {
			busy = false;
		}
	}
</script>

<div class="flex min-h-[80dvh] flex-col justify-center">
	<h1 class="text-center text-2xl font-black tracking-tight">{m.reset_password_title()}</h1>

	{#if !token}
		<p class="mt-8 rounded-xl bg-red-50 px-4 py-3 text-center text-sm font-medium text-red-700">
			{m.reset_password_no_token()}
		</p>
		<a href="/recuperar-senha" class="mt-6 block text-center font-semibold text-emerald-700">
			{m.forgot_password_button()}
		</a>
	{:else}
		<form class="mt-8 space-y-3" onsubmit={submit}>
			<input
				type="password"
				bind:value={newPassword}
				required
				placeholder={m.new_password()}
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
				{m.reset_password_button()}
			</button>
		</form>
	{/if}
</div>
