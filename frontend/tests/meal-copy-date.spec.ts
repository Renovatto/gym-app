import { expect, test, type Page } from '@playwright/test';

const today = '2026-10-27';
const breakfastDay = '2026-10-20';
const emptyDiary = (day: string) => ({
	date: day,
	meals: [],
	totals: { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
	goals: null,
	estimates: [],
	review: { status: 'complete', has_unknown_energy: false, has_unknown_macros: false }
});

type TestDiary = Omit<ReturnType<typeof emptyDiary>, 'meals'> & {
	meals: Array<{
		meal_type: string;
		entries: Array<{
			id: number;
			meal_type: string;
			source: string;
			food_id: number;
			recipe_id: null;
			name: string;
			quantity: number;
			grams: number;
			macros: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
			received_from: null;
		}>;
		subtotal: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
	}>;
};

async function setupMealCopyApp(
	page: Page,
	theme: 'light' | 'dark',
	loggedDays: Record<string, string[]>,
	options: {
		holdLunchResponse?: boolean;
		holdDiaryAfterMealDelete?: boolean;
		diaries?: Record<string, TestDiary>;
	} = {}
): Promise<{
	loggedQueries: string[];
	copies: URL[];
	mealDeletions: URL[];
	diaryEntryDeletions: number[];
	diaryReloadStarted: Promise<void>;
	releaseDiaryReload: () => void;
	releaseLunch: () => void;
}> {
	const loggedQueries: string[] = [];
	const copies: URL[] = [];
	const mealDeletions: URL[] = [];
	const diaryEntryDeletions: number[] = [];
	const diaries = options.diaries ?? {};
	let shouldHoldDiaryReload = false;
	let releaseDiaryReload: () => void = () => {};
	let resolveDiaryReloadStarted: () => void = () => {};
	const diaryReloadStarted = new Promise<void>((resolve) => { resolveDiaryReloadStarted = resolve; });
	const heldDiaryReload = new Promise<void>((resolve) => { releaseDiaryReload = resolve; });
	let releaseLunchResponse: () => void = () => {};
	const lunchResponse = new Promise<void>((resolve) => { releaseLunchResponse = resolve; });
	await page.clock.install({ time: new Date('2026-10-27T10:00:00+02:00') });
	await page.addInitScript((selectedTheme) => {
		localStorage.setItem('gymapp.theme', selectedTheme);
		localStorage.setItem('gymapp.access', 'offline-test-token');
		localStorage.setItem('PARAGLIDE_LOCALE', 'pt-BR');
	}, theme);
	await page.route('http://127.0.0.1:18999/**', async (route) => {
		const requestUrl = new URL(route.request().url());
		const path = requestUrl.pathname;
		if (path === '/me') return route.fulfill({ json: { id: 1, locale: 'pt-BR', has_profile: true, plan: 'free', is_admin: false } });
		if (path === '/me/profile') return route.fulfill({ json: { tutorial_enabled: false, tutorial_progress: {} } });
		if (path === '/me/news') return route.fulfill({ json: { items: [], unread_count: 0, pending_important: null } });
		if (path === '/me/diary/logged-days') {
			const mealType = requestUrl.searchParams.get('meal_type') ?? '';
			loggedQueries.push(mealType);
			if (options.holdLunchResponse && mealType === 'lunch') await lunchResponse;
			return route.fulfill({ json: loggedDays[mealType] ?? [] });
		}
		if (path === '/me/diary/copy-previous') {
			copies.push(requestUrl);
			return route.fulfill({ json: emptyDiary(requestUrl.searchParams.get('day') ?? today) });
		}
		if (path === '/me/diary/delete-meal') {
			mealDeletions.push(requestUrl);
			shouldHoldDiaryReload = options.holdDiaryAfterMealDelete ?? false;
			const diary = diaries[requestUrl.searchParams.get('day') ?? today];
			const mealType = requestUrl.searchParams.get('meal_type');
			if (diary && mealType) {
				diary.meals = diary.meals.filter((group) => group.meal_type !== mealType);
			}
			return route.fulfill({ status: 204, body: '' });
		}
		if (/^\/me\/diary\/\d+$/.test(path) && route.request().method() === 'DELETE') {
			const entryId = Number(path.split('/').at(-1));
			diaryEntryDeletions.push(entryId);
			for (const diary of Object.values(diaries)) {
				diary.meals = diary.meals.map((group) => ({
					...group,
					entries: group.entries.filter((entry) => entry.id !== entryId)
				}));
			}
			return route.fulfill({ status: 204, body: '' });
		}
		if (path === '/me/diary') {
			if (shouldHoldDiaryReload) {
				shouldHoldDiaryReload = false;
				resolveDiaryReloadStarted();
				await heldDiaryReload;
			}
			const requestedDay = requestUrl.searchParams.get('day') ?? today;
			return route.fulfill({ json: diaries[requestedDay] ?? emptyDiary(requestedDay) });
		}
		if (path === '/me/diary/gap') return route.fulfill({ json: { primary: 'complete', suggestions: [] } });
		if (path === '/me/diary/meal-plan') return route.fulfill({ json: { meals: [] } });
		if (path === '/me/supplements') return route.fulfill({ json: { items: [], taken_count: 0 } });
		if (path === '/me/diet/period') return route.fulfill({ json: null });
		if (path === '/me/summary/adaptive' || path === '/me/cycle') return route.fulfill({ status: 404, json: { detail: 'NOT_FOUND' } });
		return route.fulfill({ json: [] });
	});
	return {
		loggedQueries,
		copies,
		mealDeletions,
		diaryEntryDeletions,
		diaryReloadStarted,
		releaseDiaryReload,
		releaseLunch: releaseLunchResponse
	};
}

async function addMeal(page: Page, meal: 'Café da manhã' | 'Almoço'): Promise<void> {
	await page.getByRole('button', { name: meal, exact: true }).first().click();
}

async function openMealCopy(page: Page, meal: 'Café da manhã' | 'Almoço'): Promise<void> {
	const card = page.locator('[data-tour="diet-meals"] section').filter({
		has: page.getByRole('heading', { name: meal, exact: true })
	});
	const repeatButton = card.getByRole('button', { name: 'Repetir de ontem' });
	if ((await repeatButton.count()) === 0) {
		await card.getByRole('heading', { name: meal, exact: true }).click();
	}
	await card.getByRole('button', { name: 'Repetir de ontem' }).click();
}

async function contrastRatio(locator: import('@playwright/test').Locator): Promise<number> {
	return locator.evaluate((element) => {
		const parse = (color: string) => {
			const oklch = color.match(/oklch\(([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)/);
			if (oklch) {
				const lightness = Number(oklch[1]);
				const chroma = Number(oklch[2]);
				const hue = Number(oklch[3]) * Math.PI / 180;
				const a = chroma * Math.cos(hue);
				const b = chroma * Math.sin(hue);
				const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
				const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
				const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
				return [
					4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
					-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
					-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s
				].map((channel) => 255 * (channel <= 0.0031308 ? 12.92 * channel : 1.055 * channel ** (1 / 2.4) - 0.055));
			}
			return color.match(/[\d.]+/g)?.slice(0, 3).map(Number) ?? [0, 0, 0];
		};
		const luminance = (color: string) => {
			const rgb = parse(color).map((channel) => {
				const srgb = channel / 255;
				return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
			});
			return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
		};
		const foreground = luminance(getComputedStyle(element).color);
		let surface: Element | null = element;
		while (surface) {
			const backgroundColor = getComputedStyle(surface).backgroundColor;
			if (backgroundColor !== 'transparent' && !backgroundColor.endsWith(', 0)') && !backgroundColor.endsWith('/ 0)')) break;
			surface = surface.parentElement;
		}
		const background = luminance(getComputedStyle(surface ?? element).backgroundColor);
		return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
	});
}

for (const theme of ['light', 'dark'] as const) {
	test(`calendario de copia filtra a refeicao e mantem contraste no tema ${theme}`, async ({ page }) => {
		const harness = await setupMealCopyApp(page, theme, {
			breakfast: [breakfastDay],
			lunch: ['2026-10-22']
		});
		await page.goto(`/dieta?dia=${today}`);
		await addMeal(page, 'Café da manhã');
		await openMealCopy(page, 'Café da manhã');
		await expect(page.getByText('Repetir esta refeição de ontem ou de outro dia?')).toBeVisible();
		await expect(page.getByRole('button', { name: 'Ontem', exact: true })).toBeDisabled();
		const sourceLabel = page.getByText(/^Origem:/);
		const sourceBounds = await sourceLabel.boundingBox();
		expect(sourceBounds).not.toBeNull();
		expect(sourceBounds!.height).toBeLessThanOrEqual(24);
		await expect.poll(() => harness.loggedQueries).toEqual(['breakfast']);
		await page.getByRole('button', { name: 'Outra data' }).click();

		const calendar = page.getByRole('dialog');
		const breakfastDayButton = calendar.getByRole('button', { name: '20', exact: true });
		const noBreakfastButton = calendar.getByRole('button', { name: /^21 / });
		await expect(breakfastDayButton.locator('span.bg-emerald-500')).toBeVisible();
		await expect(noBreakfastButton).toHaveAttribute('aria-disabled', 'true');
		await noBreakfastButton.click({ force: true });
		const hint = calendar.locator('#calendar-hint-2026-10-21');
		await expect(hint).toBeVisible();
		await expect(hint).toHaveText('Não houve lançamento de Café da manhã nesta data.');
		expect(await contrastRatio(hint)).toBeGreaterThanOrEqual(4.5);
		const hintBounds = await hint.boundingBox();
		expect(hintBounds).not.toBeNull();
		expect(hintBounds!.x).toBeGreaterThanOrEqual(0);
		expect(hintBounds!.x + hintBounds!.width).toBeLessThanOrEqual(390);

		await breakfastDayButton.click();
		await expect(page.getByRole('button', { name: 'Copiar', exact: true })).toBeEnabled();
		await page.getByRole('button', { name: 'Copiar', exact: true }).click();
		await expect.poll(() => harness.copies.length).toBe(1);
		expect(harness.copies[0].searchParams.get('day')).toBe(today);
		expect(harness.copies[0].searchParams.get('from_day')).toBe(breakfastDay);
		expect(harness.copies[0].searchParams.get('meal_type')).toBe('breakfast');
		await expect(page.getByRole('status').filter({ hasText: 'Refeição copiada para' })).toBeVisible();
	});
}

test('resposta atrasada de outra refeicao nao altera os dias do calendario aberto', async ({ page }) => {
	const harness = await setupMealCopyApp(page, 'light', {
		breakfast: [breakfastDay],
		lunch: ['2026-10-21']
	}, { holdLunchResponse: true });
	await page.goto(`/dieta?dia=${today}`);
	await addMeal(page, 'Café da manhã');
	await addMeal(page, 'Almoço');
	await openMealCopy(page, 'Almoço');
	await expect.poll(() => harness.loggedQueries).toEqual(['lunch']);
	await page.getByRole('button', { name: 'Cancelar', exact: true }).last().click();
	await openMealCopy(page, 'Café da manhã');
	await expect.poll(() => harness.loggedQueries).toEqual(['lunch', 'breakfast']);
	const lateLunchResponse = page.waitForResponse((response) =>
		response.url().includes('/me/diary/logged-days') && response.url().includes('meal_type=lunch')
	);
	harness.releaseLunch();
	await lateLunchResponse;
	await page.getByRole('button', { name: 'Outra data' }).click();
	const calendar = page.getByRole('dialog');
	await expect(calendar.getByRole('button', { name: '20', exact: true }).locator('span.bg-emerald-500')).toBeVisible();
	await calendar.getByRole('button', { name: /^21 / }).click({ force: true });
	await expect(calendar.locator('#calendar-hint-2026-10-21')).toContainText('Café da manhã');
});

test('mudar o dia cancela a confirmacao de copia e impede usar a origem antiga', async ({ page }) => {
	const harness = await setupMealCopyApp(page, 'light', { breakfast: ['2026-10-26'] });
	await page.goto(`/dieta?dia=${today}`);
	await addMeal(page, 'Café da manhã');
	await openMealCopy(page, 'Café da manhã');
	await expect.poll(() => harness.loggedQueries).toEqual(['breakfast']);
	await expect(page.getByRole('button', { name: 'Ontem', exact: true })).toBeEnabled();
	await page.getByRole('button', { name: 'Dia anterior', exact: true }).click();
	await expect(page.getByText('Repetir esta refeição de ontem ou de outro dia?')).toHaveCount(0);
	expect(harness.copies).toEqual([]);
});

for (const theme of ['light', 'dark'] as const) {
	test(`excluir refeicao pede confirmacao e mantem contraste no tema ${theme}`, async ({ page }) => {
	const harness = await setupMealCopyApp(page, theme, {});
	await page.goto(`/dieta?dia=${today}`);
	await addMeal(page, 'Café da manhã');
	const mealCard = page.locator('[data-tour="diet-meals"] section').filter({
		has: page.getByRole('heading', { name: 'Café da manhã', exact: true })
	});
	const swipeArea = mealCard.locator('[data-meal-swipe="breakfast"]');
	const deleteButton = mealCard.locator('[data-meal-delete="swipe"]');
	await expect(deleteButton).toHaveCount(0);
	const swipeBounds = await swipeArea.boundingBox();
	expect(swipeBounds).not.toBeNull();
	await page.mouse.move(swipeBounds!.x + swipeBounds!.width - 25, swipeBounds!.y + 35);
	await page.mouse.down();
	await page.mouse.move(swipeBounds!.x + swipeBounds!.width - 85, swipeBounds!.y + 35, { steps: 6 });
	await page.mouse.up();
	await expect(deleteButton).toBeVisible();
	expect(await contrastRatio(deleteButton)).toBeGreaterThanOrEqual(4.5);
	await deleteButton.click();
	const confirmationText = page.getByText(/Excluir esta refeição e todos os seus lançamentos/);
	await expect(confirmationText).toBeVisible();
	await expect(deleteButton).toHaveCount(0);
	const confirmButton = mealCard.getByRole('button', { name: 'Excluir', exact: true });
	expect(await contrastRatio(confirmationText)).toBeGreaterThanOrEqual(4.5);
	expect(await contrastRatio(confirmButton)).toBeGreaterThanOrEqual(4.5);
	expect(harness.mealDeletions).toEqual([]);

	await mealCard.getByRole('button', { name: 'Cancelar', exact: true }).click();
	await page.waitForTimeout(250);
	const resetSwipeBounds = await swipeArea.boundingBox();
	expect(resetSwipeBounds).not.toBeNull();
	await page.mouse.move(resetSwipeBounds!.x + resetSwipeBounds!.width - 25, resetSwipeBounds!.y + 35);
	await page.mouse.down();
	await page.mouse.move(resetSwipeBounds!.x + resetSwipeBounds!.width - 240, resetSwipeBounds!.y + 35, { steps: 10 });
	await page.mouse.up();
	await expect(confirmationText).toBeVisible();
	await expect(deleteButton).toHaveCount(0);
	expect(harness.mealDeletions).toEqual([]);
	await page.waitForTimeout(250);
	await confirmButton.click();
	await expect.poll(() => harness.mealDeletions.length).toBe(1);
	expect(harness.mealDeletions[0].searchParams.get('day')).toBe(today);
	expect(harness.mealDeletions[0].searchParams.get('meal_type')).toBe('breakfast');
	await expect(page.getByRole('status')).toBeVisible();
	await expect(mealCard).toHaveCount(0);
});
}

test('excluir refeicao continua acessivel por teclado no cartao aberto', async ({ page }) => {
	const harness = await setupMealCopyApp(page, 'light', {});
	await page.goto(`/dieta?dia=${today}`);
	await addMeal(page, 'Café da manhã');
	const mealCard = page.locator('[data-tour="diet-meals"] section').filter({
		has: page.getByRole('heading', { name: 'Café da manhã', exact: true })
	});
	const keyboardDelete = mealCard.locator('[data-meal-delete="keyboard"]');
	await mealCard.getByRole('button', { name: /^Café da manhã/ }).focus();
	await page.keyboard.press('Tab');
	await page.keyboard.press('Tab');
	await page.keyboard.press('Tab');
	await expect(keyboardDelete).toBeFocused();
	await keyboardDelete.press('Enter');
	await expect(page.getByText(/Excluir esta refeição e todos os seus lançamentos/)).toBeVisible();
	expect(harness.mealDeletions).toEqual([]);
});

test('excluir um lancamento preserva a posicao da tela na refeicao', async ({ page }) => {
	const macros = { kcal: 120, protein_g: 10, carbs_g: 12, fat_g: 4 };
	const entries = Array.from({ length: 10 }, (_, index) => ({
		id: index + 1,
		meal_type: 'breakfast',
		source: 'food',
		food_id: index + 1,
		recipe_id: null,
		name: `Alimento ${index + 1}`,
		quantity: 100,
		grams: 100,
		macros,
		received_from: null
	}));
	const diary: TestDiary = {
		...emptyDiary(today),
		meals: [{
			meal_type: 'breakfast',
			entries,
			subtotal: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 }
		}],
		totals: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 }
	};
	const harness = await setupMealCopyApp(page, 'light', {}, { diaries: { [today]: diary } });
	await page.goto(`/dieta?dia=${today}`);
	const mealCard = page.locator('[data-tour="diet-meals"] section').filter({
		has: page.getByRole('heading', { name: 'Café da manhã', exact: true })
	});
	await mealCard.getByRole('heading', { name: 'Café da manhã', exact: true }).click();
	const entry = mealCard.getByRole('button', { name: /Alimento 8/ });
	await entry.scrollIntoViewIfNeeded();
	await entry.click();
	const scrollBeforeDelete = await page.evaluate(() => window.scrollY);
	expect(scrollBeforeDelete).toBeGreaterThan(100);

	await page.getByRole('button', { name: 'Remover', exact: true }).click();
	await page.getByRole('button', { name: 'Excluir de vez', exact: true }).click();
	await expect.poll(() => harness.diaryEntryDeletions).toEqual([8]);
	await expect(mealCard.getByRole('button', { name: /Alimento 8/ })).toHaveCount(0);
	const scrollAfterDelete = await page.evaluate(() => window.scrollY);
	expect(scrollAfterDelete).toBeGreaterThan(100);
	expect(Math.abs(scrollAfterDelete - scrollBeforeDelete)).toBeLessThan(100);
});

test('excluir uma refeicao atualiza os dados sem substituir a tela', async ({ page }) => {
	const macros = { kcal: 120, protein_g: 10, carbs_g: 12, fat_g: 4 };
	const makeEntries = (mealType: string, firstId: number) => Array.from({ length: 10 }, (_, index) => ({
		id: firstId + index,
		meal_type: mealType,
		source: 'food',
		food_id: firstId + index,
		recipe_id: null,
		name: `${mealType} alimento ${index + 1}`,
		quantity: 100,
		grams: 100,
		macros,
		received_from: null
	}));
	const breakfastEntries = makeEntries('breakfast', 1);
	const lunchEntries = makeEntries('lunch', 11);
	const group = (mealType: string, entries: TestDiary['meals'][number]) => ({
		...entries,
		meal_type: mealType
	});
	const diary: TestDiary = {
		...emptyDiary(today),
		meals: [
			group('breakfast', { meal_type: 'breakfast', entries: breakfastEntries, subtotal: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 } }),
			group('lunch', { meal_type: 'lunch', entries: lunchEntries, subtotal: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 } })
		],
		totals: { kcal: 2400, protein_g: 200, carbs_g: 240, fat_g: 80 }
	};
	const harness = await setupMealCopyApp(page, 'light', {}, {
		diaries: { [today]: diary },
		holdDiaryAfterMealDelete: true
	});
	await page.goto(`/dieta?dia=${today}`);
	const breakfastCard = page.locator('[data-tour="diet-meals"] section').filter({
		has: page.getByRole('heading', { name: 'Café da manhã', exact: true })
	});
	await breakfastCard.getByRole('heading', { name: 'Café da manhã', exact: true }).click();
	await breakfastCard.locator('[data-meal-delete="keyboard"]').click();
	await expect(page.getByText(/Excluir esta refeição e todos os seus lançamentos/)).toBeVisible();
	const scrollBeforeDelete = await page.evaluate(() => window.scrollY);
	expect(scrollBeforeDelete).toBeGreaterThan(100);
	await breakfastCard.getByRole('button', { name: 'Excluir', exact: true }).click();
	const scrollAfterConfirmation = await page.evaluate(() => window.scrollY);
	await harness.diaryReloadStarted;
	await expect(breakfastCard.getByRole('heading', { name: 'Café da manhã', exact: true })).toBeVisible();
	expect(await page.evaluate(() => window.scrollY)).toBe(scrollAfterConfirmation);
	expect(harness.mealDeletions[0].searchParams.get('meal_type')).toBe('breakfast');

	harness.releaseDiaryReload();
	await expect(breakfastCard).toHaveCount(0);
	await expect(page.getByRole('heading', { name: 'Almoço', exact: true })).toBeVisible();
});

test('resposta atrasada de exclusao nao fecha o cartao do novo dia', async ({ page }) => {
	const previousDay = '2026-10-26';
	const macros = { kcal: 120, protein_g: 10, carbs_g: 12, fat_g: 4 };
	const entries = Array.from({ length: 10 }, (_, index) => ({
		id: index + 1,
		meal_type: 'breakfast',
		source: 'food',
		food_id: index + 1,
		recipe_id: null,
		name: `Alimento ${index + 1}`,
		quantity: 100,
		grams: 100,
		macros,
		received_from: null
	}));
	const diary: TestDiary = {
		...emptyDiary(today),
		meals: [{ meal_type: 'breakfast', entries, subtotal: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 } }],
		totals: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 }
	};
	const previousDayDiary: TestDiary = {
		...emptyDiary(previousDay),
		meals: [{ meal_type: 'breakfast', entries, subtotal: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 } }],
		totals: { kcal: 1200, protein_g: 100, carbs_g: 120, fat_g: 40 }
	};
	const harness = await setupMealCopyApp(page, 'light', {}, {
		diaries: { [today]: diary, [previousDay]: previousDayDiary },
		holdDiaryAfterMealDelete: true
	});
	await page.goto(`/dieta?dia=${today}`);
	const oldDayMeal = page.locator('[data-tour="diet-meals"] section').filter({
		has: page.getByRole('heading', { name: 'Café da manhã', exact: true })
	});
	await oldDayMeal.getByRole('heading', { name: 'Café da manhã', exact: true }).click();
	await oldDayMeal.locator('[data-meal-delete="keyboard"]').click();
	await oldDayMeal.getByRole('button', { name: 'Excluir', exact: true }).click();
	await harness.diaryReloadStarted;

	await page.getByRole('button', { name: 'Dia anterior', exact: true }).click();
	const newDayMeal = page.locator('[data-tour="diet-meals"] section').filter({
		has: page.getByRole('heading', { name: 'Café da manhã', exact: true })
	});
	await newDayMeal.getByRole('heading', { name: 'Café da manhã', exact: true }).click();
	const addFoodButton = newDayMeal.getByRole('button', { name: /\+ Adicionar/ });
	await expect(addFoodButton).toBeVisible();
	const delayedDiaryResponse = page.waitForResponse((response) =>
		response.url().includes('/me/diary?') && new URL(response.url()).searchParams.get('day') === today
	);
	harness.releaseDiaryReload();
	await delayedDiaryResponse;
	await expect(page.getByRole('status')).toContainText('Excluído');
	await expect(addFoodButton).toBeVisible();
});
