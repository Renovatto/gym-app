import { test, expect } from '@playwright/test';
import { shellRequests } from '../src/lib/sw-shell';

// Regressao: o service worker guardava a casca com cache.addAll(caminhos), que
// aceita a copia do cache HTTP do navegador. Um index.html velho (de antes da troca
// de dominio) entrou no cache do worker e o app passou a chamar uma API que nao
// existia mais. Toda casca precisa ser buscada direto no servidor.
test('casca do service worker ignora o cache HTTP do navegador', () => {
	const requests = shellRequests(['/', '/_app/immutable/entry/app.js', '/manifest.webmanifest'], 'https://gymapp.rsaaon.com');

	expect(requests).toHaveLength(3);
	for (const request of requests) {
		expect(request.cache).toBe('reload');
		expect(request.method).toBe('GET');
	}
	expect(requests.map((r) => r.url)).toEqual([
		'https://gymapp.rsaaon.com/',
		'https://gymapp.rsaaon.com/_app/immutable/entry/app.js',
		'https://gymapp.rsaaon.com/manifest.webmanifest'
	]);
});
