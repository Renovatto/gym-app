<script lang="ts">
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api';
	import { login, session } from '$lib/session.svelte';
	import { errorMessage } from '$lib/format';

	let email = $state('');
	let password = $state('');
	let busy = $state(false);
	let erro = $state('');

	// Quem ja tem sessao valida nao precisa ver o formulario de novo.
	$effect(() => {
		if (session.ready && session.user) void goto(`${base}/`);
	});

	async function entrar(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		busy = true;
		erro = '';
		try {
			await login(email.trim(), password);
			await goto(`${base}/`);
		} catch (error) {
			erro = errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR');
		} finally {
			busy = false;
		}
	}
</script>

<div class="wrap">
	<form class="card box" onsubmit={entrar}>
		<div class="brand" style="padding:0">
			<div class="brand-mark" aria-hidden="true">
				<svg
					width="18"
					height="18"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2.1"
					stroke-linecap="round"><path d="M4 9v6M20 9v6M7 6v12M17 6v12M7 12h10" /></svg
				>
			</div>
			<div>
				<div class="brand-name">GymApp</div>
				<div class="brand-sub">Console admin</div>
			</div>
		</div>

		<p class="hint">
			Entre com a conta do app. O acesso administrativo depende do e-mail estar na allowlist do
			servidor.
		</p>

		<label class="stack-field">
			<span class="eyebrow">E-mail</span>
			<span class="field" style="width:100%">
				<input type="email" bind:value={email} required autocomplete="username" style="width:100%" />
			</span>
		</label>

		<label class="stack-field">
			<span class="eyebrow">Senha</span>
			<span class="field" style="width:100%">
				<input
					type="password"
					bind:value={password}
					required
					autocomplete="current-password"
					style="width:100%"
				/>
			</span>
		</label>

		{#if erro}
			<p class="erro">{erro}</p>
		{/if}

		<button class="btn btn-accent" type="submit" disabled={busy} style="justify-content:center">
			{busy ? 'Entrando…' : 'Entrar'}
		</button>
	</form>
</div>

<style>
	.wrap {
		display: grid;
		place-items: center;
		min-height: 100vh;
		padding: 24px;
	}
	.box {
		width: min(400px, 100%);
		padding: 26px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.hint {
		font-size: 12.5px;
		color: var(--ink-3);
		line-height: 1.55;
	}
	.stack-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.erro {
		font-size: 13px;
		color: var(--critical);
		background: var(--critical-wash);
		border-radius: var(--radius-sm);
		padding: 9px 11px;
	}
</style>
