import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Check, X } from 'lucide-react';

export function ToastStack({ children }) {
  return <div className="toast-stack">{children}</div>;
}

export default function Toast({ message, type = 'error', onDismiss, duration = 5500 }) {
  const [visible, setVisible] = useState(Boolean(message));
  const onDismissRef = useRef(onDismiss);
  const removeTimer = useRef(null);

  useEffect(() => { onDismissRef.current = onDismiss; }, [onDismiss]);

  const dismiss = useCallback(() => {
    setVisible(false);
    clearTimeout(removeTimer.current);
    removeTimer.current = setTimeout(() => onDismissRef.current?.(), 280);
  }, []);

  useEffect(() => {
    if (!message) return undefined;
    setVisible(true);
    const timer = setTimeout(dismiss, duration);
    return () => {
      clearTimeout(timer);
      clearTimeout(removeTimer.current);
    };
  }, [message, duration, dismiss]);

  if (!message) return null;
  const Icon = type === 'success' ? Check : AlertTriangle;
  return <div className={`toast-notification toast-${type} ${visible ? 'is-visible' : 'is-exiting'}`} role={type === 'success' ? 'status' : 'alert'}>
    <Icon className="toast-icon" size={17} aria-hidden="true" />
    <span className="toast-message">{message}</span>
    <button className="toast-close" type="button" aria-label="Dismiss notification" onClick={dismiss}><X size={15} /></button>
  </div>;
}
