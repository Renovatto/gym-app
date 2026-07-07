<script lang="ts">
	import { guideSections } from '$lib/guideContent';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	const sections = guideSections(getLocale());
</script>

<div class="mb-4 flex items-center gap-2">
	<a
		href="/perfil"
		aria-label={m.back()}
		class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
	>
		<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	</a>
	<h1 class="text-2xl font-bold">{m.guide_title()}</h1>
</div>

<div class="space-y-4">
	{#each sections as section (section.title)}
		<section class="rounded-3xl bg-white p-5 shadow-sm">
			<h2 class="mb-3 font-bold text-slate-900">{section.title}</h2>

			{#if section.kind === 'glossary'}
				<dl class="space-y-3">
					{#each section.terms as item (item.term)}
						<div>
							<dt class="text-sm font-bold text-emerald-700">{item.term}</dt>
							<dd class="text-sm text-slate-600">{item.definition}</dd>
						</div>
					{/each}
				</dl>
			{:else if section.kind === 'formulas'}
				<div class="space-y-3">
					{#each section.items as item (item.name)}
						<div class="rounded-2xl bg-slate-50 p-3">
							<p class="text-sm font-bold text-slate-800">{item.name}</p>
							<p class="mt-1 font-mono text-sm text-emerald-700">{item.formula}</p>
							<p class="mt-1 text-xs text-slate-500">{item.note}</p>
						</div>
					{/each}
				</div>
			{:else}
				{#if section.intro}
					<p class="mb-2 text-sm text-slate-600">{section.intro}</p>
				{/if}
				<ul class="space-y-2">
					{#each section.bullets as bullet (bullet)}
						<li class="flex gap-2 text-sm text-slate-600">
							<span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500"></span>
							<span>{bullet}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/each}
</div>
