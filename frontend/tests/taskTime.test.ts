import test from 'node:test';
import assert from 'node:assert/strict';

import {
  formatShanghaiDateTime,
  formatTaskDuration,
  parseBackendDateTime,
} from '../src/utils/taskTime.ts';

test('时长超过 1 小时时显示 H:MM:SS', () => {
  assert.equal(formatTaskDuration(7988), '2:13:08');
});

test('时长不足 1 小时时显示 M:SS', () => {
  assert.equal(formatTaskDuration(245), '4:05');
});

test('未知时长返回 null', () => {
  assert.equal(formatTaskDuration(null), null);
});

test('后端无时区时间按 UTC 解析', () => {
  assert.equal(
    parseBackendDateTime('2026-08-24T07:13:19').toISOString(),
    '2026-08-24T07:13:19.000Z',
  );
});

test('任务时间固定显示为东八区', () => {
  assert.equal(
    formatShanghaiDateTime('2026-08-24T07:13:19'),
    '2026/08/24 15:13:19',
  );
});
