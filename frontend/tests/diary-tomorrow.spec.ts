import { test, expect, type Page } from '@playwright/test';

const today = '2026-10-27';
const tomorrow = '2026-10-28';
const food = {
	id: 17, slug: 'banana', name: 'Banana', category: 'fruit', kcal: 89,
	protein_g: 1.1, carbs_g: 22.8, fat_g: 0.3, default_portion_g: 100,
	portions: [], is_custom: false, is_favorite: false
};
const recipe = {
	id: 31, name: 'Mingau de teste', servings: 1,
	ingredients: [{ id: 1, food, grams: 100, macros: { kcal: 89, protein_g: 1.1, carbs_g: 22.8, fat_g: 0.3 } }],
	total: { kcal: 89, protein_g: 1.1, carbs_g: 22.8, fat_g: 0.3 },
	per_serving: { kcal: 89, protein_g: 1.1, carbs_g: 22.8, fat_g: 0.3 }, is_favorite: false
};

type HarnessOptions = { failDelete?: boolean; theme?: 'light' | 'dark' };

async function mockApp(page: Page, options: HarnessOptions = {}): Promise<{ posts: Array<Record<string, unknown>>; deletes: string[]; setDeleteFailure: (fail: boolean) => void; setUserId: (id: number) => void }> {
	const posts: Array<Record<string, unknown>> = [];
	const deletes: string[] = [];
	let failDelete = options.failDelete ?? false;
	let userId = 1;
	await page.clock.install({ time: new Date('2026-10-27T10:00:00+02:00') });
	await page.addInitScript((theme) => {
		localStorage.setItem('gymapp.theme', theme);
		localStorage.setItem('gymapp.access', 'offline-test-token');
		localStorage.setItem('PARAGLIDE_LOCALE', 'pt-BR');
	}, options.theme ?? 'light');
	await page.route('http://127.0.0.1:18999/**', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		const path = url.pathname;
		if (path === '/me') return route.fulfill({ json: { id: userId, locale: 'pt-BR', has_profile: true, plan: 'free', is_admin: false } });
		if (path === '/me/profile') return route.fulfill({ json: { tutorial_enabled: false, tutorial_progress: {} } });
		if (path === '/me/news') return route.fulfill({ json: { items: [], unread_count: 0, pending_important: null } });
		if (path === '/me/diary' && request.method() === 'POST') {
			const body = request.postDataJSON() as Record<string, unknown>;
			posts.push(body);
			const id = 500 + posts.length;
			return route.fulfill({ json: { id, meal_type: body.meal_type, source: body.source, food_id: body.food_id ?? null, recipe_id: body.recipe_id ?? null, name: body.source === 'recipe' ? recipe.name : food.name, quantity: body.quantity, grams: 100, macros: { kcal: 89, protein_g: 1.1, carbs_g: 22.8, fat_g: 0.3 }, received_from: null } });
		}
		if (path === '/me/diary/undo-additions' && request.method() === 'POST') {
			const { entry_ids } = request.postDataJSON() as { entry_ids: number[] };
			deletes.push(...entry_ids.map(String));
			return failDelete
				? route.fulfill({ status: 503, json: { detail: 'GENERIC_ERROR' } })
				: route.fulfill({ status: 204, body: '' });
		}
		if (path === '/me/foods' || path === '/foods') return route.fulfill({ json: [food] });
		if (path === '/me/foods/recent' || path === '/me/foods/favorites') return route.fulfill({ json: [] });
		if (path === '/me/recipes') return route.fulfill({ json: [recipe] });
		if (path === '/me/diary') {
			return route.fulfill({ json: { date: url.searchParams.get('day') ?? today, meals: [], totals: { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 }, goals: null, estimates: [], review: { status: 'complete', has_unknown_energy: false, has_unknown_macros: false } } });
		}
		if (path === '/me/diary/gap') return route.fulfill({ json: { primary: 'complete', suggestions: [] } });
		if (path === '/me/diary/meal-plan') return route.fulfill({ json: { meals: [] } });
		if (path === '/me/diary/logged-days') return route.fulfill({ json: [] });
		if (path === '/me/supplements') return route.fulfill({ json: { items: [], taken_count: 0 } });
		if (path === '/me/diet/period') return route.fulfill({ json: null });
		if (path === '/me/summary/adaptive' || path === '/me/cycle') return route.fulfill({ status: 404, json: { detail: 'NOT_FOUND' } });
		return route.fulfill({ json: [] });
	});
	return { posts, deletes, setUserId: (id: number) => { userId = id; }, setDeleteFailure: (fail: boolean) => { failDelete = fail; } };
}

test('navega de hoje para amanha e impede avancar alem de D+1', async ({ page }) => {
	await mockApp(page);
	await page.goto(`/dieta?dia=${today}`);
	await expect(page.getByRole('heading', { name: 'Dieta' })).toBeVisible();
	await page.getByRole('button', { name: 'Próximo dia' }).click();
	await expect(page.getByRole('button', { name: 'Amanhã' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Próximo dia' })).toBeDisabled();
});

test('calendario seleciona amanha e desabilita datas posteriores', async ({ page }) => {
	await mockApp(page);
	await page.goto(`/dieta?dia=${today}`);
	await page.getByRole('button', { name: 'Hoje' }).click();
	const calendar = page.getByRole('dialog');
	await expect(calendar.getByRole('button', { name: '28', exact: true })).toBeEnabled();
	await expect(calendar.getByRole('button', { name: '29', exact: true })).toBeDisabled();
	await calendar.getByRole('button', { name: '28', exact: true }).click();
	await expect(page.getByRole('button', { name: 'Amanhã' })).toBeVisible();
});

test('rota direta salva alimento amanha na data certa e desfazer exige confirmacao', async ({ page }) => {
	const { posts, deletes } = await mockApp(page);
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar ao diário|Adicionar/ }).last().click();
	await expect.poll(() => posts.length).toBe(1);
	expect(posts[0]).toMatchObject({ entry_date: tomorrow, meal_type: 'breakfast', source: 'food', food_id: 17 });
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await page.getByRole('button', { name: /^Pronto \(1\)/ }).click();
	const toast = page.getByTestId('tomorrow-toast');
	await expect(toast).toBeVisible();
	await expect(toast).toContainText('1 item adicionado');
	await toast.getByRole('button', { name: 'Desfazer' }).click();
	await expect(toast).toContainText('Desfazer esta inclusão?');
	await page.screenshot({ path: '/private/tmp/gymapp-tomorrow-confirmation.png' });
	expect(deletes).toEqual([]);
	await toast.getByRole('button', { name: 'Cancelar' }).click();
	expect(deletes).toEqual([]);
	await toast.getByRole('button', { name: 'Desfazer' }).click();
	await toast.getByRole('button', { name: 'Confirmar exclusão' }).click();
	await expect.poll(() => deletes).toEqual(['501']);
});

test('rota direta para D+2 normaliza para hoje e nunca salva data futura', async ({ page }) => {
	const { posts } = await mockApp(page);
	await page.goto('/dieta/adicionar?day=2026-10-29&meal=breakfast');
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar à refeição|Adicionar/ }).last().click();
	await expect.poll(() => posts.length).toBe(1);
	expect(posts[0]).toMatchObject({ entry_date: today, meal_type: 'breakfast' });
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await expect(page.getByRole('status').filter({ hasText: 'Adicionado' })).toBeVisible();
});

test('receita salva amanha e desfazer usa o ID retornado para cada inclusao', async ({ page }) => {
	const { posts, deletes } = await mockApp(page);
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await page.getByRole('button', { name: 'Receitas' }).click();
	await page.getByRole('button', { name: 'Mingau de teste' }).click();
	await page.getByRole('button', { name: /Adicionar ao diário|Adicionar/ }).last().click();
	await expect.poll(() => posts.length).toBe(1);
	expect(posts[0]).toMatchObject({ entry_date: tomorrow, source: 'recipe', recipe_id: 31 });
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await page.getByRole('button', { name: /^Pronto \(1\)/ }).click();
	const toast = page.getByTestId('tomorrow-toast');
	await expect(toast).toContainText('1 item adicionado');
	await page.getByRole('button', { name: 'Desfazer' }).click();
	await page.getByRole('button', { name: 'Confirmar exclusão' }).click();
	await expect.poll(() => deletes).toEqual(['501']);
});

test('20 itens geram um unico aviso ao finalizar e desfazer captura somente esta sessao', async ({ page }) => {
	const { posts, deletes } = await mockApp(page);
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	for (let count = 1; count <= 20; count += 1) {
		await page.getByRole('button', { name: 'Banana' }).click();
		await page.getByRole('button', { name: /Adicionar à refeição|Adicionar/ }).last().click();
		await expect(page.getByRole('button', { name: `Pronto (${count})`, exact: true })).toBeEnabled();
		await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	}
	await page.getByRole('button', { name: 'Pronto (20)', exact: true }).click();
	const toast = page.getByTestId('tomorrow-toast');
	await expect(toast).toHaveCount(1);
	await expect(toast).toContainText('20 itens adicionados');
	await expect(toast).toContainText('Salvo para amanhã');
	await toast.getByRole('button', { name: 'Desfazer' }).click();
	await expect(toast).toContainText('Os 20 itens');
	expect(deletes).toEqual([]);
	await toast.getByRole('button', { name: 'Confirmar exclusão' }).click();
	await expect.poll(() => deletes).toEqual(Array.from({ length: 20 }, (_, index) => String(501 + index)));
	expect(posts).toHaveLength(20);
	await expect(toast).toHaveCount(0);

	await page.goto(`/dieta/adicionar?day=${today}&meal=breakfast`);
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar à refeição|Adicionar/ }).last().click();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await expect(page.getByRole('status').filter({ hasText: 'Adicionado' })).toBeVisible();
});

test('falha ao desfazer mantem o aviso e permite tentar novamente', async ({ page }) => {
	const harness = await mockApp(page, { failDelete: true });
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar ao diário|Adicionar/ }).last().click();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await page.getByRole('button', { name: /^Pronto \(1\)/ }).click();
	const toast = page.getByTestId('tomorrow-toast');
	await toast.getByRole('button', { name: 'Desfazer' }).click();
	await toast.getByRole('button', { name: 'Confirmar exclusão' }).click();
	await expect(toast.getByRole('alert')).toBeVisible();
	await expect(toast).toBeVisible();
	harness.setDeleteFailure(false);
	await toast.getByRole('button', { name: 'Confirmar exclusão' }).click();
	await expect.poll(() => harness.deletes).toEqual(['501', '501']);
	await expect(toast).toHaveCount(0);
});

test('toast de amanha expira, mas a confirmacao pausa o prazo', async ({ page }) => {
	const { posts, deletes } = await mockApp(page);
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar ao diário|Adicionar/ }).last().click();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await page.getByRole('button', { name: /^Pronto \(1\)/ }).click();
	const toast = page.getByTestId('tomorrow-toast');
	await expect(toast).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Dieta', exact: true })).toBeVisible();
	await page.mouse.move(0, 0);
	await page.clock.fastForward(17000);
	await toast.getByRole('button', { name: 'Desfazer' }).click();
	const countdown = await toast.getByTestId('undo-countdown').textContent();
	await page.clock.fastForward(20000);
	await expect(toast).toBeVisible();
	await toast.getByRole('button', { name: 'Cancelar' }).click();
	await expect(toast.getByTestId('undo-countdown')).toHaveText(countdown!);
	await page.keyboard.press('Tab');
	await page.mouse.move(0, 0);
	await page.clock.fastForward(2000);
	await expect(toast).toHaveCount(0);
	await expect.poll(() => posts.length).toBe(1);
	expect(deletes).toEqual([]);
});


test('virada do ano preserva a data escolhida e atualiza amanha para hoje', async ({ page }) => {
	await mockApp(page);
	await page.clock.setSystemTime(new Date('2026-12-31T12:00:00Z'));
	await page.goto('/dieta');
	await page.getByRole('button', { name: 'Próximo dia' }).click();
	await expect(page.getByRole('button', { name: 'Amanhã' })).toBeVisible();
	await page.getByRole('button', { name: 'Amanhã' }).click();
	const calendar = page.getByRole('dialog');
	await expect(calendar).toContainText('janeiro de 2027');
	await expect(calendar.getByRole('button', { name: '1', exact: true })).toBeEnabled();
	await expect(calendar.getByRole('button', { name: '2', exact: true })).toBeDisabled();
	await calendar.getByRole('button', { name: '1', exact: true }).click();
	await page.clock.setSystemTime(new Date('2027-01-01T12:00:00Z'));
	await page.clock.fastForward(31000);
	await expect(page.getByRole('button', { name: 'Hoje' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Próximo dia' })).toBeEnabled();
});

// Contraste usa as cores efetivas, incluindo o remapeamento de tokens e fundos transparentes.
async function textContrast(locator: import('@playwright/test').Locator, backgroundOnly = false): Promise<number> {
	return locator.evaluate((element, backgroundOnly) => {
		const context = document.createElement('canvas').getContext('2d')!;
		function pixels(color: string): number[] {
			context.clearRect(0, 0, 1, 1);
			context.fillStyle = color;
			context.fillRect(0, 0, 1, 1);
			return Array.from(context.getImageData(0, 0, 1, 1).data);
		}
		function composite(front: number[], back: number[]): number[] {
			// Composicao alfa combina cada canal com o fundo efetivamente visivel.
			const alpha = front[3] / 255;
			return front.slice(0, 3).map((channel, index) => channel * alpha + back[index] * (1 - alpha));
		}
		const ancestors: Element[] = [];
		for (let ancestor: Element | null = element; ancestor; ancestor = ancestor.parentElement) ancestors.unshift(ancestor);
		let background = [255, 255, 255];
		for (const ancestor of ancestors) background = composite(pixels(getComputedStyle(ancestor).backgroundColor), background);
		let foreground: number[];
		if (backgroundOnly) {
			// O preenchimento da barra deve contrastar com o trilho, nao consigo mesmo.
			const fill = pixels(getComputedStyle(element).backgroundColor);
			background = [255, 255, 255];
			for (const ancestor of ancestors.slice(0, -1)) background = composite(pixels(getComputedStyle(ancestor).backgroundColor), background);
			foreground = composite(fill, background);
		} else {
			foreground = composite(pixels(getComputedStyle(element).color), background);
		}
		function luminance(channels: number[]): number {
			// Luminancia relativa WCAG: lineariza sRGB e pondera R/G/B pela sensibilidade visual.
			const linear = channels.map((channel) => {
				const srgb = channel / 255;
				return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
			});
			return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
		}
		const light = Math.max(luminance(foreground), luminance(background));
		const dark = Math.min(luminance(foreground), luminance(background));
		// Razao WCAG entre as luminancias mais clara e mais escura.
		return (light + 0.05) / (dark + 0.05);
	}, backgroundOnly);
}

for (const theme of ['light', 'dark'] as const) {
	test(`aviso final, timer, confirmacao e erro ficam legiveis no tema ${theme}`, async ({ page }) => {
		await mockApp(page, { theme, failDelete: true });
		await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
		await page.getByRole('button', { name: 'Banana' }).click();
		await page.getByRole('button', { name: /Adicionar à refeição|Adicionar/ }).last().click();
		await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
		await page.getByRole('button', { name: 'Pronto (1)', exact: true }).click();
		const toast = page.getByTestId('tomorrow-toast');
		await expect(toast).toBeVisible();
		await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /dark/ : /^(?!.*dark)/);
		expect((await toast.innerText()).match(/amanhã/g)).toHaveLength(1);
		for (const text of [toast.locator('[role="status"] p').nth(0), toast.locator('[role="status"] p').nth(1), toast.getByTestId('undo-countdown'), toast.getByRole('button', { name: 'Desfazer' })]) {
			expect(await textContrast(text)).toBeGreaterThanOrEqual(4.5);
		}
		expect(await textContrast(toast.locator('.timer-bar'), true)).toBeGreaterThanOrEqual(3);
		await expect(toast).toHaveCSS('opacity', '1');
		await page.screenshot({ path: `/private/tmp/gymapp-tomorrow-${theme}.png` });
		await toast.getByRole('button', { name: 'Desfazer' }).click();
		const confirmation = toast.getByRole('group');
		for (const text of [confirmation.locator('p').nth(0), confirmation.locator('p').nth(1), confirmation.getByRole('button', { name: 'Confirmar exclusão' }), confirmation.getByRole('button', { name: 'Cancelar' })]) {
			expect(await textContrast(text)).toBeGreaterThanOrEqual(4.5);
		}
		await toast.getByRole('button', { name: 'Confirmar exclusão' }).click();
		await expect(toast.getByRole('alert')).toBeVisible();
		expect(await textContrast(toast.getByRole('alert'))).toBeGreaterThanOrEqual(4.5);
		await page.screenshot({ path: `/private/tmp/gymapp-tomorrow-confirmation-${theme}.png` });
	});
}

test('fechar sem adicionar itens nao cria aviso de amanha', async ({ page }) => {
	await mockApp(page);
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await page.getByRole('button', { name: 'Pronto', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'Dieta', exact: true })).toBeVisible();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
});


test('criar alimento e voltar preserva a contagem e os IDs da inclusao', async ({ page }) => {
	const { deletes } = await mockApp(page);
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar à refeição|Adicionar/ }).last().click();
	await expect(page.getByRole('button', { name: 'Pronto (1)', exact: true })).toBeVisible();
	await page.getByRole('link', { name: 'Cadastrar alimento', exact: true }).first().click();
	await expect(page.getByRole('heading', { name: 'Cadastrar alimento', exact: true })).toBeVisible();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await page.goBack();
	await page.getByRole('button', { name: 'Pronto (1)', exact: true }).click();
	const toast = page.getByTestId('tomorrow-toast');
	await expect(toast).toHaveCount(1);
	await toast.getByRole('button', { name: 'Desfazer' }).click();
	await toast.getByRole('button', { name: 'Confirmar exclusão' }).click();
	await expect.poll(() => deletes).toEqual(['501']);
});

test('voltar da rota direta conclui o resumo dos itens ja salvos', async ({ page }) => {
	await mockApp(page);
	await page.goto('/dieta');
	// Usa navegacao SPA: recarregar o documento por page.goto descartaria o estado dos avisos.
	const link = page.getByRole('link', { name: 'Alimentos e Receitas', exact: true });
	await link.evaluate((element, destination) => element.setAttribute('href', destination), `/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await link.click();
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar à refeição|Adicionar/ }).last().click();
	await expect(page.getByRole('button', { name: 'Pronto (1)', exact: true })).toBeEnabled();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await page.goBack();
	const toast = page.getByTestId('tomorrow-toast');
	await expect(toast).toHaveCount(1);
	await toast.getByRole('button', { name: 'Fechar', exact: true }).click();
	await page.reload();
	await page.goForward();
	await expect(page.getByRole('button', { name: 'Pronto', exact: true })).toBeVisible();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	await page.getByRole('button', { name: 'Pronto', exact: true }).click();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
});


test('historico de outra conta nao restaura IDs nem contagem de inclusoes', async ({ page }) => {
	const harness = await mockApp(page);
	await page.goto(`/dieta/adicionar?day=${tomorrow}&meal=breakfast`);
	await page.getByRole('button', { name: 'Banana' }).click();
	await page.getByRole('button', { name: /Adicionar à refeição|Adicionar/ }).last().click();
	await expect(page.getByRole('button', { name: 'Pronto (1)', exact: true })).toBeEnabled();
	harness.setUserId(2);
	await page.reload();
	await expect(page.getByRole('button', { name: 'Pronto', exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Pronto', exact: true }).click();
	await expect(page.getByTestId('tomorrow-toast')).toHaveCount(0);
	expect(harness.deletes).toEqual([]);
});
