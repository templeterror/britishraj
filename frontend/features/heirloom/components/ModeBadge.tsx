import type { RelayMode } from "@/features/heirloom/types/contracts";
import styles from "./ModeBadge.module.css";

/** Shown on every screen while the API reports `meta.mode == "demo"`. */
export default function ModeBadge({ mode }: { mode: RelayMode | undefined }) {
  if (mode !== "demo") return null;
  return <span className={styles.badge}>Mock data mode</span>;
}
