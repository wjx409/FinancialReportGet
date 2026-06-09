"""
财报链接获取工具 - FastAPI 后端
"""
import asyncio
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.models import TaskState, RowResult
from api.processor import process_excel, TEMP_DIR, get_task_dir

# -------- 全局任务存储 --------
_tasks: Dict[str, TaskState] = {}
_tasks_lock = threading.Lock()
_websockets: Dict[str, list[WebSocket]] = {}

app = FastAPI(title="财报链接获取工具", version="1.0")


# -------- Pydantic 模型 --------
class UploadResponse(BaseModel):
    task_id: str
    total_rows: int
    filename: str


# -------- 辅助函数 --------
def broadcast(task_id: str, msg: dict):
    """向所有连接的 WebSocket 推送消息"""
    for ws in _websockets.get(task_id, []):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(msg), asyncio.get_event_loop())
        except Exception:
            pass


def cleanup_task(task_id: str):
    """删除任务临时目录"""
    task_dir = get_task_dir(task_id)
    if task_dir.exists():
        shutil.rmtree(task_dir)
    with _tasks_lock:
        _tasks.pop(task_id, None)
        _websockets.pop(task_id, None)


# -------- 路由 --------
@app.get("/")
async def root():
    """前端单页入口"""
    static_path = Path(__file__).parent.parent / "dist"
    index = static_path / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="前端未构建，请先运行 npm run build")


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """接收 Excel 文件，创建任务"""
    # 校验扩展名
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls 文件")

    # 校验大小（10MB）
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    # Magic byte 校验（ZIP/XLSX 均以 PK 开头）
    if not content[:2] == b"PK":
        raise HTTPException(status_code=400, detail="文件格式无效，必须为 Excel 文件")

    task_id = str(uuid.uuid4())
    task_dir = get_task_dir(task_id)
    input_path = task_dir / "input.xlsx"
    input_path.write_bytes(content)

    # 读取行数
    import openpyxl
    wb = openpyxl.load_workbook(input_path)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    total_rows = len(rows) - 1  # 减去表头
    if total_rows <= 0:
        raise HTTPException(status_code=400, detail="Excel 文件无数据行")
    if total_rows > 500:
        raise HTTPException(status_code=400, detail="单次处理最多 500 行，当前文件有 " + str(total_rows) + " 行")

    with _tasks_lock:
        _tasks[task_id] = TaskState(
            task_id=task_id,
            filename=file.filename,
            total_rows=total_rows,
        )
    _websockets[task_id] = []

    # 后台启动处理
    threading.Thread(
        target=_process_task,
        args=(task_id, str(input_path)),
        daemon=True,
    ).start()

    return UploadResponse(task_id=task_id, total_rows=total_rows, filename=file.filename)


def _process_task(task_id: str, input_path: str):
    """后台处理线程：逐行查询，写 Excel，推送 WebSocket"""
    task = _tasks.get(task_id)
    if not task:
        return

    task.status = "processing"

    def on_progress(current: int, total: int, row_result: dict):
        if task_id in _tasks:
            _tasks[task_id].success_count += (1 if row_result["status"] == "成功" else 0)
            _tasks[task_id].fail_count += (1 if row_result["status"] != "成功" else 0)
            _tasks[task_id].results.append(RowResult(**row_result))
        broadcast(task_id, {
            "type": "progress",
            "current": current,
            "total": total,
            "code": row_result.get("code", ""),
            "name": row_result.get("name", ""),
            "status": row_result.get("status", ""),
            "title": row_result.get("title", ""),
            "url": row_result.get("url", ""),
            "publish_date": row_result.get("publish_date", ""),
        })

    try:
        results, out_path = process_excel(input_path, task_id, on_progress)
        if task_id in _tasks:
            _tasks[task_id].status = "done"
            _tasks[task_id].result_file_path = out_path
        broadcast(task_id, {
            "type": "done",
            "task_id": task_id,
            "success_count": sum(1 for r in results if r["status"] == "成功"),
            "fail_count": sum(1 for r in results if r["status"] != "成功"),
        })
    except Exception as e:
        if task_id in _tasks:
            _tasks[task_id].status = "error"
        broadcast(task_id, {"type": "error", "message": str(e)})


@app.websocket("/api/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    if task_id not in _websockets:
        _websockets[task_id] = []
    _websockets[task_id].append(websocket)
    try:
        # 发送当前状态
        with _tasks_lock:
            task = _tasks.get(task_id)
        if task:
            await websocket.send_json({
                "type": "init",
                "status": task.status,
                "total_rows": task.total_rows,
                "success_count": task.success_count,
                "fail_count": task.fail_count,
            })
        while True:
            # 保持连接，客户端主动关闭
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if task_id in _websockets:
            _websockets[task_id] = [ws for ws in _websockets[task_id] if ws != websocket]


@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {
        "task_id": task_id,
        "status": task.status,
        "filename": task.filename,
        "total_rows": task.total_rows,
        "success_count": task.success_count,
        "fail_count": task.fail_count,
        "results": [
            {
                "row_index": r.row_index,
                "code": r.code,
                "name": r.name,
                "title": r.title,
                "url": r.url,
                "publish_date": r.publish_date,
                "status": r.status,
            }
            for r in task.results
        ],
    }


@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if task.status != "done" or not task.result_file_path:
        raise HTTPException(status_code=400, detail="任务尚未完成，无法下载")
    path = Path(task.result_file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="结果文件丢失，请重新处理")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    cleanup_task(task_id)
    return {"ok": True}


# -------- 静态文件（前端构建产物）--------
dist_path = Path(__file__).parent.parent / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True))
