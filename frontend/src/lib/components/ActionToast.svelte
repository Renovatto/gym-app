<script lang="ts">
	import { tick } from 'svelte';
	import { ApiError } from '$lib/api';
	import { errorMessage } from '$lib/errors';
	import { dismissActionToast, type ActionToastState } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';

	let { toast }: { toast: ActionToastState } = $props();
	let remaining = $state(0);
	let confirming = $state(false);
	let busy = $state(false);
	let error = $state('');
	let hovered = $state(false);
	let focused = $state(false);
	let confirmButton = $state<HTMLButtonElement>();
	let undoButton = $state<HTMLButtonElement>();
	const paused = $derived(confirming || busy || hovered || focused);
	// O contador arredonda para cima para nunca mostrar zero antes do encerramento.
	const seconds = $derived(Math.ceil(remaining / 1000));
	// Barra restante = tempo disponivel dividido pela duracao total do aviso.
	const remainingShare = $derived(remaining / toast.duration);

	$effect(() => {
		let lastTick = performance.now();
		remaining = toast.duration;
		const timer = setInterval(() => {
			const now = performance.now();
			// Mede tempo decorrido real; a pausa conserva o saldo da opcao de desfazer.
			const elapsed = now - lastTick;
			lastTick = now;
			if (paused || document.hidden) return;
			remaining = Math.max(0, remaining - elapsed);
			if (remaining === 0) dismissActionToast(toast.id);
		}, 100);
		return () => clearInterval(timer);
	});

	async function askUndo(): Promise<void> {
		confirming = true;
		error = '';
		await tick();
		confirmButton?.focus();
	}

	async function cancelUndo(): Promise<void> {
		confirming = false;
		error = '';
		await tick();
		undoButton?.focus();
	}

	async function confirmUndo(): Promise<void> {
		if (busy) return;
		busy = true;
		error = '';
		try {
			await toast.action.run();
			dismissActionToast(toast.id);
		} catch (cause) {
			error = errorMessage(cause instanceof ApiError ? cause.code : 'GENERIC_ERROR');
		} finally {
			busy = false;
		}
	}
</script>

<!-- A regiao tem nome acessivel; apenas a mensagem inicial e anunciada, sem ler cada segundo. -->
<section
	data-testid="tomorrow-toast"
	aria-label={toast.title}
	onmouseenter={() => (hovered = true)}
	onmouseleave={() => (hovered = false)}
	onfocusin={() => (focused = true)}
	onfocusout={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) focused = false; }}
	class="action-toast pointer-events-auto w-full max-w-lg shrink-0 rounded-2xl border border-amber-400 border-l-[6px] border-l-orange-500 bg-amber-50 p-4 text-amber-900 shadow-xl"
>
	<div class="flex items-start gap-3">
		<span aria-hidden="true" class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-orange-600 text-xl font-bold text-white">↗</span>
		<div class="min-w-0 flex-1 break-words" role="status" aria-live="polite">
			<p class="font-extrabold">{toast.title}</p>
			<p class="mt-1 text-sm">{toast.message}</p>
		</div>
		<button type="button" disabled={busy} onclick={() => dismissActionToast(toast.id)} aria-label={m.close()} class="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-xl focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">×</button>
	</div>
	<div class="mt-3 flex items-center gap-3" aria-hidden="true">
		<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-amber-200">
			<div class="timer-bar h-full origin-left rounded-full bg-orange-700" style:transform="scaleX({remainingShare})"></div>
		</div>
		<span data-testid="undo-countdown" class="min-w-10 text-right text-xs font-bold tabular-nums">{m.diary_undo_seconds({ seconds })}</span>
	</div>
	{#if confirming}
		<div class="mt-3 rounded-xl border border-amber-300 bg-white/70 p-3" role="group" aria-label={toast.action.confirmation}>
			<p class="font-bold">{toast.action.confirmation}</p>
			<p class="mt-1 text-sm">{toast.action.description}</p>
			{#if error}<p role="alert" class="mt-2 text-sm font-semibold text-red-700">{error}</p>{/if}
			<div class="mt-3 flex flex-wrap gap-2">
				<button bind:this={confirmButton} type="button" disabled={busy} onclick={confirmUndo} class="min-h-11 rounded-xl bg-red-700 px-3 py-2 text-sm font-bold text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">{busy ? m.diary_undo_removing() : m.diary_undo_confirm()}</button>
				<button type="button" disabled={busy} onclick={cancelUndo} class="min-h-11 rounded-xl border border-amber-300 px-3 py-2 text-sm font-bold focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">{m.cancel()}</button>
			</div>
		</div>
	{:else}
		<div class="mt-2 flex items-center gap-3">
			<button bind:this={undoButton} type="button" onclick={askUndo} class="min-h-11 rounded-lg px-2 text-sm font-extrabold text-orange-800 underline decoration-2 underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2">{toast.action.label}</button>
			<p class="ml-auto text-xs">{m.diary_undo_expires()}</p>
		</div>
	{/if}
</section>

<style>
	.action-toast { animation: appear 220ms ease-out; }
	.timer-bar { transition: transform 100ms linear; }
	@keyframes appear { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
	@media (prefers-reduced-motion: reduce) {
		.action-toast { animation: none; }
		.timer-bar { transition: none; }
	}
</style>
