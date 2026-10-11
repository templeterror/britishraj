import type { StressPreset } from "@/features/heirloom/types/contracts";

/** 5_000_000 -> "$5.0M", 672_444 -> "$672K", 950 -> "$950". */
export function formatMoneyCompact(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${Math.round(abs / 1e3)}K`;
  return `${sign}$${Math.round(abs)}`;
}

/** Probability 0..1 -> "6%"; never prints a false 0% or 100% for an extreme estimate. */
export function formatProbability(p: number | null): string {
  if (p === null) return "Unknown";
  if (p > 0 && p < 0.005) return "<1%";
  if (p < 1 && p > 0.995) return ">99%";
  return `${Math.round(p * 100)}%`;
}

export const PRESET_LABEL: Record<StressPreset, string> = {
  base: "Base",
  exit_delay_24m: "Exit +24 mo",
  shock_30_y1: "−30% shock",
  sale_haircut_20: "Sale haircut 20%",
};

export const PRESET_ORDER: StressPreset[] = ["base", "exit_delay_24m", "shock_30_y1", "sale_haircut_20"];

/** Extraction confidence 0..1 -> "91%"; null when the extractor gave none. */
export function formatConfidence(p: number | null): string {
  return p === null ? "Not stated" : `${Math.round(p * 100)}%`;
}

/** "Robert Morgan" -> "Robert". */
export function firstName(displayName: string | undefined, fallback: string): string {
  const first = displayName?.trim().split(/\s+/)[0];
  return first ? first : fallback;
}
