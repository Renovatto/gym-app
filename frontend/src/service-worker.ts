/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

/*
 * Service worker do PWA: faz o app instalado ABRIR sem internet.
 *
 * O que ele guarda: so a casca do app (JS, CSS, icones) - nada de dados. Os dados
 * vivem na API, em outro dominio, e resposta de API nunca entra em cache aqui: um
 * peso ou uma refeicao desatualizada na tela seria pior que a tela vazia.
 *
 * Por que o cache leva a versao do build no nome: cada deploy gera um `version` novo,
 * entao o cache novo nasce separado e o antigo e apagado no activate. E o que impede
 * o erro classico de service worker - prender uma versao velha no celular da pessoa.
 *
 * A troca acontece no proximo abrir do app (sem skipWaiting) de proposito: trocar os
 * arquivos no meio da sessao quebraria a carga preguicosa das telas que ainda nao
 * foram abertas.
 */

import { build, files, version } from '$service-worker';

const CACHE_NAME = `gymapp-${version}`;

// build = JS/CSS com hash no nome; files = o que esta em static/ (icones, manifest).
// A raiz entra separada porque o fallback da SPA (index.html) nao esta nessas listas.
const SHELL = ['/', ...build, ...files];
// Decidir por PERTENCIMENTO, nao por exclusao: so entra em cache o que e casca.
// A versao anterior excluia "outro dominio" achando que a API estaria fora - mas em
// producao ela vive no mesmo endereco, em /api. Resultado: resposta de API entrava
// em cache-first e a tela mostrava dado velho para sempre (desfazer a agua e lancar
// refeicao pareciam travados). Lista do que pode, nunca lista do que nao pode.
const CASCA = new Set(SHELL);

const worker = self as unknown as ServiceWorkerGlobalScope;

worker.addEventListener('install', (event) => {
	// skipWaiting porque a versao anterior servia resposta de API do cache: esperar
	// o app ser fechado para trocar deixaria o aparelho com dado velho por dias. O
	// custo conhecido e uma tela ainda aberta pedir um arquivo que o deploy trocou -
	// incomodo pontual, contra um bug que faz o app parecer quebrado.
	worker.skipWaiting();
	event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)));
});

worker.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
			.then(() => worker.clients.claim())
	);
});

worker.addEventListener('fetch', (event) => {
	const request = event.request;
	const url = new URL(request.url);

	// Fora do escopo do cache: metodo que muda dado, outro dominio e qualquer coisa
	// que nao seja http(s).
	if (request.method !== 'GET') return;
	if (url.origin !== worker.location.origin) return;
	if (!url.protocol.startsWith('http')) return;

	// Navegacao (abrir o app, trocar de tela): tenta a rede para pegar o deploy novo
	// e cai na casca guardada quando nao ha conexao. Como a SPA resolve as rotas no
	// cliente, a raiz serve qualquer caminho.
	if (request.mode === 'navigate') {
		event.respondWith(
			fetch(request).catch(async () => {
				const cache = await caches.open(CACHE_NAME);
				return (await cache.match('/')) ?? Response.error();
			})
		);
		return;
	}

	// Tudo que nao e casca (a API, em primeiro lugar) vai direto para a rede e nunca
	// e guardado. Dado do usuario tem que chegar fresco ou nao chegar.
	if (!CASCA.has(url.pathname)) return;

	// Arquivo com hash no nome nunca muda de conteudo: cache primeiro, rede so na
	// primeira vez. Vale tambem para icone e manifest.
	event.respondWith(
		caches.open(CACHE_NAME).then(async (cache) => {
			const cached = await cache.match(request);
			if (cached) return cached;
			const response = await fetch(request);
			if (response.ok) cache.put(request, response.clone());
			return response;
		})
	);
});

export {};
