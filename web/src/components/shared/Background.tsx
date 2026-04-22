const Background = () => {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#f6faf8]"
    >
      {/* Top-left large emerald blob */}
      <div className="absolute -left-40 -top-40 h-130 w-130 rounded-full bg-emerald-200/40 blur-[120px]" />

      {/* Top-right soft teal blob */}
      <div className="absolute -right-32 top-0 h-100 w-100 rounded-full bg-teal-200/30 blur-[100px]" />

      {/* Center subtle green glow */}
      <div className="absolute left-1/2 top-1/3 h-90 w-150 -translate-x-1/2 rounded-full bg-emerald-100/50 blur-[130px]" />

      {/* Bottom-left muted lime accent */}
      <div className="absolute -bottom-24 left-1/4 h-80 w-80 rounded-full bg-lime-200/25 blur-[90px]" />

      {/* Bottom-right deep emerald blob */}
      <div className="absolute -bottom-32 -right-20 h-110 w-110 rounded-full bg-emerald-300/20 blur-[110px]" />

      {/* Subtle dot-grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "radial-gradient(circle, #003d29 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />
    </div>
  );
};

export default Background;
