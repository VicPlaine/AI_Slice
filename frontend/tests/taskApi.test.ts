import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeSceneMode,
  normalizeTaskDetailResponse,
} from '../src/utils/taskApi.ts';

test('历史 interview 场景会显示为新的播客访谈模式', () => {
  assert.equal(normalizeSceneMode('interview'), 'podcast');
});

test('任务详情缺少可选字段时会补默认值', () => {
  const normalized = normalizeTaskDetailResponse({
    id: 'task-1',
    status: 'pending',
    video_filename: 'demo.mp4',
    progress: 0,
    progress_message: '等待处理',
    created_at: '2026-04-08T00:00:00Z',
    updated_at: '2026-04-08T00:00:00Z',
  });

  assert.equal(normalized.video_oss_key, '');
  assert.equal(normalized.video_start_offset, 0);
  assert.equal(normalized.error_message, null);
  assert.deepEqual(normalized.clips, []);
});

test('任务详情会保留已有 clips 数据', () => {
  const normalized = normalizeTaskDetailResponse({
    id: 'task-2',
    status: 'done',
    video_filename: 'done.mp4',
    progress: 100,
    progress_message: '处理完成',
    created_at: '2026-04-08T00:00:00Z',
    updated_at: '2026-04-08T00:00:00Z',
    clips: [
      {
        id: 'clip-1',
        clip_index: 1,
        title: '片段 1',
        summary: '摘要',
        clip_type: '高能',
        start_time: 12,
        end_time: 24,
        duration: 12,
        virality_score: 9,
        suggested_caption: '文案',
        download_url: '/api/clips/clip-1/download',
      },
    ],
  });

  assert.equal(normalized.clips.length, 1);
  assert.equal(normalized.clips[0].title, '片段 1');
  assert.equal(normalized.clips[0].download_url, '/api/clips/clip-1/download');
});
