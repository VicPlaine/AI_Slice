import test from 'node:test';
import assert from 'node:assert/strict';

import { shouldPollTaskList } from '../src/utils/taskPolling.ts';

test('存在 pending 任务时继续轮询', () => {
  assert.equal(
    shouldPollTaskList([
      { status: 'pending' },
      { status: 'done' },
    ]),
    true,
  );
});

test('存在处理中任务时继续轮询', () => {
  assert.equal(
    shouldPollTaskList([
      { status: 'analyzing' },
      { status: 'done' },
    ]),
    true,
  );
});

test('全部任务都结束时停止轮询', () => {
  assert.equal(
    shouldPollTaskList([
      { status: 'done' },
      { status: 'failed' },
    ]),
    false,
  );
});

test('已取消任务属于终态，不再轮询', () => {
  assert.equal(shouldPollTaskList([{ status: 'canceled' }]), false);
});
