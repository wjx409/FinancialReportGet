"""数据模型：任务状态与行结果"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class RowResult:
    row_index: int       # Excel 行号（从 1 开始）
    code: str           # 证券代码
    name: str           # 公司名称
    title: str         # 财报标题
    url: str           # PDF 链接
    publish_date: str  # 发布时间
    status: str        # 处理状态


@dataclass
class TaskState:
    task_id: str
    filename: str
    total_rows: int
    success_count: int = 0
    fail_count: int = 0
    status: str = "pending"   # pending | processing | done | error
    results: List[RowResult] = field(default_factory=list)
    result_file_path: str = ""
