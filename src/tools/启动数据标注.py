#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 添加tools目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'tools'))

from data_labeler import DataLabeler

if __name__ == "__main__":
    print("启动跳一跳数据标注工具...")
    app = DataLabeler()
    app.run()