#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成示例 Excel，用于测试 financial_report_fetcher.py"""
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "机构名单"

ws.append(["证券代码", "公司名称"])
ws.append(["000001", "平安银行"])
ws.append(["600519", "贵州茅台"])
ws.append(["300750", "宁德时代"])
ws.append(["688981", "中芯国际"])
ws.append(["601398", "工商银行"])

out = "/workspace/sample_institutions.xlsx"
wb.save(out)
print(f"已生成: {out}")
