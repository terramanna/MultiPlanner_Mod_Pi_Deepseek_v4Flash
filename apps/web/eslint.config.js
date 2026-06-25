// JS reviewability gate — the cross-language twin of ruff's C901 (see ruff.toml).
//
// Scope is intentionally narrow: only the `complexity` rule is enabled, so this
// gates cyclomatic complexity (max 10, hard error) without turning into a full
// lint sweep. It is the real metric behind the function-size rule in AGENTS.md;
// the 50-logical-line cap in scripts/check_file_size_policy.py is the coarse
// backstop. Broaden later if a fuller lint pass is wanted.
//
// `dist/` is build output and is excluded; node_modules is ignored by default.
export default [
  { ignores: ["dist/**"] },
  {
    files: ["**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
    rules: { complexity: ["error", 10] },
  },
];
