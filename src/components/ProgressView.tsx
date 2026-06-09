import { useEffect, useRef } from 'react'
import { CheckCircle2, XCircle, Loader2, Clock } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'

interface Props {
  taskId: string
}

export default function ProgressView({ taskId }: Props) {
  const { task, addLog, setDone, setError } = useTaskStore()
  const wsRef = useRef<WebSocket | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let connected = false

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/ws/${taskId}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => { connected = true }
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string)
          if (msg.type === 'init') {
            // ignore
          } else if (msg.type === 'progress') {
            addLog({
              current: msg.current,
              total: msg.total,
              code: msg.code,
              name: msg.name,
              status: msg.status,
              title: msg.title,
            })
          } else if (msg.type === 'done') {
            setDone(msg.success_count, msg.fail_count)
          } else if (msg.type === 'error') {
            setError(msg.message)
          }
        } catch {}
      }

      ws.onclose = () => {
        connected = false
        // 重连
        if (useTaskStore.getState().task.status === 'processing') {
          reconnectTimer.current = setTimeout(connect, 2000)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()
    return () => {
      connected = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [taskId, addLog, setDone, setError])

  // 滚动到最新日志
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [task.log.length])

  const pct =
    task.total_rows > 0
      ? Math.round(((task.success_count + task.fail_count) / task.total_rows) * 100)
      : 0

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[#8B949E] text-xs">
          <Loader2 size={13} className="animate-spin text-[#00E5A0]" />
          正在查询巨潮资讯接口
        </div>
        <div className="flex items-center gap-3">
          <span className="stat-pill success">
            <CheckCircle2 size={11} />
            {task.success_count} 成功
          </span>
          <span className="stat-pill fail">
            <XCircle size={11} />
            {task.fail_count} 失败
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-[#8B949E] mb-2 font-mono">
          <span>{task.success_count + task.fail_count} / {task.total_rows} 行</span>
          <span>{pct}%</span>
        </div>
        <div className="progress-bar-track">
          <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Log list */}
      <div className="card p-0 max-h-64 overflow-y-auto">
        <div className="px-4 py-2 border-b border-[#30363D] flex items-center gap-2">
          <Clock size={12} className="text-[#8B949E]" />
          <span className="text-xs text-[#8B949E]">实时日志</span>
        </div>
        {task.log.length === 0 ? (
          <div className="py-8 text-center text-xs text-[#484F58]">
            等待处理...
          </div>
        ) : (
          <div>
            {task.log.map((entry) => (
              <div key={entry.id} className="log-entry flex items-center gap-3">
                <span className="text-[#484F58] text-xs w-12 shrink-0">
                  #{entry.current}
                </span>
                <span className="text-[#8B949E] text-xs w-16 shrink-0 truncate">
                  {entry.code || entry.name || '-'}
                </span>
                <span
                  className={`text-xs shrink-0 ${entry.status === '成功' ? 'text-[#00E5A0]' : 'text-[#F85149]'}`}
                >
                  {entry.status}
                </span>
                <span className="text-[#E6EDF3] text-xs truncate flex-1">
                  {entry.title || '-'}
                </span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        )}
      </div>
    </div>
  )
}
