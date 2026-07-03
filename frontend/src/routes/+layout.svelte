<script lang="ts">
	import './layout.css';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import favicon from '$lib/assets/favicon.svg';
	import TabBar from '$lib/components/TabBar.svelte';
	import { bootstrap, session } from '$lib/session.svelte';

	let { children } = $props();

	const PUBLIC_ROUTES = ['/login', '/registro'];
	const isPublic = $derived(PUBLIC_ROUTES.includes(page.url.pathname));

	bootstrap();

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
		session.loaded && session.user?.has_profile && !isPublic && page.url.pathname !== '/onboarding'
	);
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="min-h-dvh bg-slate-50 text-slate-900">
	{#if session.loaded || isPublic}
		<main class="mx-auto max-w-md px-4 pt-6 {showTabBar ? 'pb-24' : 'pb-8'}">
			{@render children()}
		</main>
		{#if showTabBar}
			<TabBar />
		{/if}
	{:else}
		<div class="flex min-h-dvh items-center justify-center">
			<div
				class="h-10 w-10 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"
			></div>
		</div>
	{/if}
</div>
