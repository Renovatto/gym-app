// Normalizacao de busca no frontend: espelha o normalize_search do backend
// (sem acento, sem caixa, sem espacos nas pontas). Usar SEMPRE dos dois lados
// da comparacao para a busca "funcionar de verdade" (ex.: "fuba" acha "Fubá").
export function normalizeSearch(text: string): string {
	return (
		text
			.normalize('NFD')
			// remove os diacriticos (acentos viram caracteres combinantes U+0300-U+036F no NFD)
			.replace(/[\u0300-\u036f]/g, '')
			.toLowerCase()
			.trim()
	);
}

// true se o termo (ja normalizado) aparece no texto (normalizado aqui).
export function searchMatches(haystack: string, normalizedTerm: string): boolean {
	if (!normalizedTerm) return true;
	return normalizeSearch(haystack).includes(normalizedTerm);
}
