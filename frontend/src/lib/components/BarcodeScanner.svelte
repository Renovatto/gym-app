<script lang="ts">
	import { m } from '$lib/paraglide/messages';
	import Spinner from '$lib/components/Spinner.svelte';

	let { onread, onclose }: { onread: (code: string) => void; onclose: () => void } = $props();

	// Motivos de falha separados porque a acao da pessoa muda em cada um: permissao
	// ela resolve nos ajustes, conexao insegura so o endereco https resolve, e
	// aparelho sem camera nao tem solucao - so restaria digitar.
	type Falha = 'permissao' | 'insegura' | 'indisponivel';

	let video = $state<HTMLVideoElement | null>(null);
	let falha = $state<Falha | null>(null);
	let iniciando = $state(true);

	$effect(() => {
		const elemento = video;
		if (!elemento) return;

		let cancelado = false;
		let parar: (() => void) | null = null;

		void (async () => {
			// A camera exige contexto seguro (https ou localhost). Pelo IP da rede em
			// http o navegador nem oferece a API - e o caso mais comum de "nao abre"
			// durante o desenvolvimento, entao ele tem mensagem propria.
			if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
				falha = 'insegura';
				iniciando = false;
				return;
			}

			try {
				// import dinamico: a biblioteca de leitura (centenas de KB) so e baixada
				// quando alguem abre o leitor, e nao no carregamento do app.
				const { BrowserMultiFormatReader } = await import('@zxing/browser');
				const { BarcodeFormat, DecodeHintType } = await import('@zxing/library');

				// So os formatos de produto: menos formatos, leitura mais rapida e
				// menos chance de ler errado algo que nem e codigo de barras.
				const hints = new Map();
				hints.set(DecodeHintType.POSSIBLE_FORMATS, [
					BarcodeFormat.EAN_13,
					BarcodeFormat.EAN_8,
					BarcodeFormat.UPC_A,
					BarcodeFormat.UPC_E
				]);

				const leitor = new BrowserMultiFormatReader(hints);
				const controls = await leitor.decodeFromConstraints(
					// ideal e nao exact: se o aparelho nao tiver camera traseira, ele usa
					// a que tiver em vez de falhar.
					{ video: { facingMode: { ideal: 'environment' } } },
					elemento,
					(resultado) => {
						if (cancelado || !resultado) return;
						cancelado = true;
						controls.stop();
						onread(resultado.getText());
					}
				);
				parar = () => controls.stop();
				if (cancelado) controls.stop();
				iniciando = false;
			} catch (erro) {
				const nome = erro instanceof DOMException ? erro.name : '';
				falha = nome === 'NotAllowedError' || nome === 'SecurityError' ? 'permissao' : 'indisponivel';
				iniciando = false;
			}
		})();

		return () => {
			cancelado = true;
			parar?.();
		};
	});
</script>

<div class="fixed inset-0 z-50 flex flex-col bg-ink">
	<div
		class="flex items-center justify-between px-4 pt-[calc(env(safe-area-inset-top)+0.75rem)] pb-3"
	>
		<p class="text-sm font-bold text-white">{m.scan_title()}</p>
		<button
			type="button"
			onclick={onclose}
			aria-label={m.cancel()}
			class="grid h-9 w-9 place-items-center rounded-full text-white/70 active:bg-white/10"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
		</button>
	</div>

	<div class="relative flex-1 overflow-hidden">
		<!-- svelte-ignore a11y_media_has_caption -->
		<video bind:this={video} class="h-full w-full object-cover" playsinline muted autoplay></video>

		{#if !falha}
			<!-- Janela de mira: nao recorta nada, so diz onde encostar o codigo. -->
			<div class="pointer-events-none absolute inset-0 grid place-items-center">
				<div class="h-28 w-4/5 max-w-xs rounded-2xl border-2 border-emerald-400/90 shadow-[0_0_0_9999px_rgba(15,23,42,0.55)]"></div>
			</div>
		{/if}

		{#if iniciando && !falha}
			<div class="absolute inset-0 grid place-items-center">
				<Spinner class="h-7 w-7 text-white" />
			</div>
		{/if}

		{#if falha}
			<div class="absolute inset-0 grid place-items-center px-6">
				<p class="max-w-xs text-center text-sm font-semibold text-white">
					{#if falha === 'permissao'}{m.scan_error_permission()}
					{:else if falha === 'insegura'}{m.scan_error_insecure()}
					{:else}{m.scan_error_unavailable()}{/if}
				</p>
			</div>
		{/if}
	</div>

	<p class="px-6 pt-4 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] text-center text-xs text-white/60">
		{m.scan_hint()}
	</p>
</div>
