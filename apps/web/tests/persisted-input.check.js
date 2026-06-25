import assert from "node:assert/strict";
import { bindPersistedInput } from "../src/persisted-input.js";

function storageWith(value) {
  const entries = new Map(value === undefined ? [] : [["search", value]]);
  return {
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, nextValue) => entries.set(key, String(nextValue)),
    value: (key) => entries.get(key),
  };
}

const listeners = {};
const input = {
  value: "",
  addEventListener: (event, listener) => {
    listeners[event] = listener;
  },
};
const storage = storageWith("52.324784, 7.467435");

bindPersistedInput(input, "search", storage);
assert.equal(input.value, "52.324784, 7.467435");

input.value = "Bentheim";
listeners.input();
assert.equal(storage.value("search"), "Bentheim");
