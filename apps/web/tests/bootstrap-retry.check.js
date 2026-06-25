import assert from "node:assert/strict";
import { retryUntilReady } from "../src/bootstrap-retry.js";

const events = [];
let attempts = 0;

const result = await retryUntilReady(
  async () => {
    attempts += 1;
    if (attempts < 2) {
      throw new Error("not ready");
    }
    return "ok";
  },
  {
    delayMs: 0,
    wait: async () => {
      events.push("wait");
    },
    onRetry: () => {
      events.push("retry");
    },
  }
);

assert.equal(result, "ok");
assert.equal(attempts, 2);
assert.deepEqual(events, ["retry", "wait"]);
