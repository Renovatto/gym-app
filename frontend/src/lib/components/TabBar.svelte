<script lang="ts">
	import { page } from '$app/state';
	import { session } from '$lib/session.svelte';
	import { m } from '$lib/paraglide/messages';

	const iconPaths: Record<string, string> = {
		home: 'M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10',
		workout:
			'M6.5 6.5v11M17.5 6.5v11M3 9.5v5M21 9.5v5M6.5 12h11',
		diet: 'M12 20.94c1.5 0 2.75 1.06 4 1.06 3 0 6-8 6-12.22A4.91 4.91 0 0 0 17 5c-2.22 0-4 1.44-5 2-1-.56-2.78-2-5-2a4.9 4.9 0 0 0-5 4.78C2 14 5 22 8 22c1.25 0 2.5-1.06 4-1.06Z M10 2c1 .5 2 2 2 5',
		progress: 'M3 21h18M7 17V9M12 17V5M17 17v-7',
		profile:
			'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 3.6-6 8-6s8 2 8 6'
	};

	const tabs = $derived([
		{ href: '/', icon: 'home', label: m.tab_today() },
		{ href: '/treino', icon: 'workout', label: m.tab_workout() },
		...(session.profile?.diet_enabled ? [{ href: '/dieta', icon: 'diet', label: m.tab_diet() }] : []),
		{ href: '/progresso', icon: 'progress', label: m.tab_progress() },
		{ href: '/perfil', icon: 'profile', label: m.tab_profile() }
	]);
</script>

<nav
	class="fixed inset-x-0 bottom-0 z-10 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)]"
>
	<div class="mx-auto flex max-w-md">
		{#each tabs as tab (tab.href)}
			{@const active = page.url.pathname === tab.href}
			<a
				href={tab.href}
				class="flex min-h-16 flex-1 flex-col items-center justify-center gap-1 text-xs font-medium
					{active ? 'text-emerald-600' : 'text-slate-400'}"
			>
				<svg
					viewBox="0 0 24 24"
					class="h-6 w-6"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				>
					<path d={iconPaths[tab.icon]} />
				</svg>
				{tab.label}
			</a>
		{/each}
	</div>
</nav>
