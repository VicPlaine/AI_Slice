export type SceneMode = 'livestream' | 'podcast' | 'lecture';

export interface SceneModeOption {
  value: SceneMode;
  label: string;
  description: string;
  icon: string;
}

export const SCENE_MODE_OPTIONS: SceneModeOption[] = [
  {
    value: 'livestream',
    label: '直播回放',
    description: '从直播中找高能、搞笑、干货等爆款片段，30秒~3分钟短视频',
    icon: '🎬',
  },
  {
    value: 'podcast',
    label: '播客访谈',
    description: '提取鲜明观点、人物故事与争议话题，生成1~4分钟片段',
    icon: '🎙️',
  },
  {
    value: 'lecture',
    label: '课程讲座',
    description: '按知识点切分，每个切片5~10分钟，保留完整讲解',
    icon: '📚',
  },
];

export interface SpecialEffect {
  time_point: string;
  effect: string;
  reason: string;
}

export interface EditingGuide {
  special_effects: SpecialEffect[];
  music: string;
  subtitles: string[];
  rhythm: string;
  cover: string;
}

export interface TaskClip {
  id: string;
  clip_index: number;
  title: string;
  summary: string;
  clip_type: string;
  start_time: number;
  end_time: number;
  duration: number;
  virality_score: number;
  suggested_caption: string;
  oss_key?: string | null;
  download_url?: string | null;
  viral_titles?: string[] | null;
  editing_guide?: EditingGuide | null;
}

export interface TaskListItem {
  id: string;
  status: string;
  video_filename: string;
  video_duration?: number | null;
  scene_mode: SceneMode;
  progress: number;
  progress_message: string;
  created_at: string;
}

export interface TaskDetail extends TaskListItem {
  video_oss_key: string;
  video_start_offset: number;
  error_message: string | null;
  updated_at: string;
  clips: TaskClip[];
}
