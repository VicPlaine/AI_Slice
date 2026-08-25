import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildLocalClipSpecs,
  buildClipArchiveName,
  summarizeLocalClipExport,
} from '../src/utils/localClipExport.ts';

test('导出规格保留原始 clip 时间，不使用展示时间', () => {
  const specs = buildLocalClipSpecs([
    { clip_index: 1, title: '第一段', start_time: 2482, end_time: 2533 },
  ]);

  assert.deepEqual(specs[0], {
    clipIndex: 1,
    title: '第一段',
    startTime: 2482,
    endTime: 2533,
    duration: 51,
    outputName: '01_第一段.mp4',
  });
});

test('非法字符会被替换成安全文件名', () => {
  const specs = buildLocalClipSpecs([
    { clip_index: 2, title: 'A/B:C*D?', start_time: 10, end_time: 20 },
  ]);

  assert.equal(specs[0].outputName, '02_A_B_C_D_.mp4');
});

test('零时长片段会被过滤', () => {
  const specs = buildLocalClipSpecs([
    { clip_index: 3, title: '空片段', start_time: 10, end_time: 10 },
  ]);

  assert.equal(specs.length, 0);
});

test('汇总文案会区分成功和失败数量', () => {
  assert.equal(
    summarizeLocalClipExport({
      succeeded: 9,
      failed: [{ clipIndex: 4, title: '片段 4', reason: 'ffmpeg error' }],
    }),
    '已成功导出 9 段，失败 1 段',
  );
});

test('归档文件名会继承原视频基础名', () => {
  assert.equal(buildClipArchiveName('直播回放.mp4'), '直播回放_切片.zip');
});
