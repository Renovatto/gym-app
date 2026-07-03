interface ToastState {
	message: string;
	visible: boolean;
}

export const toastState = $state<ToastState>({ message: '', visible: false });

let timer: ReturnType<typeof setTimeout> | null = null;

export function showToast(message: string, durationMs = 2500): void {
	toastState.message = message;
	toastState.visible = true;
	if (timer) clearTimeout(timer);
	timer = setTimeout(() => {
		toastState.visible = false;
	}, durationMs);
}
