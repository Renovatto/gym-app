<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { errorMessage } from '$lib/errors';

	let email = $state('');
	let sent = $state(false);
	let error = $state('');
	let busy = $state(false);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		error = '';
		busy = true;
		try {
			await api.forgotPassword(email.trim());
			sent = true;
		} catch (e) {
			error = errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR');
		} finally {
			busy = false;
		}
	}
</script>

<div class="flex min-h-[80dvh] flex-col justify-center">
	<h1 class="text-center text-2xl font-black tracking-tight">{m.forgot_password_title()}</h1>

	{#if sent}
		<div class="mt-8 rounded-3xl bg-emerald-50 p-6 text-center">
			<p class="text-4xl">📧</p>
			<p class="mt-3 font-semibold text-emerald-900">{m.forgot_password_sent()}</p>
		</div>
		<a href="/login" class="mt-6 block text-center font-semibold text-emerald-700">
			{m.back_to_login()}
		</a>
	{:else}
		<p class="mt-2 text-center text-slate-500">{m.forgot_password_hint()}</p>
		<form class="mt-8 space-y-3" onsubmit={submit}>
			<input
				type="email"
				bind:value={email}
				required
				placeholder={m.email()}
				autocomplete="email"
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
				{m.forgot_password_button()}
			</button>
		</form>
		<a href="/login" class="mt-6 block text-center font-semibold text-emerald-700">
			{m.back_to_login()}
		</a>
	{/if}
</div>
