<script lang="ts">
	import '../app.css';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import Toast from '$lib/components/Toast.svelte';
	import { api } from '$lib/api';
	import { loadSession, logout, session } from '$lib/session.svelte';
	import { initTheme, themeState, toggleTheme } from '$lib/theme.svelte';
	import { initials } from '$lib/format';

	let { children } = $props();

	let railOpen = $state(false);
	let unreadFeedback = $state(0);

	// Rotulo do topo por rota: uma fonte so, para o titulo nunca discordar do menu.
	const PAGES: Record<string, { title: string; sub: string }> = {
		'': { title: 'Dashboard', sub: 'Visao geral de uso, derivada do banco' },
		usuarios: { title: 'Usuarios', sub: 'Consulta paginada no servidor' },
		relatorios: { title: 'Relatorios', sub: 'Agregados de uso por periodo' },
		feedbacks: { title: 'Feedbacks', sub: 'Mensagens enviadas pelo app' },
		novidades: { title: 'Novidades', sub: 'O que os usuarios veem no app' }
	};

	const current = $derived(page.url.pathname.replace(base, '').replace(/^\/|\/$/g, ''));
	const meta = $derived(PAGES[current] ?? PAGES['']);
	const isLogin = $derived(current === 'login');

	$effect(() => {
		initTheme();
		void loadSession();
	});

	// Guard: quem nao esta logado vai para o login; quem esta logado mas nao e
	// admin ve a recusa em vez de uma tela quebrada de 403 em cada requisicao.
	$effect(() => {
		if (!session.ready || isLogin) return;
		if (!session.user) void goto(`${base}/login`);
	});

	// Contador de nao lidos no menu. Roda uma vez por sessao de admin valido.
	$effect(() => {
		if (!session.user?.is_admin) return;
		void api
			.listFeedback()
			.then((reports) => {
				unreadFeedback = reports.filter((report) => !report.read).length;
			})
			.catch(() => {
				// Contador e enfeite: se falhar, o menu so fica sem o numero.
			});
	});

	function sair(): void {
		logout();
		void goto(`${base}/login`);
	}

	function isCurrent(path: string): 'page' | undefined {
		return current === path ? 'page' : undefined;
	}
</script>

<svelte:head><title>Admin GymApp</title></svelte:head>

{#if isLogin}
	{@render children()}
{:else if !session.ready}
	<div class="boot mono">carregando…</div>
{:else if session.user && !session.user.is_admin}
	<div class="boot-box">
		<div class="card empty" style="max-width:460px">
			<div class="empty-mark">
				<svg
					width="20"
					height="20"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
				>
					<rect x="4" y="10" width="16" height="10" rx="2.4" />
					<path d="M8 10V7.5a4 4 0 0 1 8 0V10" />
				</svg>
			</div>
			<h3>Sem acesso administrativo</h3>
			<p>
				A conta <b>{session.user.email}</b> nao esta na allowlist do servidor. Peca para incluir o
				e-mail em GYMAPP_ADMIN_EMAILS ou entre com outra conta.
			</p>
			<button class="btn" type="button" onclick={sair}>Trocar de conta</button>
		</div>
	</div>
{:else if session.user}
	<div class="shell">
		<div
			class="rail-scrim"
			class:is-open={railOpen}
			onclick={() => (railOpen = false)}
			onkeydown={(event) => event.key === 'Escape' && (railOpen = false)}
			role="presentation"
		></div>

		<aside class="rail" class:is-open={railOpen}>
			<div class="brand">
				<div class="brand-mark" aria-hidden="true">
					<svg
						width="18"
						height="18"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2.1"
						stroke-linecap="round"
					>
						<path d="M4 9v6M20 9v6M7 6v12M17 6v12M7 12h10" />
					</svg>
				</div>
				<div>
					<div class="brand-name">GymApp</div>
					<div class="brand-sub">Console admin</div>
				</div>
			</div>

			<nav class="nav" aria-label="Secoes do painel">
				<a
					class="nav-item"
					href="{base}/"
					aria-current={isCurrent('')}
					onclick={() => (railOpen = false)}
				>
					<svg
						width="17"
						height="17"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.9"
						stroke-linecap="round"
						stroke-linejoin="round"><path d="M3 13h5l2 5 4-11 2 6h5" /></svg
					>
					Dashboard
				</a>
				<a
					class="nav-item"
					href="{base}/usuarios"
					aria-current={isCurrent('usuarios')}
					onclick={() => (railOpen = false)}
				>
					<svg
						width="17"
						height="17"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.9"
						stroke-linecap="round"
						stroke-linejoin="round"
						><circle cx="9" cy="8" r="3.2" /><path d="M3.5 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5" /><path
							d="M16 6.2a3 3 0 0 1 0 5.6M17.5 14.4c2 .7 3.2 2.4 3.2 4.6"
						/></svg
					>
					Usuarios
				</a>
				<a
					class="nav-item"
					href="{base}/relatorios"
					aria-current={isCurrent('relatorios')}
					onclick={() => (railOpen = false)}
				>
					<svg
						width="17"
						height="17"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.9"
						stroke-linecap="round"
						stroke-linejoin="round"
						><path d="M4 20V5" /><path d="M4 20h16" /><rect
							x="7"
							y="11"
							width="3.2"
							height="6"
							rx="1"
						/><rect x="13.5" y="7" width="3.2" height="10" rx="1" /></svg
					>
					Relatorios
				</a>
				<a
					class="nav-item"
					href="{base}/feedbacks"
					aria-current={isCurrent('feedbacks')}
					onclick={() => (railOpen = false)}
				>
					<svg
						width="17"
						height="17"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.9"
						stroke-linecap="round"
						stroke-linejoin="round"
						><path
							d="M20 14.5a2.5 2.5 0 0 1-2.5 2.5H9l-4 3V6.5A2.5 2.5 0 0 1 7.5 4h10A2.5 2.5 0 0 1 20 6.5z"
						/></svg
					>
					Feedbacks
					{#if unreadFeedback > 0}
						<span class="nav-count is-alert mono">{unreadFeedback}</span>
					{/if}
				</a>
				<a
					class="nav-item"
					href="{base}/novidades"
					aria-current={isCurrent('novidades')}
					onclick={() => (railOpen = false)}
				>
					<svg
						width="17"
						height="17"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.9"
						stroke-linecap="round"
						stroke-linejoin="round"
						><path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path
							d="M13.7 21a2 2 0 0 1-3.4 0"
						/></svg
					>
					Novidades
				</a>
			</nav>

			<div class="rail-foot">
				<div class="rail-user">
					<div class="avatar" aria-hidden="true">{initials(null, session.user.email)}</div>
					<div style="min-width:0;flex:1">
						<div style="font-size:13px;font-weight:650">Administrador</div>
						<div class="mono" style="font-size:10.5px;color:var(--ink-3);overflow:hidden;text-overflow:ellipsis">
							{session.user.email}
						</div>
					</div>
				</div>
				<button class="btn btn-ghost btn-sm" type="button" onclick={sair}>Sair</button>
			</div>
		</aside>

		<div class="work">
			<header class="topbar">
				<button
					class="btn btn-ghost burger"
					type="button"
					aria-label="Abrir navegacao"
					onclick={() => (railOpen = !railOpen)}
				>
					<svg
						width="18"
						height="18"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16" /></svg
					>
				</button>
				<div>
					<div class="topbar-title">{meta.title}</div>
					<div class="topbar-sub">{meta.sub}</div>
				</div>
				<div class="topbar-tools">
					<button
						class="btn btn-ghost"
						type="button"
						onclick={toggleTheme}
						aria-label="Alternar tema"
					>
						{#if themeState.current === 'dark'}
							<svg
								width="16"
								height="16"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="1.9"
								stroke-linecap="round"
								><circle cx="12" cy="12" r="4" /><path
									d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"
								/></svg
							>
							<span class="theme-text">Tema claro</span>
						{:else}
							<svg
								width="16"
								height="16"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="1.9"
								stroke-linecap="round"
								stroke-linejoin="round"
								><path d="M20 14.5A8.2 8.2 0 0 1 9.5 4 8.3 8.3 0 1 0 20 14.5z" /></svg
							>
							<span class="theme-text">Tema escuro</span>
						{/if}
					</button>
				</div>
			</header>

			<main class="content">{@render children()}</main>
		</div>
	</div>
{/if}

<Toast />

<style>
	.boot {
		display: grid;
		place-items: center;
		min-height: 100vh;
		color: var(--ink-3);
		font-size: 13px;
	}
	.boot-box {
		display: grid;
		place-items: center;
		min-height: 100vh;
		padding: 24px;
	}
	.burger {
		display: none;
	}
	@media (max-width: 900px) {
		.burger {
			display: inline-flex;
		}
	}
	@media (max-width: 620px) {
		/* No celular o botao de tema fica so com o icone: o rotulo empurraria o titulo. */
		.theme-text {
			display: none;
		}
	}
</style>
