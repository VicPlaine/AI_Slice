export function formatTaskDuration(durationSeconds: number | null | undefined): string | null {
  if (
    durationSeconds === null ||
    durationSeconds === undefined ||
    !Number.isFinite(durationSeconds) ||
    durationSeconds < 0
  ) {
    return null;
  }

  const totalSeconds = Math.round(durationSeconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }

  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

const HAS_TIMEZONE_SUFFIX = /(Z|[+-]\d{2}:?\d{2})$/i;

export function parseBackendDateTime(value: string): Date {
  // 后端数据库保存的是 UTC 的无时区 datetime；浏览器会误当成本地时间。
  const normalized = HAS_TIMEZONE_SUFFIX.test(value) ? value : `${value}Z`;
  return new Date(normalized);
}

export function formatShanghaiDateTime(value: string, compact = false): string {
  const date = parseBackendDateTime(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: compact ? undefined : 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: compact ? undefined : '2-digit',
    hour12: false,
  }).format(date);
}
