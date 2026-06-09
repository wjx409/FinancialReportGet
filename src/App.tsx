import { useCallback } from 'react'
import { Play, Shield } from 'lucide-react'
import Header from './components/Header'
import UploadZone from './components/UploadZone'
import ProgressView from './components/ProgressView'
import ResultView from './components/ResultView'
import { useTaskStore } from './store/taskStore'

export default function App() {
  const { task, setUploading, setTaskId, setError } = useTaskStore()

  const handleUpload = useCallback(async (file: File) => {
    setUploading()
    try {
      const formData = new FormData()
      formData.append('file', file)
      const resp = await fetch('/api/upload', { method: 'POST', body: formData })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail ?? '上传失败')
      setTaskId(data.task_id, data.total_rows, data.filename)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [setUploading, setTaskId, setError])

  const handleStart = useCallback(() => {
    if (!task.file) return
    handleUpload(task.file)
  }, [task.file, handleUpload])

  return (
    <div className="min-h-screen bg-[#0D1117]">
      <Header />

      <main className="max-w-4xl mx-auto px-6 py-10 space-y-6">

        {/* Hero title */}
        <div className="fade-up fade-up-1 scan-line">
          <h2 className="text-2xl font-bold text-[#E6EDF3]">
            批量获取机构最新年报链接
          </h2>
          <p className="text-[#8B949E] text-sm mt-2 leading-relaxed">
            上传含证券代码的 Excel 名单，系统自动从巨潮资讯查询每家机构的
            <span className="text-[#00E5A0]">2025 年年度报告</span>
            PDF 下载链接，一键导出结果文件。
          </p>
        </div>

        {/* Upload section */}
        {task.status === 'idle' && (
          <div className="fade-up fade-up-2">
            <UploadZone onUpload={handleUpload} />
          </div>
        )}

        {/* Uploading state */}
        {task.status === 'uploading' && (
          <div className="card flex items-center gap-3 text-[#8B949E] text-sm">
            <div className="w-5 h-5 border-2 border-[#00E5A0] border-t-transparent rounded-full animate-spin" />
            正在上传 {task.filename}...
          </div>
        )}

        {/* Idle with file selected — show start button */}
        {task.status === 'idle' && task.filename && (
          <div className="fade-up fade-up-2">
            <button onClick={handleStart} className="btn-primary flex items-center gap-2">
              <Play size={15} />
              开始获取
            </button>
          </div>
        )}

        {/* Processing */}
        {task.status === 'processing' && task.task_id && (
          <div className="fade-up fade-up-2 space-y-4">
            <div className="card">
              <div className="flex items-center gap-2 mb-4">
                <Shield size={14} className="text-[#00E5A0]" />
                <span className="text-sm text-[#8B949E]">查询目标：2025 年年度报告</span>
              </div>
              <ProgressView taskId={task.task_id} />
            </div>
          </div>
        )}

        {/* Done */}
        {task.status === 'done' && (
          <div className="fade-up fade-up-2">
            <ResultView />
          </div>
        )}

        {/* Error */}
        {task.status === 'error' && (
          <div className="card border-[#F85149]">
            <p className="text-[#F85149] text-sm">处理出错：{task.errorMsg}</p>
            <button
              onClick={() => useTaskStore.getState().reset()}
              className="btn-secondary mt-3 text-xs"
            >
              重试
            </button>
          </div>
        )}

        {/* Footer note */}
        <div className="fade-up fade-up-4 pt-4 border-t border-[#30363D]">
          <p className="text-xs text-[#484F58] leading-relaxed">
            数据来源：巨潮资讯网（www.cninfo.com.cn），中国证监会指定信息披露网站。
            查询接口为公开公告检索接口，每次请求间隔 0.8 秒以避免触发反爬限制。
            结果文件中的链接可直接点击下载 PDF。
          </p>
        </div>
      </main>
    </div>
  )
}
