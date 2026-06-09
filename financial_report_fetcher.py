#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务报告链接自动获取工具
根据 Excel 中的机构名单（证券代码/公司名称），自动从巨潮资讯网 (cninfo.com.cn)
查询最新的财报（年度报告及半年度、季度报告等定期报告）链接，并写入 Excel 对应列。

使用方式:
    python financial_report_fetcher.py <输入文件.xlsx> [输出文件.xlsx]

Excel 格式:
    - 默认第一行为表头
    - 必须包含 "证券代码" 列（如 000001、600519），或 "公司名称" 列
    - 若两者都有，优先使用证券代码
    - 程序会自动在 Excel 中添加/更新以下列:
        * 最新财报标题
        * 最新财报链接
        * 最新财报发布时间
"""

import sys
import time
import re
import argparse
import os
import json
import base64
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font


# -------- 配置 --------
QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
FILE_URL_PREFIX = "http://static.cninfo.com.cn/"
REQUEST_DELAY = 0.8  # 秒，避免反爬
MAX_RETRY = 3
TIME_OUT = 15

# 定期报告分类（涵盖年报、半年报、一/三季度报）
PERIODIC_REPORT_CATEGORY = (
    "category_ndbg_szsh;"      # 年报
    "category_bndbg_szsh;"     # 半年报
    "category_yjdbg_szsh;"     # 一季度报
    "category_sjdbg_szsh;"     # 三季度报
)

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.9",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/disclosure",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


# -------- 工具函数 --------
def normalize_stock_code(code: Any) -> str:
    """将输入的证券代码规范化为 6 位字符串，不足 6 位前面补 0。"""
    if code is None:
        return ""
    raw = str(code).strip()
    if not raw:
        return ""
    # 去除可能出现的小数部分（Excel 读出来可能变成 1.0）
    m = re.search(r"\d+", raw)
    if not m:
        return ""
    digits = m.group(0)
    return digits.zfill(6)


def detect_market(stock_code: str) -> str:
    """
    根据证券代码判断所属板块。
    返回: szse (深市), sse (沪市), bse (北市), 或空
    """
    code = stock_code
    if not code or len(code) < 6:
        return ""
    head = code[:3]
    # 沪市主板/科创板: 600/601/603/605/688, 以及 900(B股)
    if head in {"600", "601", "603", "605", "688", "900"}:
        return "sse"
    # 深市主板/创业板: 000/001/002/300/301, 以及 200(B股)
    if head in {"000", "001", "002", "003", "300", "301", "200"}:
        return "szse"
    # 北交所: 8/9 开头的 4/6 位代码
    if code[0] in {"8", "9"}:
        return "bse"
    # 默认用 szse（巨潮的 szse 实际可覆盖大多数查询）
    return "szse"


def detect_plate(stock_code: str) -> str:
    """配合 column 使用的 plate 参数。"""
    market = detect_market(stock_code)
    if market == "sse":
        return "sh"
    if market == "szse":
        return "sz"
    if market == "bse":
        return "bj"
    return ""


def build_stock_param(stock_code: str, org_id: Optional[str] = None) -> str:
    """
    构造 stock 参数，格式为 "stockCode,orgId"。
    orgId 没有时可以留空，巨潮接口可直接按股票代码查询（内部会自动补齐）。
    """
    code = normalize_stock_code(stock_code)
    if not code:
        return ""
    if org_id:
        return f"{code},{org_id}"
    # 没有 orgId 时，仅传证券代码；我们将在 seDate 中放宽时间限制
    return code


def parse_timestamp(ts: Optional[int]) -> str:
    """将毫秒时间戳转为日期字符串。"""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


# -------- API 调用 --------
def _strip_html(text: str) -> str:
    """去掉搜索结果中的 <em> 等 HTML 标签。"""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", str(text)).strip()


def fetch_latest_report(
    stock_code: str,
    company_name: Optional[str] = None,
) -> Dict[str, str]:
    """
    查询最新的定期报告信息。返回 dict: {title, url, publish_date, status}

    查询策略：
    - 优先使用证券代码作为 searchkey，同时指定板块 column/plate 来提高精度
    - 若无代码则使用公司名称作为 searchkey
    - 在返回结果中过滤出与输入匹配的条目（按 secCode 或公司名）
    """
    code = normalize_stock_code(stock_code)
    result = {"title": "", "url": "", "publish_date": "", "status": ""}

    if not code and not (company_name and str(company_name).strip()):
        result["status"] = "缺少证券代码/公司名称"
        return result

    market = detect_market(code)
    plate = detect_plate(code)
    # 若无法从代码判断市场，留空 column/plate（扩大搜索范围）
    column = market or ""

    # 搜索关键词：优先用代码，代码缺失时用公司名
    keyword = code if code else (company_name or "").strip()

    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": column,
        "tabName": "fulltext",
        "plate": plate,
        "stock": "",
        "searchkey": keyword,
        "secid": "",
        "category": PERIODIC_REPORT_CATEGORY,
        "trade": "",
        "seDate": "",
        "sortName": "time",
        "sortType": "desc",
        "isHLtitle": "true",
    }

    session = requests.Session()
    last_err = ""

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = session.post(
                QUERY_URL,
                headers=DEFAULT_HEADERS,
                data=payload,
                timeout=TIME_OUT,
            )
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                time.sleep(REQUEST_DELAY * attempt)
                continue

            data = resp.json()
            announcements = data.get("announcements", []) or []
            if not announcements:
                result["status"] = "未查询到定期报告"
                return result

            # 过滤：有代码时严格匹配 secCode，否则匹配公司名
            matched = []
            for a in announcements:
                sec_code = (a.get("secCode") or "").strip()
                sec_name = _strip_html(a.get("secName") or "")
                title = _strip_html(a.get("announcementTitle") or "")
                if code and sec_code == code:
                    matched.append((a, title))
                elif (not code) and company_name:
                    name = (company_name or "").strip()
                    if name and (name in sec_name or name in title):
                        matched.append((a, title))
            if not matched:
                # 没有精确匹配时，取第一条（可能搜索结果已足够相关）
                a = announcements[0]
                title = _strip_html(a.get("announcementTitle") or "")
                matched.append((a, title))

            # 第一条是时间最新的
            first, clean_title = matched[0]
            adjunct = first.get("adjunctUrl", "") or ""
            ts = first.get("announcementTime", 0)

            result["title"] = clean_title
            result["url"] = FILE_URL_PREFIX + adjunct if adjunct else ""
            result["publish_date"] = parse_timestamp(ts)
            result["status"] = "成功"
            return result

        except Exception as e:
            last_err = f"异常: {e}"
            time.sleep(REQUEST_DELAY * attempt)

    result["status"] = f"查询失败: {last_err}"
    return result


# -------- Excel 读写 --------
def _find_col_indexes(headers: List[str]) -> Dict[str, int]:
    """从表头行中定位关键列的索引（0-based）。"""
    mapping = {"code": -1, "name": -1, "title": -1, "url": -1, "date": -1}
    for idx, h in enumerate(headers):
        if h is None:
            continue
        text = str(h).strip()
        if mapping["code"] < 0 and (
            text in {"证券代码", "股票代码", "代码", "scode", "stock_code", "stock code"}
            or re.search(r"证券\s*代码|股票\s*代码", text)
        ):
            mapping["code"] = idx
        if mapping["name"] < 0 and (
            text in {"公司名称", "机构名称", "证券简称", "简称", "公司简称", "name", "company"}
            or re.search(r"公司\s*名称|机构\s*名称", text)
        ):
            mapping["name"] = idx
        if mapping["title"] < 0 and (
            text in {"最新财报标题", "公告标题", "report_title"}
        ):
            mapping["title"] = idx
        if mapping["url"] < 0 and (
            text in {"最新财报链接", "公告链接", "下载链接", "report_url", "url"}
        ):
            mapping["url"] = idx
        if mapping["date"] < 0 and (
            text in {"最新财报发布时间", "发布时间", "publish_date"}
        ):
            mapping["date"] = idx
    return mapping


def process_workbook(input_path: str, output_path: str) -> None:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    wb = load_workbook(input_path)
    sheet = wb.active

    # 读取表头
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel 文件为空")

    headers = list(rows[0])
    col_map = _find_col_indexes(headers)

    # 若缺少输出列，则在末尾追加
    new_headers = headers[:]

    def ensure_header(key: int, text: str) -> int:
        if col_map[key] >= 0:
            return col_map[key]
        new_idx = len(new_headers)
        new_headers.append(text)
        col_map[key] = new_idx
        return new_idx

    title_col = ensure_header("title", "最新财报标题")
    url_col = ensure_header("url", "最新财报链接")
    date_col = ensure_header("date", "最新财报发布时间")

    # 写入更新后的表头
    for c_idx, val in enumerate(new_headers, start=1):
        sheet.cell(row=1, column=c_idx, value=val)

    # 遍历数据行
    total = len(rows) - 1
    success = 0
    for r_idx, row in enumerate(rows[1:], start=2):
        values = list(row) + [None] * (len(new_headers) - len(row))
        code_val = values[col_map["code"]] if col_map["code"] >= 0 else ""
        name_val = values[col_map["name"]] if col_map["name"] >= 0 else ""

        code_str = normalize_stock_code(code_val)
        company_str = str(name_val).strip() if name_val else ""

        row_number = r_idx - 1
        print(
            f"[{row_number}/{total}] 正在查询 - "
            f"代码: {code_str or '-'} 名称: {company_str or '-'} ...",
            flush=True,
        )

        info = fetch_latest_report(code_str, company_str)

        # 写入三列
        sheet.cell(row=r_idx, column=title_col + 1, value=info["title"])
        cell_url = sheet.cell(row=r_idx, column=url_col + 1, value=info["url"])
        if info["url"]:
            # 设置为超链接样式（蓝色带下划线，点击可直接打开）
            cell_url.hyperlink = info["url"]
            cell_url.font = Font(color="0563C1", underline="single")
        sheet.cell(row=r_idx, column=date_col + 1, value=info["publish_date"])

        print(f"    -> {info['status']}: {info['title'] or '(空)'}", flush=True)
        if info["status"] == "成功":
            success += 1
        time.sleep(REQUEST_DELAY)

    wb.save(output_path)
    print(
        f"\n完成！共处理 {total} 行，成功 {success} 行，"
        f"结果已保存到: {output_path}"
    )


# -------- 命令行入口 --------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="根据 Excel 机构名单自动获取最新财报链接并写回 Excel"
    )
    parser.add_argument("input", help="输入 Excel 文件路径（.xlsx）")
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="输出 Excel 文件路径（默认: <输入名>_带链接.xlsx）",
    )
    args = parser.parse_args()

    input_path = args.input
    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_带链接{ext or '.xlsx'}"

    try:
        process_workbook(input_path, output_path)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
