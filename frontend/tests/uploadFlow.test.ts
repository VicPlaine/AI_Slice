import test from 'node:test';
import assert from 'node:assert/strict';

import { classifyUploadFailure } from '../src/utils/uploadFlow.ts';

test('AbortError 会被识别为用户取消', () => {
  assert.deepEqual(
    classifyUploadFailure(new DOMException('The operation was aborted.', 'AbortError')),
    {
      kind: 'cancelled',
      message: '已取消当前处理',
    },
  );
});

test('axios 超时错误会给出明确提示', () => {
  assert.deepEqual(
    classifyUploadFailure({
      code: 'ECONNABORTED',
      message: 'timeout of 300000ms exceeded',
    }),
    {
      kind: 'timeout',
      message: '上传超时，请检查网络后重试',
    },
  );
});

test('普通错误保留原始消息', () => {
  assert.deepEqual(
    classifyUploadFailure(new Error('处理失败')),
    {
      kind: 'failed',
      message: '处理失败',
    },
  );
});
