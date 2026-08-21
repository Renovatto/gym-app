<script lang="ts">
	import './layout.css';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import favicon from '$lib/assets/favicon.svg';
	import TabBar from '$lib/components/TabBar.svelte';
	import FeedbackFab from '$lib/components/FeedbackFab.svelte';
	import Toast from '$lib/components/Toast.svelte';
	import CelebrationOverlay from '$lib/components/CelebrationOverlay.svelte';
	import TourOverlay from '$lib/components/TourOverlay.svelte';
	import NewsModal from '$lib/components/NewsModal.svelte';
	import { bootstrap, session } from '$lib/session.svelte';
	import { refreshSharingPending } from '$lib/sharing.svelte';
	import { refreshNews } from '$lib/news.svelte';
	import { initTheme } from '$lib/theme.svelte';
	import { tour } from '$lib/tour.svelte';

	let { children } = $props();

	initTheme();

	const PUBLIC_ROUTES = ['/login', '/registro', '/recuperar-senha', '/redefinir-senha'];
	const isPublic = $derived(PUBLIC_ROUTES.includes(page.url.pathname));

	// Telas de foco (sub-rotas de treino/dieta): escondem a barra de abas
	// para o usuário não sair sem querer no meio do fluxo.
	const TAB_ROUTES = ['/', '/treino', '/dieta', '/progresso', '/perfil'];
	const isFocusRoute = $derived(
		!TAB_ROUTES.includes(page.url.pathname) &&
			(page.url.pathname.startsWith('/treino/') || page.url.pathname.startsWith('/dieta/'))
	);

	bootstrap();

	// Sem polling (a API hiberna no plano gratuito): recontamos quando a pessoa volta
	// para o app, que e quando um convite novo teria chegado. Mesmo gatilho que o
	// cronometro de descanso ja usa para se re-sincronizar.
	$effect(() => {
		function onVisible(): void {
			if (document.visibilityState !== 'visible' || !session.user) return;
			void refreshSharingPending();
			void refreshNews();
		}
		document.addEventListener('visibilitychange', onVisible);
		return () => document.removeEventListener('visibilitychange', onVisible);
	});

	$effect(() => {
		if (!session.loaded) return;
		const path = page.url.pathname;
		if (!session.user) {
			if (!isPublic) goto('/login', { replaceState: true });
			return;
		}
		if (!session.user.has_profile) {
			if (path !== '/onboarding') goto('/onboarding', { replaceState: true });
			return;
		}
		if (isPublic || path === '/onboarding') goto('/', { replaceState: true });
	});

	const showTabBar = $derived(
		session.loaded &&
			session.user?.has_profile &&
			!isPublic &&
			!isFocusRoute &&
			page.url.pathname !== '/onboarding'
	);
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<Toast />
<CelebrationOverlay />
<TourOverlay />

<div class="min-h-dvh bg-slate-50 text-slate-900">
	{#if session.loaded || isPublic}
		<main class="mx-auto max-w-md px-4 pt-6 {showTabBar ? 'pb-24' : 'pb-8'}">
			{@render children()}
		</main>
		{#if showTabBar}
			<FeedbackFab />
			<TabBar />
			<!-- Fica junto da barra de abas de proposito: assim a novidade nunca interrompe
			     o onboarding, o login nem uma tela de foco (treino em andamento, por
			     exemplo). E espera o tutorial terminar, para nao ter duas coisas
			     explicando o app ao mesmo tempo. -->
			{#if !tour.active}
				<NewsModal />
			{/if}
		{/if}
	{:else}
		<div class="flex min-h-dvh items-center justify-center">
			<div
				class="h-10 w-10 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"
			></div>
		</div>
	{/if}
</div>
