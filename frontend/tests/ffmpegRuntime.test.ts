import test from 'node:test';
import assert from 'node:assert/strict';

import { createSharedFFmpegRuntime } from '../src/services/ffmpegRuntime.ts';

test('共享 runtime 会复用同一个 FFmpeg 实例', async () => {
  let createCount = 0;
  const loadCalls: Array<{ coreURL: string; wasmURL: string }> = [];
  const instance = {
    load: async (urls: { coreURL: string; wasmURL: string }) => {
      loadCalls.push(urls);
    },
    terminate: () => {},
  };

  const runtime = createSharedFFmpegRuntime({
    createFFmpeg: () => {
      createCount += 1;
      return instance;
    },
    resolveCoreUrls: async () => ({
      coreURL: 'blob:core',
      wasmURL: 'blob:wasm',
    }),
  });

  const first = await runtime.getFFmpeg();
  const second = await runtime.getFFmpeg();

  assert.equal(first, instance);
  assert.equal(second, instance);
  assert.equal(createCount, 1);
  assert.deepEqual(loadCalls, [{ coreURL: 'blob:core', wasmURL: 'blob:wasm' }]);
});

test('加载失败后会重置缓存并允许重试', async () => {
  let createCount = 0;
  let shouldFail = true;

  const runtime = createSharedFFmpegRuntime({
    createFFmpeg: () => {
      createCount += 1;
      return {
        load: async () => {
          if (shouldFail) {
            throw new Error('load failed');
          }
        },
        terminate: () => {},
      };
    },
    resolveCoreUrls: async () => ({
      coreURL: 'blob:core',
      wasmURL: 'blob:wasm',
    }),
  });

  await assert.rejects(runtime.getFFmpeg(), /load failed/);

  shouldFail = false;
  const instance = await runtime.getFFmpeg();

  assert.ok(instance);
  assert.equal(createCount, 2);
});

test('加载时收到 abort 会终止实例并重置缓存', async () => {
  let terminateCount = 0;
  let createCount = 0;
  const controller = new AbortController();

  const runtime = createSharedFFmpegRuntime({
    createFFmpeg: () => {
      createCount += 1;
      return {
        load: async (_urls: unknown, { signal }: { signal?: AbortSignal } = {}) => {
          if (!signal) {
            return;
          }
          if (signal?.aborted) {
            throw new DOMException('aborted', 'AbortError');
          }
          await new Promise((_, reject) => {
            signal?.addEventListener(
              'abort',
              () => reject(new DOMException('aborted', 'AbortError')),
              { once: true },
            );
          });
        },
        terminate: () => {
          terminateCount += 1;
        },
      };
    },
    resolveCoreUrls: async () => ({
      coreURL: 'blob:core',
      wasmURL: 'blob:wasm',
    }),
  });

  const pending = runtime.getFFmpeg({ signal: controller.signal });
  controller.abort();

  await assert.rejects(pending, (error: unknown) => {
    assert.equal(error instanceof DOMException, true);
    assert.equal((error as DOMException).name, 'AbortError');
    return true;
  });

  await runtime.getFFmpeg();

  assert.equal(terminateCount, 1);
  assert.equal(createCount, 2);
});
