import type { SceneMode, TaskDetail, TaskListItem } from '../types/task';

type TaskDetailRequiredFields = Pick<
  TaskDetail,
  'id' | 'status' | 'video_filename' | 'progress' | 'progress_message' | 'created_at' | 'updated_at'
>;

type TaskDetailOptionalFields = Partial<
  Omit<
    Pick<TaskDetail, 'video_oss_key' | 'video_duration' | 'video_start_offset' | 'scene_mode' | 'error_message' | 'clips'>,
    'scene_mode'
  > & { scene_mode: SceneMode | 'interview' | null }
>;

export type TaskDetailResponseInput = TaskDetailRequiredFields & TaskDetailOptionalFields;

export function normalizeSceneMode(sceneMode: string | null | undefined): SceneMode {
  if (sceneMode === 'interview') return 'podcast';
  if (sceneMode === 'podcast' || sceneMode === 'lecture') return sceneMode;
  return 'livestream';
}

export type TaskListItemResponseInput = Omit<TaskListItem, 'scene_mode'> & {
  scene_mode?: string | null;
};

export function normalizeTaskListItem(task: TaskListItemResponseInput): TaskListItem {
  return {
    ...task,
    scene_mode: normalizeSceneMode(task.scene_mode),
  };
}

export function normalizeTaskDetailResponse(task: TaskDetailResponseInput): TaskDetail {
  return {
    ...task,
    video_oss_key: task.video_oss_key ?? '',
    video_duration: task.video_duration ?? null,
    video_start_offset: task.video_start_offset ?? 0,
    scene_mode: normalizeSceneMode(task.scene_mode),
    error_message: task.error_message ?? null,
    clips: task.clips ?? [],
  };
}
