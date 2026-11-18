import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const config = [
  { ignores: [".next/**", "node_modules/**", "coverage/**", "next-env.d.ts"] },
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    rules: {
      // Data-fetching and auth bootstrap hooks intentionally synchronise React
      // state with external async systems (API and Supabase Auth).
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default config;
