<script lang="ts">
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { login, session } from '$lib/session.svelte';
	import { loginErrorMessage } from '$lib/format';

	let email = $state('');
	let password = $state('');
	let busy = $state(false);
	let erro = $state('');
	let senhaVisivel = $state(false);

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
			erro = loginErrorMessage(error);
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
				<!-- O type vem por spread porque o Svelte proibe type dinamico junto com
				     bind:value; o spread entrega o mesmo atributo sem esbarrar na regra. -->
				<input
					{...{ type: senhaVisivel ? 'text' : 'password' }}
					bind:value={password}
					required
					autocomplete="current-password"
					style="width:100%"
				/>
				<button
					type="button"
					class="olho"
					onclick={() => (senhaVisivel = !senhaVisivel)}
					aria-label={senhaVisivel ? 'Ocultar senha' : 'Mostrar senha'}
				>
					<svg
						width="17"
						height="17"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						{#if senhaVisivel}
							<path
								d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.4 5.2A9.5 9.5 0 0112 5c5 0 9 4.5 9 7a12 12 0 01-2.4 3.3M6.2 6.7C3.9 8.2 3 10.4 3 12c0 2.5 4 7 9 7a9.6 9.6 0 004.2-.95"
							/>
						{:else}
							<path d="M3 12c0-2.5 4-7 9-7s9 4.5 9 7-4 7-9 7-9-4.5-9-7z" />
							<circle cx="12" cy="12" r="2.6" />
						{/if}
					</svg>
				</button>
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
	/* Fica dentro do .field (que ja e flex), entao nao precisa de posicionamento
	   absoluto: e so o ultimo item da linha, com a cor apagada dos icones. */
	.olho {
		display: grid;
		place-items: center;
		flex: none;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--ink-3);
		cursor: pointer;
	}
	.olho:hover {
		color: var(--ink);
	}
	.erro {
		font-size: 13px;
		color: var(--critical);
		background: var(--critical-wash);
		border-radius: var(--radius-sm);
		padding: 9px 11px;
	}
</style>
