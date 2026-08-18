<script lang="ts">
	import { goto } from '$app/navigation';
	import Spinner from '$lib/components/Spinner.svelte';
	import { signIn } from '$lib/session.svelte';
	import { m } from '$lib/paraglide/messages';
	import { loginErrorMessage } from '$lib/errors';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);
	let showPassword = $state(false);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		error = '';
		busy = true;
		try {
			await signIn(email, password);
			await goto('/');
		} catch (e) {
			error = loginErrorMessage(e);
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
		<div class="relative">
			<!-- O type vem por spread porque o Svelte proibe type dinamico junto com
			     bind:value; o spread entrega o mesmo atributo sem esbarrar na regra. -->
			<input
				{...{ type: showPassword ? 'text' : 'password' }}
				bind:value={password}
				required
				placeholder={m.password()}
				autocomplete="current-password"
				class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 pr-14 text-base outline-none focus:border-emerald-600"
			/>
			<button
				type="button"
				onclick={() => (showPassword = !showPassword)}
				aria-label={showPassword ? m.hide_password() : m.show_password()}
				class="absolute top-1/2 right-2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-xl text-slate-400 active:bg-slate-100"
			>
				<svg
					viewBox="0 0 24 24"
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				>
					{#if showPassword}
						<path
							d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.4 5.2A9.5 9.5 0 0112 5c5 0 9 4.5 9 7a12 12 0 01-2.4 3.3M6.2 6.7C3.9 8.2 3 10.4 3 12c0 2.5 4 7 9 7a9.6 9.6 0 004.2-.95"
						/>
					{:else}
						<path d="M3 12c0-2.5 4-7 9-7s9 4.5 9 7-4 7-9 7-9-4.5-9-7z" />
						<circle cx="12" cy="12" r="2.6" />
					{/if}
				</svg>
			</button>
		</div>
		{#if error}
			<p class="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</p>
		{/if}
		<button
			type="submit"
			disabled={busy}
			class="flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-60"
		>
			{#if busy}<Spinner /> {m.signing_in()}{:else}{m.login()}{/if}
		</button>
	</form>

	<a href="/recuperar-senha" class="mt-4 block text-center text-sm font-semibold text-slate-500">
		{m.forgot_password_link()}
	</a>
	<a href="/registro" class="mt-4 block text-center font-semibold text-emerald-700">
		{m.no_account()}
	</a>
</div>
