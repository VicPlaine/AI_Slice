import test from 'node:test';
import assert from 'node:assert/strict';

import { evaluateVideoSelection } from '../src/utils/videoFileMatch.ts';

test('完全相同的文件名视为高匹配', () => {
  const result = evaluateVideoSelection({
    taskFilename: '3.31 25K C++ 11K到21k-01.mp4',
    fileName: '3.31 25K C++ 11K到21k-01.mp4',
    mimeType: 'video/mp4',
    sizeBytes: 1024,
  });

  assert.equal(result.isVideoLike, true);
  assert.equal(result.isLikelyMatch, true);
  assert.equal(result.warning, null);
});

test('非视频文件直接标记为无效', () => {
  const result = evaluateVideoSelection({
    taskFilename: '直播回放.mp4',
    fileName: '直播回放.txt',
    mimeType: 'text/plain',
    sizeBytes: 512,
  });

  assert.equal(result.isVideoLike, false);
});

test('文件名差异明显时给出警告', () => {
  const result = evaluateVideoSelection({
    taskFilename: '直播回放.mp4',
    fileName: '别的素材.mp4',
    mimeType: 'video/mp4',
    sizeBytes: 1024,
  });

  assert.equal(result.isLikelyMatch, false);
  assert.match(result.warning ?? '', /可能不是本任务的原视频/);
});
