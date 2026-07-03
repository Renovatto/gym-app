import type { Equipment, ExerciseLevel, MuscleGroup } from '$lib/api';
import { m } from '$lib/paraglide/messages';

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
