type HeirloomLogoProps = {
  size?: number;
  withWordmark?: boolean;
  ringColor?: string;
  ringColorSecondary?: string;
  wordmarkColor?: string;
};

// Original mark: two interlocking rings standing for a family's wealth
// passing from one generation to the next. No third-party logo assets are
// used anywhere in this app. Evergreen + Brass per
// design-system/HEIRLOOM-DESIGN-SYSTEM.md. wordmarkColor defaults to
// currentColor so the mark reads correctly wherever it's dropped (header,
// sign-in page, etc.) without hardcoding a background assumption.
export function HeirloomLogo({
  size = 28,
  withWordmark = true,
  ringColor = "#1f5a45",
  ringColorSecondary = "#a8874a",
  wordmarkColor = "currentColor",
}: HeirloomLogoProps) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem" }}>
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <circle cx="13" cy="16" r="9" stroke={ringColor} strokeWidth="2.5" />
        <circle cx="21" cy="16" r="9" stroke={ringColorSecondary} strokeWidth="2.5" />
      </svg>
      {withWordmark && (
        <span
          style={{
            fontFamily: "var(--font-heirloom-serif), Georgia, serif",
            fontSize: `${Math.max(size * 0.64, 15)}px`,
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color: wordmarkColor,
          }}
        >
          Heirloom
        </span>
      )}
    </span>
  );
}
