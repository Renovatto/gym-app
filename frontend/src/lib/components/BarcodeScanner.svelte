<script lang="ts">
	import { m } from '$lib/paraglide/messages';
	import Spinner from '$lib/components/Spinner.svelte';

	let { onread, onclose }: { onread: (code: string) => void; onclose: () => void } = $props();

	// Motivos de falha separados porque a acao da pessoa muda em cada um: permissao
	// ela resolve nos ajustes, conexao insegura so o endereco https resolve, e
	// aparelho sem camera nao tem solucao - so restaria digitar.
	type Falha = 'permissao' | 'insegura' | 'indisponivel';

	// A cada este intervalo uma foto do video vira uma tentativa de leitura. Mais
	// rapido que isso so gasta bateria: o codigo nao entra e sai de quadro em 150ms.
	const INTERVALO_MS = 150;
	// Se o video nao comecar a dar quadros nesse tempo, alguma coisa travou e e
	// melhor dizer isso do que deixar o spinner girando para sempre.
	const ESPERA_MAXIMA_MS = 8000;

	let video = $state<HTMLVideoElement | null>(null);
	let falha = $state<Falha | null>(null);
	let iniciando = $state(true);

	$effect(() => {
		const elemento = video;
		if (!elemento) return;

		let cancelado = false;
		let stream: MediaStream | null = null;
		let timer: ReturnType<typeof setInterval> | null = null;

		function encerrar(): void {
			cancelado = true;
			if (timer) clearInterval(timer);
			stream?.getTracks().forEach((t) => t.stop());
		}

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
				// ideal e nao exact: se o aparelho nao tiver camera traseira, usa a que
				// tiver em vez de falhar.
				stream = await navigator.mediaDevices.getUserMedia({
					video: { facingMode: { ideal: 'environment' } }
				});
				if (cancelado) return encerrar();

				// Estas TRES coisas sao propriedade, nao atributo: o Safari do iPhone so
				// toca um video inline sem gesto se elas estiverem no objeto. Escritas
				// como atributo no HTML (o que o Svelte faz) ele ignora, a reproducao
				// nunca comeca, e o resultado e exatamente uma tela preta com a camera
				// ligada - o sintoma que isso aqui conserta.
				elemento.muted = true;
				elemento.playsInline = true;
				elemento.srcObject = stream;
				await elemento.play();

				// import dinamico: a biblioteca de leitura (centenas de KB) so e baixada
				// quando alguem abre o leitor, e nao no carregamento do app.
				const { BarcodeFormat, BinaryBitmap, DecodeHintType, HybridBinarizer, MultiFormatReader, RGBLuminanceSource } =
					await import('@zxing/library');
				if (cancelado) return encerrar();

				// So os formatos de produto: menos formatos, leitura mais rapida e menos
				// chance de ler errado algo que nem e codigo de barras.
				const hints = new Map();
				hints.set(DecodeHintType.POSSIBLE_FORMATS, [
					BarcodeFormat.EAN_13,
					BarcodeFormat.EAN_8,
					BarcodeFormat.UPC_A,
					BarcodeFormat.UPC_E
				]);
				const leitor = new MultiFormatReader();
				leitor.setHints(hints);

				const tela = document.createElement('canvas');
				const pincel = tela.getContext('2d', { willReadFrequently: true });
				if (!pincel) {
					falha = 'indisponivel';
					iniciando = false;
					return encerrar();
				}

				const comecou = Date.now();

				timer = setInterval(() => {
					if (cancelado) return;

					const largura = elemento.videoWidth;
					const altura = elemento.videoHeight;
					if (!largura || !altura) {
						if (Date.now() - comecou > ESPERA_MAXIMA_MS) {
							falha = 'indisponivel';
							iniciando = false;
							encerrar();
						}
						return;
					}
					iniciando = false;

					// Le so a faixa central do quadro, a mesma area da mira: e onde a
					// pessoa encosta o codigo, e olhar menos pixel deixa a leitura rapida
					// o bastante para rodar a cada 150ms sem esquentar o aparelho.
					const faixaAltura = Math.round(altura * 0.4);
					const topo = Math.round((altura - faixaAltura) / 2);
					tela.width = largura;
					tela.height = faixaAltura;
					pincel.drawImage(elemento, 0, topo, largura, faixaAltura, 0, 0, largura, faixaAltura);

					const { data } = pincel.getImageData(0, 0, largura, faixaAltura);
					// RGBA -> luminancia (a formula padrao de brilho percebido). O leitor
					// trabalha em tons de cinza; passar o quadro colorido so daria trabalho
					// a mais para ele fazer a mesma conta.
					const cinza = new Uint8ClampedArray(largura * faixaAltura);
					for (let i = 0, p = 0; i < cinza.length; i++, p += 4) {
						cinza[i] = (data[p] * 306 + data[p + 1] * 601 + data[p + 2] * 117) >> 10;
					}

					try {
						const fonte = new RGBLuminanceSource(cinza, largura, faixaAltura);
						const resultado = leitor.decode(new BinaryBitmap(new HybridBinarizer(fonte)));
						const codigo = resultado.getText();
						encerrar();
						onread(codigo);
					} catch {
						// nenhum codigo neste quadro: normal, a proxima tentativa vem ai
					} finally {
						leitor.reset();
					}
				}, INTERVALO_MS);
			} catch (erro) {
				const nome = erro instanceof DOMException ? erro.name : '';
				falha = nome === 'NotAllowedError' || nome === 'SecurityError' ? 'permissao' : 'indisponivel';
				iniciando = false;
				encerrar();
			}
		})();

		return encerrar;
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
		<video bind:this={video} class="h-full w-full object-cover"></video>

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
