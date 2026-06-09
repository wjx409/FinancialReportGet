import { useState, useRef, useCallback } from 'react'
import { Upload, FileSpreadsheet, X, AlertCircle } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'

interface Props {
  onUpload: (file: File) => Promise<void>
}

export default function UploadZone({ onUpload }: Props) {
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const { task, setFile } = useTaskStore()

  const validate = (file: File): string => {
    const lower = file.name.toLowerCase()
    if (!lower.endsWith('.xlsx') && !lower.endsWith('.xls')) {
      return '仅支持 .xlsx 或 .xls 格式的 Excel 文件'
    }
    if (file.size > 10 * 1024 * 1024) {
      return '文件大小不能超过 10MB'
    }
    return ''
  }

  const handleFile = useCallback((file: File) => {
    const err = validate(file)
    if (err) {
      setError(err)
      return
    }
    setError('')
    setFile(file)
  }, [setFile])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }
  const onDragLeave = () => setDragOver(false)

  if (task.filename && task.status === 'idle') {
    return (
      <div className="card flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <FileSpreadsheet size={20} className="text-[#00E5A0] shrink-0" />
          <div className="min-w-0">
            <p className="text-[#E6EDF3] text-sm font-medium truncate">{task.filename}</p>
            <p className="text-[#8B949E] text-xs mt-0.5">
              已选择 · 等待开始处理
            </p>
          </div>
        </div>
        <button
          onClick={() => {
            useTaskStore.getState().reset()
            setError('')
          }}
          className="btn-secondary flex items-center gap-1.5 text-xs px-3 py-1.5"
        >
          <X size={13} />
          移除
        </button>
      </div>
    )
  }

  return (
    <div>
      <div
        className={`upload-zone rounded-xl p-12 flex flex-col items-center justify-center gap-4 cursor-pointer ${dragOver ? 'drag-over' : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        <div className="w-14 h-14 rounded-2xl bg-[rgba(0,229,160,0.1)] border border-[rgba(0,229,160,0.2)] flex items-center justify-center">
          <Upload size={24} className="text-[#00E5A0]" />
        </div>
        <div className="text-center">
          <p className="text-[#E6EDF3] text-sm font-medium">
            拖拽 Excel 文件到这里
          </p>
          <p className="text-[#8B949E] text-xs mt-1.5">
            或点击选择文件 · 支持 .xlsx / .xls
          </p>
        </div>
        <p className="text-[#484F58] text-xs">
          表头需包含「证券代码」或「公司名称」列
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={onChange}
        />
      </div>

      {error && (
        <div className="mt-3 flex items-center gap-2 text-[#F85149] text-xs">
          <AlertCircle size={13} />
          {error}
        </div>
      )}
    </div>
  )
}
