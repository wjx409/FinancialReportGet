import { useTaskStore } from '../store/taskStore'

const STATUS_LABELS = {
  idle: '空闲',
  uploading: '上传中',
  processing: '处理中',
  done: '已完成',
  error: '出错',
}

export default function Header() {
  const status = useTaskStore((s) => s.task.status)

  return (
    <header className="border-b border-[#30363D] bg-[#161B22]">
      <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div className="w-8 h-8 rounded-lg bg-[#00E5A0] flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 10 L5 6 L8 8 L11 4 L14 7" stroke="#0D1117" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <h1 className="text-[#E6EDF3] font-semibold text-base leading-tight">
              财报链接获取工具
            </h1>
            <p className="text-[#8B949E] text-xs mt-0.5">
              基于巨潮资讯 · 批量获取年报链接
            </p>
          </div>
        </div>

        {/* Status badge */}
        <div className="flex items-center gap-2">
          <span className={`status-dot ${status}`} />
          <span className="text-xs text-[#8B949E] font-mono">
            {STATUS_LABELS[status] ?? status}
          </span>
        </div>
      </div>
    </header>
  )
}
