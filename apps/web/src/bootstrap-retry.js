export async function retryUntilReady(task, options = {}) {
  const delayMs = options.delayMs ?? 1000;
  const signal = options.signal;
  const wait = options.wait ?? defaultWait;
  const onRetry = options.onRetry ?? (() => {});

  while (!signal?.aborted) {
    try {
      return await task();
    } catch (error) {
      onRetry(error);
      if (signal?.aborted) {
        return undefined;
      }
      await wait(delayMs, signal);
    }
  }

  return undefined;
}

function defaultWait(delayMs, signal) {
  return new Promise((resolve) => {
    const timeoutId = globalThis.setTimeout(resolve, delayMs);
    if (!signal) {
      return;
    }
    signal.addEventListener(
      "abort",
      () => {
        globalThis.clearTimeout(timeoutId);
        resolve();
      },
      { once: true }
    );
  });
}
