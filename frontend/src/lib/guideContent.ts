// Conteudo da area de consulta (guia de saude do app). Os tres idiomas ficam lado a
// lado de proposito: e conteudo denso e assim fica facil de ler e manter em um lugar so.
// As formulas sao a mesma fonte da verdade do backend (services/goals.py).

import type { Locale } from '$lib/paraglide/runtime';

// Um par termo/definicao (usado no glossario de siglas).
export interface GlossaryTerm {
	term: string;
	definition: string;
}

// Uma formula com nome, expressao e uma observacao curta.
export interface FormulaEntry {
	name: string;
	formula: string;
	note: string;
}

// Uma secao do guia pode ser: glossario, lista de formulas ou lista de topicos.
export type GuideSection =
	| { kind: 'glossary'; title: string; terms: GlossaryTerm[] }
	| { kind: 'formulas'; title: string; items: FormulaEntry[] }
	| { kind: 'topics'; title: string; intro?: string; bullets: string[] };

const PT_BR: GuideSection[] = [
	{
		kind: 'glossary',
		title: 'Glossario (siglas)',
		terms: [
			{ term: 'IMC (BMI)', definition: 'Indice de Massa Corporal = peso / altura2. Triagem geral; nao distingue gordura de musculo.' },
			{ term: 'BMR', definition: 'Taxa metabolica basal: calorias que o corpo gasta em repouso absoluto (so para viver).' },
			{ term: 'TDEE', definition: 'Gasto energetico total do dia = BMR x nivel de atividade. E a sua manutencao (calorias para manter o peso).' },
			{ term: 'V-fat', definition: 'Gordura visceral: a que fica ao redor dos orgaos (barriga). E a mais perigosa e a que responde melhor ao deficit.' },
			{ term: 'BIA', definition: 'Bioimpedancia: metodo da balanca para estimar composicao corporal. Imprecisa no valor absoluto, mas boa para acompanhar a tendencia.' }
		]
	},
	{
		kind: 'formulas',
		title: 'Como o app calcula suas metas',
		items: [
			{ name: 'BMR (Mifflin-St Jeor)', formula: '10 x peso(kg) + 6.25 x altura(cm) - 5 x idade + s', note: 's = +5 para homens, -161 para mulheres.' },
			{ name: 'TDEE (manutencao)', formula: 'BMR x fator de atividade', note: 'Fator de 1.2 (sedentario) a 1.9 (muito ativo). Ja inclui o treino na media.' },
			{ name: 'Meta para perder gordura', formula: 'TDEE - deficit da taxa escolhida', note: 'Nunca abaixo do BMR (piso de seguranca).' },
			{ name: 'Deficit por taxa de perda', formula: 'peso x (taxa%/100) x 7700 / 7', note: 'Taxa: leve 0.25%, moderado 0.5%, agressivo 0.75% do peso por semana. 1 kg de gordura ~ 7700 kcal.' },
			{ name: 'Proteina', formula: 'g por kg de peso, conforme objetivo', note: '1.6 manter, 2.0 perder/ganhar, 2.2 recomposicao. Protege o musculo no deficit.' },
			{ name: 'Agua', formula: 'peso(kg) x 35 ml', note: 'Meta diaria base; ajuste com calor e treino.' },
			{ name: 'TDEE adaptativo', formula: 'media comida - (inclinacao do peso x 7700)', note: 'Estima sua manutencao REAL pelos dados: o que voce comeu vs como o peso mudou. Corrige o erro da formula.' }
		]
	},
	{
		kind: 'topics',
		title: 'Deficit calorico, sem mitos',
		intro: 'O deficit e o que forca a perda de gordura. Como faze-lo bem:',
		bullets: [
			'Prefira uma taxa moderada (~0.5% do peso/semana). Mais rapido nao e melhor: acelera a perda de musculo.',
			'Nunca coma abaixo do seu BMR por muito tempo. O app aplica esse piso automaticamente.',
			'Proteina alta e treino de forca no deficit: e o que garante que o que sai e gordura, nao musculo.',
			'Nao some as calorias do treino de novo na meta: o TDEE ja as inclui (contaria duas vezes).',
			'A balanca decide, nao a formula: se em 2-3 semanas o peso nao cair, o deficit real e zero. Use a meta sugerida (TDEE adaptativo).',
			'Conforme voce emagrece, o gasto cai. A meta precisa ser recalculada (o app faz isso a cada nova pesagem).'
		]
	},
	{
		kind: 'topics',
		title: 'Gordura abdominal (visceral), sem magica',
		intro: 'Nao existe reducao localizada: abdominais nao queimam a barriga. O que reduz gordura visceral:',
		bullets: [
			'Deficit calorico sustentado: a visceral costuma ser das primeiras a sair.',
			'Proteina alta em todas as refeicoes.',
			'Treino de forca + um pouco de cardio (Zona 2 constante e algum HIIT).',
			'Cortar acucar liquido (refrigerante, sucos): e o que mais alimenta gordura visceral e no figado.',
			'Reduzir alcool e dormir bem: o cortisol alto por estresse e pouco sono favorece a gordura abdominal.',
			'Fibras e vegetais: saciam e ajudam o intestino e a sensibilidade a insulina.'
		]
	},
	{
		kind: 'topics',
		title: 'Como e quando se pesar',
		intro: 'Para a leitura ser confiavel e a tendencia aparecer:',
		bullets: [
			'De manha, em jejum, depois do banheiro, antes de beber agua, com pouca roupa.',
			'Sempre nas mesmas condicoes (o horario muda bastante o numero).',
			'Peso: idealmente diario ou quase; o app usa a media para cortar o ruido do dia a dia.',
			'Composicao corporal (bioimpedancia): 1x por semana basta, no mesmo dia da semana.',
			'Nao se assuste com oscilacao de 1-2 kg em um dia: e agua e comida, nao gordura.'
		]
	}
];

const EN: GuideSection[] = [
	{
		kind: 'glossary',
		title: 'Glossary (acronyms)',
		terms: [
			{ term: 'BMI', definition: 'Body Mass Index = weight / height2. General screening; does not tell fat from muscle.' },
			{ term: 'BMR', definition: 'Basal Metabolic Rate: calories your body burns fully at rest (just to stay alive).' },
			{ term: 'TDEE', definition: 'Total Daily Energy Expenditure = BMR x activity level. This is your maintenance (calories to keep weight).' },
			{ term: 'V-fat', definition: 'Visceral fat: the fat around your organs (belly). The most dangerous, and the one that responds best to a deficit.' },
			{ term: 'BIA', definition: 'Bioimpedance: the scale method to estimate body composition. Imprecise in absolute value, but good for trends.' }
		]
	},
	{
		kind: 'formulas',
		title: 'How the app computes your goals',
		items: [
			{ name: 'BMR (Mifflin-St Jeor)', formula: '10 x weight(kg) + 6.25 x height(cm) - 5 x age + s', note: 's = +5 for men, -161 for women.' },
			{ name: 'TDEE (maintenance)', formula: 'BMR x activity factor', note: 'Factor from 1.2 (sedentary) to 1.9 (very active). Already includes training on average.' },
			{ name: 'Fat loss goal', formula: 'TDEE - deficit from chosen rate', note: 'Never below BMR (safety floor).' },
			{ name: 'Deficit from loss rate', formula: 'weight x (rate%/100) x 7700 / 7', note: 'Rate: light 0.25%, moderate 0.5%, aggressive 0.75% of bodyweight per week. 1 kg of fat ~ 7700 kcal.' },
			{ name: 'Protein', formula: 'g per kg of bodyweight, by goal', note: '1.6 maintain, 2.0 lose/gain, 2.2 recomposition. Protects muscle in a deficit.' },
			{ name: 'Water', formula: 'weight(kg) x 35 ml', note: 'Base daily goal; adjust for heat and training.' },
			{ name: 'Adaptive TDEE', formula: 'avg intake - (weight slope x 7700)', note: 'Estimates your REAL maintenance from data: what you ate vs how weight changed. Corrects the formula error.' }
		]
	},
	{
		kind: 'topics',
		title: 'Caloric deficit, no myths',
		intro: 'The deficit is what drives fat loss. How to do it well:',
		bullets: [
			'Prefer a moderate rate (~0.5% of bodyweight/week). Faster is not better: it speeds up muscle loss.',
			'Never eat below your BMR for long. The app applies this floor automatically.',
			'High protein and strength training in a deficit: this ensures what you lose is fat, not muscle.',
			'Do not add training calories to your goal again: TDEE already includes them (would double-count).',
			'The scale decides, not the formula: if weight does not drop in 2-3 weeks, your real deficit is zero. Use the suggested goal (adaptive TDEE).',
			'As you get leaner, expenditure drops. The goal must be recomputed (the app does this on each weigh-in).'
		]
	},
	{
		kind: 'topics',
		title: 'Belly (visceral) fat, no magic',
		intro: 'There is no spot reduction: ab exercises do not burn belly fat. What reduces visceral fat:',
		bullets: [
			'A sustained caloric deficit: visceral fat is often among the first to go.',
			'High protein at every meal.',
			'Strength training + some cardio (steady Zone 2 and some HIIT).',
			'Cut liquid sugar (soda, juices): it is what most feeds visceral and liver fat.',
			'Less alcohol and good sleep: high cortisol from stress and poor sleep favor belly fat.',
			'Fiber and vegetables: they satiate and help the gut and insulin sensitivity.'
		]
	},
	{
		kind: 'topics',
		title: 'How and when to weigh in',
		intro: 'For a reliable reading and a clear trend:',
		bullets: [
			'In the morning, fasted, after the bathroom, before drinking water, lightly dressed.',
			'Always under the same conditions (time of day changes the number a lot).',
			'Weight: ideally daily or almost; the app uses the average to cut daily noise.',
			'Body composition (bioimpedance): once a week is enough, on the same weekday.',
			'Do not panic over a 1-2 kg swing in a day: that is water and food, not fat.'
		]
	}
];

const ES: GuideSection[] = [
	{
		kind: 'glossary',
		title: 'Glosario (siglas)',
		terms: [
			{ term: 'IMC (BMI)', definition: 'Indice de Masa Corporal = peso / altura2. Cribado general; no distingue grasa de musculo.' },
			{ term: 'BMR', definition: 'Tasa metabolica basal: calorias que el cuerpo gasta en reposo absoluto (solo para vivir).' },
			{ term: 'TDEE', definition: 'Gasto energetico total del dia = BMR x nivel de actividad. Es tu mantenimiento (calorias para mantener el peso).' },
			{ term: 'V-fat', definition: 'Grasa visceral: la que rodea los organos (barriga). La mas peligrosa y la que mejor responde al deficit.' },
			{ term: 'BIA', definition: 'Bioimpedancia: metodo de la bascula para estimar composicion corporal. Imprecisa en valor absoluto, buena para la tendencia.' }
		]
	},
	{
		kind: 'formulas',
		title: 'Como la app calcula tus metas',
		items: [
			{ name: 'BMR (Mifflin-St Jeor)', formula: '10 x peso(kg) + 6.25 x altura(cm) - 5 x edad + s', note: 's = +5 para hombres, -161 para mujeres.' },
			{ name: 'TDEE (mantenimiento)', formula: 'BMR x factor de actividad', note: 'Factor de 1.2 (sedentario) a 1.9 (muy activo). Ya incluye el entrenamiento en promedio.' },
			{ name: 'Meta para perder grasa', formula: 'TDEE - deficit de la tasa elegida', note: 'Nunca por debajo del BMR (piso de seguridad).' },
			{ name: 'Deficit por tasa de perdida', formula: 'peso x (tasa%/100) x 7700 / 7', note: 'Tasa: ligero 0.25%, moderado 0.5%, agresivo 0.75% del peso por semana. 1 kg de grasa ~ 7700 kcal.' },
			{ name: 'Proteina', formula: 'g por kg de peso, segun objetivo', note: '1.6 mantener, 2.0 perder/ganar, 2.2 recomposicion. Protege el musculo en el deficit.' },
			{ name: 'Agua', formula: 'peso(kg) x 35 ml', note: 'Meta diaria base; ajusta con calor y entrenamiento.' },
			{ name: 'TDEE adaptativo', formula: 'media comida - (pendiente del peso x 7700)', note: 'Estima tu mantenimiento REAL con datos: lo que comiste vs como cambio el peso. Corrige el error de la formula.' }
		]
	},
	{
		kind: 'topics',
		title: 'Deficit calorico, sin mitos',
		intro: 'El deficit es lo que fuerza la perdida de grasa. Como hacerlo bien:',
		bullets: [
			'Prefiere una tasa moderada (~0.5% del peso/semana). Mas rapido no es mejor: acelera la perdida de musculo.',
			'Nunca comas por debajo de tu BMR por mucho tiempo. La app aplica ese piso automaticamente.',
			'Proteina alta y entrenamiento de fuerza en el deficit: asegura que lo que pierdes es grasa, no musculo.',
			'No sumes las calorias del entrenamiento otra vez a la meta: el TDEE ya las incluye (contaria doble).',
			'La bascula decide, no la formula: si en 2-3 semanas el peso no baja, tu deficit real es cero. Usa la meta sugerida (TDEE adaptativo).',
			'A medida que adelgazas, el gasto baja. La meta debe recalcularse (la app lo hace en cada pesaje).'
		]
	},
	{
		kind: 'topics',
		title: 'Grasa abdominal (visceral), sin magia',
		intro: 'No hay reduccion localizada: los abdominales no queman la barriga. Lo que reduce la grasa visceral:',
		bullets: [
			'Un deficit calorico sostenido: la visceral suele ser de las primeras en salir.',
			'Proteina alta en cada comida.',
			'Entrenamiento de fuerza + algo de cardio (Zona 2 constante y algo de HIIT).',
			'Cortar el azucar liquido (refresco, zumos): es lo que mas alimenta la grasa visceral y del higado.',
			'Menos alcohol y dormir bien: el cortisol alto por estres y poco sueno favorece la grasa abdominal.',
			'Fibra y verduras: sacian y ayudan al intestino y a la sensibilidad a la insulina.'
		]
	},
	{
		kind: 'topics',
		title: 'Como y cuando pesarse',
		intro: 'Para que la lectura sea fiable y la tendencia aparezca:',
		bullets: [
			'Por la manana, en ayunas, despues del bano, antes de beber agua, con poca ropa.',
			'Siempre en las mismas condiciones (la hora cambia mucho el numero).',
			'Peso: idealmente diario o casi; la app usa el promedio para cortar el ruido diario.',
			'Composicion corporal (bioimpedancia): una vez por semana basta, el mismo dia de la semana.',
			'No te asustes por una oscilacion de 1-2 kg en un dia: es agua y comida, no grasa.'
		]
	}
];

const GUIDE_BY_LOCALE: Record<Locale, GuideSection[]> = {
	'pt-br': PT_BR,
	en: EN,
	es: ES
};

export function guideSections(locale: Locale): GuideSection[] {
	return GUIDE_BY_LOCALE[locale] ?? PT_BR;
}
