"use client";

import { RelayApiError } from "@/features/heirloom/api/client";
import styles from "./StateViews.module.css";

export function LoadingState({ label }: { label: string }) {
  return (
    <div className={styles.state} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span className={styles.label}>{label}</span>
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className={styles.state}>
      <p className={styles.title}>{title}</p>
      {body ? <p className={styles.body}>{body}</p> : null}
    </div>
  );
}

function describe(error: Error): { title: string; body: string } {
  if (error instanceof RelayApiError && error.code === "network_error") {
    return {
      title: "Can't reach Heirloom Relay",
      body: "The service didn't respond. Check that the backend is running, then retry.",
    };
  }
  return { title: "Something went wrong", body: error.message };
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const { title, body } = describe(error);
  return (
    <div className={`${styles.state} ${styles.error}`} role="alert">
      <p className={styles.title}>{title}</p>
      <p className={styles.body}>{body}</p>
      <button type="button" className={styles.retry} onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
