#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import platform
import sys
from pynput import keyboard
import time

def check_accessibility_permission():
    """检查辅助功能权限"""
    print("正在检查系统权限...")
    
    if platform.system() == "Darwin":
        print("检测到macOS系统")
        try:
            # 创建测试监听器
            print("测试键盘监听权限...")
            test_listener = keyboard.Listener(on_press=lambda key: None)
            test_listener.start()
            time.sleep(0.5)
            test_listener.stop()
            
            print("✅ 权限检查通过！可以使用快捷键功能。")
            return True
            
        except Exception as e:
            print("❌ 权限检查失败！")
            print(f"错误: {e}")
            print("\n解决方法:")
            print("1. 打开'系统偏好设置'")
            print("2. 进入'安全性与隐私'")
            print("3. 点击左侧的'辅助功能'")
            print("4. 点击左下角的锁图标解锁")
            print("5. 添加Terminal或Python到允许列表")
            print("6. 重新运行此程序")
            return False
    else:
        print("非macOS系统，权限检查跳过")
        return True

if __name__ == "__main__":
    check_accessibility_permission()