import { create } from 'zustand'

export interface RowResult {
  row_index: number
  code: string
  name: string
  title: string
  url: string
  publish_date: string
  status: string
}

export interface TaskInfo {
  task_id: string
  status: 'idle' | 'uploading' | 'processing' | 'done' | 'error'
  filename: string
  file: File | null
  total_rows: number
  success_count: number
  fail_count: number
  results: RowResult[]
  log: LogEntry[]
  errorMsg: string
}

export interface LogEntry {
  id: string
  current: number
  total: number
  code: string
  name: string
  status: string
  title: string
  ts: number
}

interface TaskStore {
  task: TaskInfo
  setFile: (file: File) => void
  setUploading: () => void
  setTaskId: (task_id: string, total_rows: number, filename: string) => void
  addLog: (entry: Omit<LogEntry, 'id' | 'ts'>) => void
  setDone: (success_count: number, fail_count: number) => void
  setError: (msg: string) => void
  reset: () => void
}

const initialTask: TaskInfo = {
  task_id: '',
  status: 'idle',
  filename: '',
  file: null,
  total_rows: 0,
  success_count: 0,
  fail_count: 0,
  results: [],
  log: [],
  errorMsg: '',
}

export const useTaskStore = create<TaskStore>((set) => ({
  task: { ...initialTask },

  setFile: (file: File) =>
    set((s) => ({
      task: { ...s.task, filename: file.name, file, status: 'idle' },
    })),

  setUploading: () =>
    set((s) => ({ task: { ...s.task, status: 'uploading' } })),

  setTaskId: (task_id, total_rows, filename) =>
    set((s) => ({
      task: { ...s.task, task_id, total_rows, filename, status: 'processing' },
    })),

  addLog: (entry) =>
    set((s) => ({
      task: {
        ...s.task,
        success_count:
          s.task.success_count + (entry.status === '成功' ? 1 : 0),
        fail_count: s.task.fail_count + (entry.status !== '成功' ? 1 : 0),
        results: [
          {
            row_index: entry.current,
            code: entry.code,
            name: entry.name,
            title: entry.title,
            url: '',
            publish_date: '',
            status: entry.status,
          },
          ...s.task.results,
        ],
        log: [
          { ...entry, id: `${Date.now()}-${Math.random()}`, ts: Date.now() },
          ...s.task.log,
        ].slice(0, 200), // 最多保留 200 条
      },
    })),

  setDone: (success_count, fail_count) =>
    set((s) => ({
      task: { ...s.task, status: 'done', success_count, fail_count },
    })),

  setError: (msg) =>
    set((s) => ({ task: { ...s.task, status: 'error', errorMsg: msg } })),

  reset: () => set({ task: { ...initialTask } }),
}))
