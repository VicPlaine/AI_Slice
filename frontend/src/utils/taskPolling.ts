const TERMINAL_TASK_STATUSES = new Set(['done', 'failed', 'canceled']);

export function shouldPollTaskList(tasks: Array<{ status: string }>): boolean {
  return tasks.some((task) => !TERMINAL_TASK_STATUSES.has(task.status));
}
