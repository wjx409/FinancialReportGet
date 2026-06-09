import { useState } from 'react'
import { Download, CheckCircle2, XCircle, ExternalLink, RotateCcw } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'

export default function ResultView() {
  const { task, reset } = useTaskStore()
  const [downloading, setDownloading] = useState(false)

  const handleDownload = async () => {
    if (!task.task_id) return
    setDownloading(true)
    try {
      const resp = await fetch(`/api/download/${task.task_id}`)
      if (!resp.ok) throw new Error('下载失败')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${task.filename.replace(/\.(xlsx|xls)$/i, '')}_财报链接_2025.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('下载失败，请重试')
    } finally {
      setDownloading(false)
    }
  }

  const successRate =
    task.total_rows > 0
      ? Math.round((task.success_count / task.total_rows) * 100)
      : 0

  return (
    <div className="space-y-5">
      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="card flex flex-col items-center gap-1 py-5">
          <span className="text-2xl font-bold text-[#00E5A0] font-mono">{task.success_count}</span>
          <span className="text-xs text-[#8B949E]">成功获取</span>
        </div>
        <div className="card flex flex-col items-center gap-1 py-5">
          <span className="text-2xl font-bold text-[#F85149] font-mono">{task.fail_count}</span>
          <span className="text-xs text-[#8B949E]">未查到</span>
        </div>
        <div className="card flex flex-col items-center gap-1 py-5">
          <span className="text-2xl font-bold text-[#58A6FF] font-mono">{successRate}%</span>
          <span className="text-xs text-[#8B949E]">成功率</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="btn-primary flex items-center gap-2"
        >
          <Download size={15} />
          {downloading ? '生成中...' : '下载结果 Excel'}
        </button>
        <button onClick={reset} className="btn-secondary flex items-center gap-2">
          <RotateCcw size={14} />
          处理新文件
        </button>
      </div>

      {/* Result table (show first 20) */}
      {task.results.length > 0 && (
        <div className="card p-0 overflow-x-auto">
          <div className="px-4 py-3 border-b border-[#30363D] flex items-center gap-2">
            <CheckCircle2 size={13} className="text-[#00E5A0]" />
            <span className="text-sm text-[#E6EDF3] font-medium">结果预览</span>
            <span className="text-xs text-[#8B949E] ml-auto">
              显示 {Math.min(20, task.results.length)} / {task.results.length} 条
            </span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>证券代码</th>
                <th>公司名称</th>
                <th>最新财报标题</th>
                <th>发布时间</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {task.results.slice(0, 20).map((r, i) => (
                <tr key={i}>
                  <td className="text-[#484F58] font-mono">{r.row_index}</td>
                  <td className="font-mono text-[#58A6FF]">{r.code || '-'}</td>
                  <td className="text-[#E6EDF3]">{r.name || '-'}</td>
                  <td>
                    {r.url ? (
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#00E5A0] hover:underline flex items-center gap-1"
                      >
                        <span className="truncate max-w-[200px]">{r.title}</span>
                        <ExternalLink size={10} />
                      </a>
                    ) : (
                      <span className="text-[#484F58]">{r.title || '-'}</span>
                    )}
                  </td>
                  <td className="text-[#8B949E] font-mono text-xs">{r.publish_date || '-'}</td>
                  <td>
                    {r.status === '成功' ? (
                      <span className="flex items-center gap-1 text-[#00E5A0] text-xs">
                        <CheckCircle2 size={12} /> 成功
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[#F85149] text-xs" title={r.status}>
                        <XCircle size={12} /> {r.status.slice(0, 8)}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {task.fail_count > 0 && (
        <div className="text-xs text-[#8B949E] px-1">
          <XCircle size={12} className="inline mr-1 text-[#F85149]" />
          有 {task.fail_count} 行未查到对应年报，可能原因：公司未上市、代码错误、或该年份无年报披露。
        </div>
      )}
    </div>
  )
}
