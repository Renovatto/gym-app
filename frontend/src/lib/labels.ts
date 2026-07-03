import type { Equipment, MuscleGroup } from '$lib/api';
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
		calves: m.mg_calves()
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
	'calves'
];

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
