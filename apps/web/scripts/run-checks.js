#!/usr/bin/env node
import { globSync } from "node:fs";
import { spawn, execSync } from "node:child_process";

const files = globSync("tests/*.check.js");
const results = { pass: 0, fail: 0, skipped: 0 };
for (const file of files) {
  const p = spawn("node", [file], { stdio: "inherit", shell: true });
  const code = await new Promise((resolve) => p.on("close", resolve));
  if (code === 0) {
    results.pass++;
  } else {
    console.error(`FAIL: ${file}`);
    results.fail++;
  }
}
console.log(`\n${results.pass} passed, ${results.fail} failed`);
process.exit(results.fail > 0 ? 1 : 0);