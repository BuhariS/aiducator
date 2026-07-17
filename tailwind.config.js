module.exports = {
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
    "./frontend/src/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#14213D",
        emerald: "#0F766E",
        sunshine: "#F4B942",
        cloud: "#F6F8FB"
      },
      boxShadow: {
        card: "0 12px 35px rgba(20, 33, 61, 0.08)"
      }
    }
  },
  plugins: []
};
