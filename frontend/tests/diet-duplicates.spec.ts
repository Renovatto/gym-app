import { expect, test, type Page } from '@playwright/test';

const foodA = {
	id: 21,
	slug: 'custom-1-arroz-a',
	name: 'Arroz A',
	category: 'cereal_grain',
	kcal: 100,
	protein_g: 4,
	carbs_g: 20,
	fat_g: 2,
	default_portion_g: 100,
	portions: [],
	is_custom: true,
	is_favorite: false,
	archived_at: null
};

const foodB = { ...foodA, id: 22, slug: 'custom-1-arroz-b', name: 'Arroz B' };

const macros = { kcal: 100, protein_g: 4, carbs_g: 20, fat_g: 2 };

const recipeA = {
	id: 11,
	name: 'Arroz simples',
	servings: 1,
	ingredients: [{ id: 1, food: foodA, grams: 100, macros }],
	total: macros,
	per_serving: macros,
	is_favorite: false,
	archived_at: null
};

const recipeB = {
	...recipeA,
	id: 12,
	name: 'Arroz da casa',
	ingredients: [{ id: 2, food: foodB, grams: 100, macros }]
};

async function mockDietApi(page: Page): Promise<{ archiveRequests: number }> {
	const calls = { archiveRequests: 0 };
	await page.addInitScript(() => {
		localStorage.setItem('gymapp.access', 'offline-test-token');
		localStorage.setItem('PARAGLIDE_LOCALE', 'pt-br');
	});
	await page.route('http://127.0.0.1:18999/**', async (route) => {
		const request = route.request();
		const path = new URL(request.url()).pathname;
		if (path === '/me') {
			return route.fulfill({ json: { id: 1, locale: 'pt-BR', has_profile: true, plan: 'free', is_admin: false } });
		}
		if (path === '/me/profile') {
			return route.fulfill({ json: { tutorial_enabled: false, tutorial_progress: {} } });
		}
		if (path === '/me/news') {
			return route.fulfill({ json: { items: [], unread_count: 0, pending_important: null } });
		}
		if (path === '/me/recipes') return route.fulfill({ json: [recipeA, recipeB] });
		if (path === '/recipes/library') return route.fulfill({ json: [] });
		if (path === '/foods') return route.fulfill({ json: [foodA, foodB] });
		if (path === '/me/diet/duplicates') {
			return route.fulfill({
				json: [
					{ item_kind: 'food', items: [{ id: 21, name: 'Arroz A', is_custom: true }, { id: 22, name: 'Arroz B', is_custom: true }] },
					{ item_kind: 'recipe', items: [{ id: 11, name: 'Arroz simples', is_custom: true }, { id: 12, name: 'Arroz da casa', is_custom: true }] }
				]
			});
		}
		if (path === '/me/sharing/connections') {
			return route.fulfill({ json: [{ id: 5, person_name: 'Andre', person_email: 'andre@example.invalid', status: 'accepted', i_invited: false, created_at: '2026-10-01T00:00:00Z' }] });
		}
		if (path === '/me/sharing/offers' && request.method() === 'POST') {
			return route.fulfill({ json: [{ id: 90, item_kind: 'recipe', item_name: recipeA.name, from_name: 'Tatyelle', created_at: '2026-10-29T00:00:00Z' }] });
		}
		if (path === '/me/sharing/offers' || path === '/me/sharing/received') {
			return route.fulfill({ json: [] });
		}
		if (path === '/me/sharing/pending-count') {
			return route.fulfill({ json: { invites: 0, offers: 0, total: 0 } });
		}
		if (path === '/me/recipes/11/archive' && request.method() === 'POST') {
			calls.archiveRequests += 1;
			return route.fulfill({ json: { ...recipeA, archived_at: '2026-10-29T00:00:00Z' } });
		}
		return route.fulfill({ json: [] });
	});
	return calls;
}

function contrastRatio(foreground: string, background: string): number {
	const luminance = (color: string): number => {
		const [red, green, blue] = color.match(/[\da-f]{2}/gi)!.slice(0, 3).map((channel) => parseInt(channel, 16) / 255);
		const linear = [red, green, blue].map((channel) =>
			channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
		);
		return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
	};
	const foregroundLuminance = luminance(foreground);
	const backgroundLuminance = luminance(background);
	return (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
		(Math.min(foregroundLuminance, backgroundLuminance) + 0.05);
}

test('avisa e destaca duplicidades, permite compartilhar e inativar receita com confirmacao', async ({ page }) => {
	const calls = await mockDietApi(page);
	await page.goto('/dieta/receitas');
	const alert = page.getByRole('region', { name: /conteúdo duplicado/i });
	await expect(alert).toBeVisible();
	await expect(alert).toContainText('Arroz simples');
	await expect(alert).toContainText('Arroz da casa');
	await expect(page.getByText('Possível duplicado').first()).toBeVisible();

	for (const darkMode of [false, true]) {
		await page.evaluate((enabled) => document.documentElement.classList.toggle('dark', enabled), darkMode);
		const colors = await alert.locator('p').evaluate((element) => {
			const foreground = getComputedStyle(element).color;
			const background = getComputedStyle(element.closest('section')!).backgroundColor;
			const canvas = document.createElement('canvas');
			canvas.width = 1;
			canvas.height = 1;
			const context = canvas.getContext('2d')!;
			const toHex = (color: string) => {
				context.fillStyle = color;
				context.fillRect(0, 0, 1, 1);
				return Array.from(context.getImageData(0, 0, 1, 1).data.slice(0, 3))
					.map((channel) => channel.toString(16).padStart(2, '0')).join('');
			};
			return { foreground: toHex(foreground), background: toHex(background) };
		});
		expect(contrastRatio(colors.foreground, colors.background), `${darkMode ? 'dark' : 'light'} ${JSON.stringify(colors)}`).toBeGreaterThanOrEqual(4.5);
	}
	await page.evaluate(() => document.documentElement.classList.remove('dark'));

	await page.getByRole('link', { name: /Arroz simples Possível duplicado/ }).click();
	await expect(page.getByRole('button', { name: 'Compartilhar', exact: true })).toBeVisible();

	await page.getByRole('button', { name: 'Inativar este item', exact: true }).click();
	await expect(page.getByText(/Inativar este item\?/)).toBeVisible();
	expect(calls.archiveRequests).toBe(0);
	await page.getByRole('button', { name: 'Inativar este item', exact: true }).last().click();
	await expect.poll(() => calls.archiveRequests).toBe(1);
	await expect(page.getByRole('status').filter({ hasText: 'Item inativado.' })).toBeVisible();
});
