interface ToastState {
	message: string;
	visible: boolean;
}

export interface ToastAction {
	label: string;
	confirmation: string;
	description: string;
	run: () => Promise<void>;
}

export interface ActionToastState {
	id: number;
	message: string;
	title: string;
	duration: number;
	action: ToastAction;
}

interface ToastOptions {
	duration?: number;
	title?: string;
	kind?: 'success' | 'warning';
	action?: ToastAction;
}

export const toastState = $state<ToastState>({ message: '', visible: false });
// Cada inclusao conserva seu aviso e seu ID; um novo sucesso nao substitui uma confirmacao.
export const actionToasts = $state<ActionToastState[]>([]);
let nextActionId = 0;
let timer: ReturnType<typeof setTimeout> | null = null;

export function clearActionToasts(): void {
	actionToasts.splice(0);
}

export function dismissActionToast(id: number): void {
	const index = actionToasts.findIndex((toast) => toast.id === id);
	if (index >= 0) actionToasts.splice(index, 1);
}

export function showToast(message: string, durationOrOptions: number | ToastOptions = 4500): void {
	const options = typeof durationOrOptions === 'number' ? {} : durationOrOptions;
	if (options.action) {
		actionToasts.unshift({
			id: ++nextActionId, message, title: options.title ?? '',
			duration: options.duration ?? 18000, action: options.action
		});
		return;
	}
	toastState.message = message;
	toastState.visible = true;
	if (timer) clearTimeout(timer);
	timer = setTimeout(() => {
		toastState.visible = false;
	}, typeof durationOrOptions === 'number' ? durationOrOptions : options.duration ?? 4500);
}
