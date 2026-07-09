import type { Equipment, ExerciseLevel, MealType, MuscleGroup } from '$lib/api';
import { m } from '$lib/paraglide/messages';

export const MEAL_TYPES: MealType[] = ['breakfast', 'lunch', 'snack', 'dinner', 'other'];

export function mealTypeLabel(meal: MealType): string {
	return {
		breakfast: m.meal_breakfast(),
		pre_workout: m.meal_pre_workout(),
		lunch: m.meal_lunch(),
		snack: m.meal_snack(),
		dinner: m.meal_dinner(),
		supper: m.meal_supper(),
		other: m.meal_other()
	}[meal];
}

// Rótulo de porção: label_key + gramas, ex. "1 fatia (25 g)"
export function portionLabel(labelKey: string, grams: number): string {
	const word =
		{
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
		}[labelKey] ?? labelKey;
	return `${word} (${grams} g)`;
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
