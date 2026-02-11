/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

type ToastVariant = 'default' | 'success' | 'error' | 'info' | 'warning';

type ToastMessage = {
  id: string;
  message: string;
  variant: ToastVariant;
};

type ToastListener = (messages: ToastMessage[]) => void;

const listeners = new Set<ToastListener>();
let messages: ToastMessage[] = [];

function emit() {
  for (const listener of listeners) {
    listener(messages);
  }
}

function addToast(message: string, variant: ToastVariant = 'default') {
  const id = `toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  messages = [...messages, { id, message, variant }];
  emit();
  window.setTimeout(() => {
    messages = messages.filter((entry) => entry.id !== id);
    emit();
  }, 4000);
  return id;
}

function dismissToast(id?: string) {
  messages = id ? messages.filter((entry) => entry.id !== id) : [];
  emit();
}

type ToastFn = ((message: string) => string) & {
  success: (message: string) => string;
  error: (message: string) => string;
  info: (message: string) => string;
  warning: (message: string) => string;
  dismiss: (id?: string) => void;
};

export const toast: ToastFn = Object.assign(
  (message: string) => addToast(message, 'default'),
  {
    success: (message: string) => addToast(message, 'success'),
    error: (message: string) => addToast(message, 'error'),
    info: (message: string) => addToast(message, 'info'),
    warning: (message: string) => addToast(message, 'warning'),
    dismiss: dismissToast,
  },
);

function variantClasses(variant: ToastVariant): string {
  switch (variant) {
    case 'success':
      return 'border-green-500/40 bg-green-50 text-green-900';
    case 'error':
      return 'border-destructive/40 bg-destructive/10 text-destructive';
    case 'warning':
      return 'border-amber-500/40 bg-amber-50 text-amber-900';
    case 'info':
      return 'border-sky-500/40 bg-sky-50 text-sky-900';
    default:
      return 'border-border bg-card text-foreground';
  }
}

export function Toaster() {
  const [items, setItems] = useState<ToastMessage[]>(messages);

  useEffect(() => {
    const listener: ToastListener = (next) => setItems(next);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  return (
    <div
      className="fixed bottom-4 right-4 z-[100] flex max-w-sm flex-col gap-2"
      role="status"
      aria-live="polite"
      aria-relevant="additions"
    >
      {items.map((item) => (
        <div
          key={item.id}
          className={cn('rounded-md border px-3 py-2 text-sm shadow-md', variantClasses(item.variant))}
        >
          {item.message}
        </div>
      ))}
    </div>
  );
}
