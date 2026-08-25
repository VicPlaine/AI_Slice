import test from 'node:test';
import assert from 'node:assert/strict';

import { formatClipTime, getClipDisplayRange } from '../src/utils/clipTime.ts';

test('音频直传任务会把容器偏移换算回剪映时间', () => {
  const range = getClipDisplayRange({
    startTime: 2482,
    endTime: 2533,
    videoStartOffset: 2482,
    hasGeneratedClip: false,
  });

  assert.deepEqual(range, {
    startTime: 0,
    endTime: 51,
  });
  assert.equal(formatClipTime(range.startTime), '0:00');
  assert.equal(formatClipTime(range.endTime), '0:51');
});

test('已生成视频切片的任务保留原始切片时间', () => {
  const range = getClipDisplayRange({
    startTime: 2482,
    endTime: 2533,
    videoStartOffset: 2482,
    hasGeneratedClip: true,
  });

  assert.deepEqual(range, {
    startTime: 2482,
    endTime: 2533,
  });
});

test('没有显著偏移时直接显示原时间', () => {
  const range = getClipDisplayRange({
    startTime: 71,
    endTime: 154,
    videoStartOffset: 0.4,
    hasGeneratedClip: false,
  });

  assert.deepEqual(range, {
    startTime: 71,
    endTime: 154,
  });
  assert.equal(formatClipTime(range.startTime), '1:11');
  assert.equal(formatClipTime(range.endTime), '2:34');
});
