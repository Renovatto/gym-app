import type {
	ActivityIntensity,
	Equipment,
	ExerciseLevel,
	MealType,
	MuscleGroup,
	MuscleRegion,
	StandaloneActivityKind
} from '$lib/api';
import { m } from '$lib/paraglide/messages';

export const MEAL_TYPES: MealType[] = ['breakfast', 'lunch', 'snack', 'dinner', 'other'];

export function mealTypeLabel(meal: MealType): string {
	return {
		breakfast: m.meal_breakfast(),
		pre_workout: m.meal_pre_workout(),
		post_workout: m.meal_post_workout(),
		lunch: m.meal_lunch(),
		snack: m.meal_snack(),
		dinner: m.meal_dinner(),
		supper: m.meal_supper(),
		other: m.meal_other()
	}[meal];
}

// As 10 chaves aceitas para FoodPortion.label_key (mesma lista do backend,
// schemas.py:PortionLabelKey, e das mensagens portion_* nos 3 idiomas).
export const PORTION_LABEL_KEYS = [
	'unit',
	'slice',
	'tbsp',
	'tsp',
	'cup',
	'glass',
	'scoop',
	'filet',
	'handful',
	'portion'
] as const;

function portionWords(): Record<string, string> {
	return {
		unit: m.portion_unit(),
		slice: m.portion_slice(),
		tbsp: m.portion_tbsp(),
		tsp: m.portion_tsp(),
		cup: m.portion_cup(),
		glass: m.portion_glass(),
		scoop: m.portion_scoop(),
		filet: m.portion_filet(),
		handful: m.portion_handful(),
		portion: m.portion_portion()
	};
}

// Rótulo de porção: label_key + gramas, ex. "1 fatia (25 g)"
export function portionLabel(labelKey: string, grams: number): string {
	const word = portionWords()[labelKey] ?? labelKey;
	return `${word} (${grams} g)`;
}

// So a palavra, ex. "1 fatia" - usado no seletor de porção do cadastro de alimento,
// onde o peso já é um campo à parte.
export function portionLabelWord(labelKey: string): string {
	return portionWords()[labelKey] ?? labelKey;
}

export const ACTIVITY_KINDS: StandaloneActivityKind[] = [
	'running',
	'cycling',
	'walking',
	'yoga',
	'pilates',
	'boxing',
	'swimming',
	'dance',
	'other'
];

// Atividades onde faz sentido informar distancia - mesmo criterio de
// DISTANCE_KINDS em backend/app/services/activities.py (so exibicao aqui).
export const ACTIVITY_DISTANCE_KINDS: StandaloneActivityKind[] = ['running', 'cycling', 'walking', 'swimming'];

export function activityKindLabel(kind: StandaloneActivityKind): string {
	return {
		running: m.activity_kind_running(),
		cycling: m.activity_kind_cycling(),
		walking: m.activity_kind_walking(),
		yoga: m.activity_kind_yoga(),
		pilates: m.activity_kind_pilates(),
		boxing: m.activity_kind_boxing(),
		swimming: m.activity_kind_swimming(),
		dance: m.activity_kind_dance(),
		other: m.activity_kind_other()
	}[kind];
}

export function activityIntensityLabel(intensity: ActivityIntensity): string {
	return {
		light: m.activity_intensity_light(),
		moderate: m.activity_intensity_moderate(),
		hard: m.activity_intensity_hard()
	}[intensity];
}

export function muscleGroupLabel(group: MuscleGroup): string {
	return {
		chest: m.mg_chest(),
		back: m.mg_back(),
		shoulders: m.mg_shoulders(),
		biceps: m.mg_biceps(),
		triceps: m.mg_triceps(),
		legs: m.mg_legs(),
		glutes: m.mg_glutes(),
		abs: m.mg_abs(),
		calves: m.mg_calves(),
		cardio: m.mg_cardio()
	}[group];
}

export const MUSCLE_GROUPS: MuscleGroup[] = [
	'chest',
	'back',
	'legs',
	'shoulders',
	'biceps',
	'triceps',
	'glutes',
	'abs',
	'calves',
	'cardio'
];

export function muscleRegionLabel(region: MuscleRegion): string {
	return {
		chest_upper: m.mr_chest_upper(),
		chest_mid: m.mr_chest_mid(),
		chest_lower: m.mr_chest_lower(),
		lats: m.mr_lats(),
		upper_back: m.mr_upper_back(),
		traps: m.mr_traps(),
		lower_back: m.mr_lower_back(),
		delt_front: m.mr_delt_front(),
		delt_side: m.mr_delt_side(),
		delt_rear: m.mr_delt_rear(),
		biceps: m.mr_biceps(),
		forearms: m.mr_forearms(),
		triceps_long: m.mr_triceps_long(),
		triceps_lateral: m.mr_triceps_lateral(),
		quads: m.mr_quads(),
		hamstrings: m.mr_hamstrings(),
		adductors: m.mr_adductors(),
		abductors: m.mr_abductors(),
		glute_max: m.mr_glute_max(),
		glute_med: m.mr_glute_med(),
		abs_upper: m.mr_abs_upper(),
		abs_lower: m.mr_abs_lower(),
		obliques: m.mr_obliques(),
		core: m.mr_core(),
		gastrocnemius: m.mr_gastrocnemius(),
		soleus: m.mr_soleus()
	}[region];
}

// Subdivisao de cada MuscleGroup - espelha services/exercises.py:REGIONS_BY_GROUP
// no backend (fonte unica da verdade da hierarquia). Grupo sem entrada (cardio)
// nao tem subdivisao: a fileira de chips soma nele.
export const REGIONS_BY_GROUP: Record<MuscleGroup, MuscleRegion[]> = {
	chest: ['chest_upper', 'chest_mid', 'chest_lower'],
	back: ['lats', 'upper_back', 'traps', 'lower_back'],
	shoulders: ['delt_front', 'delt_side', 'delt_rear'],
	biceps: ['biceps', 'forearms'],
	triceps: ['triceps_long', 'triceps_lateral'],
	legs: ['quads', 'hamstrings', 'adductors', 'abductors'],
	glutes: ['glute_max', 'glute_med'],
	abs: ['abs_upper', 'abs_lower', 'obliques', 'core'],
	calves: ['gastrocnemius', 'soleus'],
	cardio: []
};

export const LEVELS: ExerciseLevel[] = ['beginner', 'intermediate', 'expert'];

export function levelLabel(level: ExerciseLevel): string {
	return {
		beginner: m.level_beginner(),
		intermediate: m.level_intermediate(),
		expert: m.level_expert()
	}[level];
}

export function equipmentLabel(equipment: Equipment): string {
	return {
		barbell: m.eq_barbell(),
		dumbbell: m.eq_dumbbell(),
		machine: m.eq_machine(),
		cable: m.eq_cable(),
		bodyweight: m.eq_bodyweight(),
		kettlebell: m.eq_kettlebell(),
		band: m.eq_band(),
		other: m.eq_other()
	}[equipment];
}
