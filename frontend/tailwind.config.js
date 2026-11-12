/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        fondo: { DEFAULT: "#070b14", 2: "#0b1220", 3: "#101a2c" },
        panel: { DEFAULT: "rgba(13,20,35,0.78)", solido: "#0d1423", borde: "rgba(148,163,184,0.12)" },
        acento: { DEFAULT: "#3b82f6", cian: "#22d3ee", suave: "#60a5fa" },
        estado: { disponible: "#22c55e", ocupado: "#f59e0b", servicio: "#ef4444", inactivo: "#64748b" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 10px 40px -12px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.03)",
        brillo: "0 0 0 1px rgba(59,130,246,0.35), 0 0 24px -4px rgba(34,211,238,0.35)",
      },
      backgroundImage: {
        rejilla: "linear-gradient(rgba(148,163,184,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.05) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};
