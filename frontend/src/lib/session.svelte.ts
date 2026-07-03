import { api, clearTokens, getTokens, setTokens, type ProfileData, type UserOut } from './api';

export const session = $state({
	loaded: false,
	user: null as UserOut | null,
	profile: null as ProfileData | null
});

export async function bootstrap(): Promise<void> {
	const { access, refresh } = getTokens();
	if (!access && !refresh) {
		session.loaded = true;
		return;
	}
	try {
		session.user = await api.me();
		if (session.user.has_profile) {
			session.profile = await api.getProfile();
		}
	} catch {
		clearTokens();
		session.user = null;
		session.profile = null;
	}
	session.loaded = true;
}

export async function signIn(email: string, password: string): Promise<void> {
	setTokens(await api.login(email, password));
	session.loaded = false;
	await bootstrap();
}

export async function signUp(email: string, password: string, locale: string): Promise<void> {
	setTokens(await api.register(email, password, locale));
	session.loaded = false;
	await bootstrap();
}

export function signOut(): void {
	clearTokens();
	session.user = null;
	session.profile = null;
}
