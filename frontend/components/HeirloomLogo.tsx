type HeirloomLogoProps = {
  size?: number;
  withWordmark?: boolean;
};

// Original mark: two interlocking rings standing for a family's wealth
// passing from one generation to the next. No third-party logo assets are
// used anywhere in this app — only the dark/green palette was borrowed as
// a look.
export function HeirloomLogo({ size = 28, withWordmark = true }: HeirloomLogoProps) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem" }}>
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <circle cx="13" cy="16" r="9" stroke="#00dd94" strokeWidth="2.5" />
        <circle cx="21" cy="16" r="9" stroke="#ffffff" strokeWidth="2.5" />
      </svg>
      {withWordmark && (
        <span
          style={{
            fontSize: `${Math.max(size * 0.64, 15)}px`,
            fontWeight: 700,
            letterSpacing: "-0.01em",
            color: "#ffffff",
          }}
        >
          Heirloom
        </span>
      )}
    </span>
  );
}
