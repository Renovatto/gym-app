import { localDay } from '$lib/api';

export function shiftLocalDay(day: string, days: number): string {
	const date = new Date(`${day}T12:00:00`);
	// Avanca dias do calendario local, preservando a data nas mudancas de horario.
	date.setDate(date.getDate() + days);
	return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function validDiaryDay(requestedDay: string | null): string {
	const today = localDay();
	if (!requestedDay || !/^\d{4}-\d{2}-\d{2}$/.test(requestedDay)) return today;
	const parsed = new Date(`${requestedDay}T12:00:00`);
	if (Number.isNaN(parsed.getTime()) || shiftLocalDay(requestedDay, 0) !== requestedDay) return today;
	return requestedDay <= shiftLocalDay(today, 1) ? requestedDay : today;
}
