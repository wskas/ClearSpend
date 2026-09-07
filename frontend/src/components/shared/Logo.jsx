export default function Logo({ size = 30, className = "", style }) {
  return (
    <img
      src="/ClearSpendLogo.svg"
      alt="ClearSpend"
      width={size}
      height={size}
      className={`rounded-lg ${className}`.trim()}
      style={{ width: size, height: size, display: "block", ...style }}
    />
  );
}
