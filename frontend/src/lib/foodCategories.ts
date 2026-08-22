// Fonte unica das categorias de alimento no frontend. A ordem daqui e a ordem que o
// usuario ve em toda tela (cadastro, edicao e filtro da biblioteca) - antes cada tela
// repetia a lista e uma delas ja tinha esquecido "Bebidas" pelo caminho.
//
// Os grupos seguem a TACO (tabela brasileira de composicao de alimentos) e espelham o
// enum FoodCategory do backend; a ordem agrupa por macro dominante: carbo, proteina,
// hortifruti, gordura, e no fim os grupos mistos.
import type { FoodCategory } from '$lib/api';
import { m } from '$lib/paraglide/messages';

export const FOOD_CATEGORIES: readonly FoodCategory[] = [
	'bakery',
	'cereal_grain',
	'tuber',
	'legume',
	'meat',
	'seafood',
	'egg',
	'dairy',
	'vegetable',
	'fruit',
	'nuts_seeds',
	'fat',
	'sweet',
	'sauce_condiment',
	'beverage',
	'prepared',
	'supplement',
	'other'
];

/** Rotulo traduzido da categoria; devolve o proprio codigo se ele nao existir mais. */
export function foodCategoryLabel(category: string): string {
	const labels: Record<FoodCategory, string> = {
		bakery: m.cat_bakery(),
		cereal_grain: m.cat_cereal_grain(),
		tuber: m.cat_tuber(),
		legume: m.cat_legume(),
		meat: m.cat_meat(),
		seafood: m.cat_seafood(),
		egg: m.cat_egg(),
		dairy: m.cat_dairy(),
		vegetable: m.cat_vegetable(),
		fruit: m.cat_fruit(),
		nuts_seeds: m.cat_nuts_seeds(),
		fat: m.cat_fat(),
		sweet: m.cat_sweet(),
		sauce_condiment: m.cat_sauce_condiment(),
		beverage: m.cat_beverage(),
		prepared: m.cat_prepared(),
		supplement: m.cat_supplement(),
		other: m.cat_other()
	};
	return labels[category as FoodCategory] ?? category;
}

/** Opcoes prontas para o ChoiceChips do cadastro e da edicao de alimento. */
export function foodCategoryOptions(): { value: FoodCategory; label: string }[] {
	return FOOD_CATEGORIES.map((value) => ({ value, label: foodCategoryLabel(value) }));
}
