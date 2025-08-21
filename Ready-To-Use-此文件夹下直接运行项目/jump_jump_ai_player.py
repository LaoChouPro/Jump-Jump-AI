#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import math
from PIL import Image, ImageTk
from ultralytics import YOLO
from pathlib import Path
import queue
import sys
import os
from datetime import datetime

# 自动安装依赖
try:
    import mss
    import pyautogui
    import pynput.mouse
except ImportError as e:
    print(f"⚠️ 缺少依赖库: {e}")
    import subprocess
    libraries = ["mss", "pyautogui", "pynput"]
    for lib in libraries:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
            print(f"✅ {lib}库安装成功")
        except:
            print(f"❌ 无法安装{lib}库")
    
    # 重新导入
    import mss
    import pyautogui
    import pynput.mouse

class JumpJumpAIPlayer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("跳一跳终结者")
        self.root.geometry("1300x800")  # 增加默认宽度以适应固定右侧栏
        self.root.minsize(900, 600)     # 设置最小窗口大小
        
        # 设置pyautogui为最高精度模式
        pyautogui.PAUSE = 0  # 移除所有默认延迟
        pyautogui.FAILSAFE = True  # 保持安全退出功能
        
        # 初始化mss截图工具
        self.sct = mss.mss()
        
        # 加载训练好的模型
        self.load_model()
        
        # 游戏控制变量
        self.capture_area = None
        self.is_playing = False
        self.detection_thread = None
        self.game_thread = None
        
        # AI参数
        self.jump_factor = tk.DoubleVar(value=0.00404)  # 跳跃因子（距离乘数）- 验证最优值
        self.jump_delay = tk.DoubleVar(value=1.5)     # 跳跃间隔秒数
        self.stable_wait = tk.DoubleVar(value=2.0)    # 画面稳定等待时间
        self.confidence_threshold = tk.DoubleVar(value=0.6)  # 置信度阈值
        
        # 游戏状态
        self.last_jump_time = 0
        self.jump_count = 0
        self.success_rate = 0
        self.current_distance = 0
        self.current_press_duration = 0  # 当前计算的点按时长
        self.is_jumping = False  # 跳跃执行状态锁
        
        # 跳跃参数锁定
        self.locked_distance = 0       # 锁定的距离
        self.locked_factor = 0         # 锁定的因子
        self.locked_duration = 0       # 锁定的点按时长
        self.jump_cycle_locked = False # 跳跃周期锁定状态
        self.display_frozen = False    # 显示冻结标记
        
        # 自动数据生成
        self.auto_save_enabled = tk.BooleanVar(value=True)  # 自动保存开关
        self.data_save_count = 0        # 保存数据计数器
        self.setup_data_directories()   # 创建数据保存目录
        
        # 图像队列和检测结果
        self.image_queue = queue.Queue(maxsize=3)
        self.detection_queue = queue.Queue(maxsize=3)
        
        # 鼠标选择相关
        self.mouse_listener = None
        self.selecting_area = False
        self.click_positions = []
        
        # 类别名称和颜色
        self.class_names = {0: "小人", 1: "方块"}
        self.class_colors = {0: (255, 0, 0), 1: (0, 255, 0)}  # BGR格式
        
        self.setup_ui()
        
    def load_model(self):
        """加载训练好的YOLO模型"""
        # 获取当前文件所在目录 (独立运行版本)
        current_dir = Path(__file__).parent
        
        model_paths = [
            current_dir / "epoch92.pt",                       # 当前目录的Small模型 (优先)
            current_dir / "yolov8n_best.pt",                  # 当前目录的Nano模型
            current_dir / "best.pt",                          # 通用模型文件名
            current_dir / "models/epoch92.pt",                # models子目录
        ]
        
        # 添加可能的子目录路径
        runs_dir = current_dir / "runs"
        if runs_dir.exists():
            for run_dir in runs_dir.glob("*"):
                if run_dir.is_dir():
                    weights_dir = run_dir / "weights"
                    if weights_dir.exists():
                        for model_file in ["best.pt", "last.pt"]:
                            model_path = weights_dir / model_file
                            if model_path not in model_paths:
                                model_paths.append(model_path)
        
        best_model = None
        for model_path in model_paths:
            if model_path.exists():
                best_model = model_path
                break
        
        if best_model:
            try:
                self.model = YOLO(str(best_model))
                # 获取模型信息
                model_info = f"{best_model}"
                if "epoch92" in str(best_model):
                    model_info += " [YOLOv8 Small - 92轮训练]"
                elif "runs" in str(best_model):
                    model_info += " [YOLOv8 训练模型]"
                    
                print(f"✅ 成功加载模型: {model_info}")
                self.current_model_path = str(best_model)
                # 设置模型显示名称
                if "epoch92" in str(best_model):
                    self.model_display_name = "YOLOv8 Small (epoch92)"
                else:
                    self.model_display_name = "YOLOv8"
            except Exception as e:
                print(f"❌ 加载模型失败: {e}")
                messagebox.showerror("错误", f"无法加载YOLO模型: {e}")
                sys.exit(1)
        else:
            messagebox.showerror("错误", "未找到训练好的模型文件！\n请确保以下位置之一存在模型文件:\n• models/epoch92.pt\n• runs/train/weights/best.pt")
            sys.exit(1)
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架 - 使用固定右侧宽度的布局
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 右侧 - 控制面板（固定宽度）
        right_container = ttk.Frame(main_frame, width=380)  # 增加到380px
        right_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_container.pack_propagate(False)  # 防止子控件改变父容器大小
        
        # 添加滚动框架
        canvas = tk.Canvas(right_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_container, orient="vertical", command=canvas.yview)
        right_frame = ttk.Frame(canvas)
        
        # 配置滚动
        right_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=right_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 打包滚动组件
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # 左侧 - 游戏画面显示（响应宽度变化）
        left_frame = ttk.LabelFrame(main_frame, text="🎮 游戏画面", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 游戏画布 - 竖屏比例 (9:16)
        self.game_canvas = tk.Canvas(left_frame, bg="black", width=450, height=800)
        self.game_canvas.pack(fill=tk.BOTH, expand=True)
        
        # === 区域选择面板 ===
        area_frame = ttk.LabelFrame(right_frame, text="🎯 区域设置", padding="10")
        area_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 鼠标选择按钮
        self.mouse_select_btn = ttk.Button(area_frame, text="🖱️ 选择游戏区域", 
                                         command=self.start_mouse_selection)
        self.mouse_select_btn.pack(fill=tk.X, pady=2)
        
        # 区域状态
        self.area_status = tk.StringVar(value="未选择游戏区域")
        ttk.Label(area_frame, textvariable=self.area_status, foreground="blue").pack(pady=5)
        
        # === AI控制面板 ===
        control_frame = ttk.LabelFrame(right_frame, text="🤖 AI控制", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 开始/停止按钮
        self.start_stop_btn = ttk.Button(control_frame, text="▶️ 开始AI游戏", 
                                       command=self.toggle_ai_play, state="disabled")
        self.start_stop_btn.pack(fill=tk.X, pady=5)
        
        # 游戏状态
        self.game_status = tk.StringVar(value="等待开始...")
        status_label = ttk.Label(control_frame, textvariable=self.game_status, 
                               foreground="green", font=("Arial", 10, "bold"))
        status_label.pack(pady=5)
        
        # === 参数调节面板 ===
        param_frame = ttk.LabelFrame(right_frame, text="⚙️ AI参数调节", padding="10")
        param_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 跳跃因子输入
        ttk.Label(param_frame, text="跳跃因子:").pack(anchor=tk.W)
        ttk.Label(param_frame, text="(点按时长 = 距离 × 因子)", font=("Arial", 8), foreground="gray").pack(anchor=tk.W)
        jump_factor_frame = ttk.Frame(param_frame)
        jump_factor_frame.pack(fill=tk.X, pady=2)
        
        self.jump_factor_entry = ttk.Entry(jump_factor_frame, textvariable=self.jump_factor, width=12)
        self.jump_factor_entry.pack(side=tk.LEFT, padx=(0,5))
        
        # 手动更新按钮
        update_btn = ttk.Button(jump_factor_frame, text="更新", command=self.manual_update_display, width=6)
        update_btn.pack(side=tk.LEFT, padx=(0,5))
        
        # 推荐值标签换行显示
        ttk.Label(param_frame, text="推荐: 0.002-0.005", font=("Arial", 8)).pack(anchor=tk.W, pady=(2,0))
        
        # 当前计算的点按时长显示
        self.press_duration_var = tk.StringVar(value="当前点按时长: 0.000s")
        press_duration_label = ttk.Label(param_frame, textvariable=self.press_duration_var, 
                                       foreground="red", font=("Arial", 10, "bold"))
        press_duration_label.pack(pady=(5,10))
        
        # 手动更新点按时长显示（移除自动trace避免冲突）
        # self.jump_factor.trace('w', self.update_press_duration_display)
        
        # 跳跃间隔时间
        ttk.Label(param_frame, text="跳跃间隔(秒):").pack(anchor=tk.W, pady=(10,0))
        jump_delay_frame = ttk.Frame(param_frame)
        jump_delay_frame.pack(fill=tk.X, pady=2)
        
        self.jump_delay_scale = ttk.Scale(jump_delay_frame, from_=0.8, to=3.0, 
                                        variable=self.jump_delay, orient=tk.HORIZONTAL)
        self.jump_delay_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.jump_delay_label = ttk.Label(jump_delay_frame, text="1.5")
        self.jump_delay_label.pack(side=tk.RIGHT, padx=(5,0))
        self.jump_delay.trace('w', lambda *args: self.jump_delay_label.config(text=f"{self.jump_delay.get():.1f}"))
        
        # 画面稳定等待时间
        ttk.Label(param_frame, text="画面稳定等待(秒):").pack(anchor=tk.W, pady=(10,0))
        stable_wait_frame = ttk.Frame(param_frame)
        stable_wait_frame.pack(fill=tk.X, pady=2)
        
        self.stable_wait_scale = ttk.Scale(stable_wait_frame, from_=1.0, to=5.0, 
                                         variable=self.stable_wait, orient=tk.HORIZONTAL)
        self.stable_wait_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.stable_wait_label = ttk.Label(stable_wait_frame, text="2.0")
        self.stable_wait_label.pack(side=tk.RIGHT, padx=(5,0))
        self.stable_wait.trace('w', lambda *args: self.stable_wait_label.config(text=f"{self.stable_wait.get():.1f}"))
        
        # 置信度阈值
        ttk.Label(param_frame, text="检测置信度阈值:").pack(anchor=tk.W, pady=(10,0))
        conf_frame = ttk.Frame(param_frame)
        conf_frame.pack(fill=tk.X, pady=2)
        
        self.conf_scale = ttk.Scale(conf_frame, from_=0.3, to=0.9, 
                                  variable=self.confidence_threshold, orient=tk.HORIZONTAL)
        self.conf_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.conf_label = ttk.Label(conf_frame, text="0.6")
        self.conf_label.pack(side=tk.RIGHT, padx=(5,0))
        self.confidence_threshold.trace('w', lambda *args: self.conf_label.config(text=f"{self.confidence_threshold.get():.1f}"))
        
        # === 自动数据生成面板 ===
        data_frame = ttk.LabelFrame(right_frame, text="💾 自动数据生成", padding="10")
        data_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 自动保存开关
        self.auto_save_checkbox = ttk.Checkbutton(data_frame, text="启用自动数据生成", 
                                                variable=self.auto_save_enabled)
        self.auto_save_checkbox.pack(anchor=tk.W)
        
        # 数据保存统计
        self.save_count_var = tk.StringVar(value="已保存: 0 张图片")
        ttk.Label(data_frame, textvariable=self.save_count_var).pack(anchor=tk.W, pady=(5,0))
        
        # === 游戏统计面板 ===
        stats_frame = ttk.LabelFrame(right_frame, text="📊 游戏统计", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 统计信息
        self.jump_count_var = tk.StringVar(value="跳跃次数: 0")
        self.distance_var = tk.StringVar(value="当前距离: 0px")
        self.calculated_duration_var = tk.StringVar(value="计算时长: 0.000s")
        
        # 模型信息显示
        model_name = getattr(self, 'model_display_name', 'YOLOv8')
        self.model_info_var = tk.StringVar(value=f"模型: {model_name}")
        
        ttk.Label(stats_frame, textvariable=self.model_info_var, 
                 foreground="blue", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(stats_frame, textvariable=self.jump_count_var).pack(anchor=tk.W)
        ttk.Label(stats_frame, textvariable=self.distance_var).pack(anchor=tk.W)
        ttk.Label(stats_frame, textvariable=self.calculated_duration_var).pack(anchor=tk.W)
        
        # === 鼠标状态面板 ===
        mouse_frame = ttk.LabelFrame(right_frame, text="🖱️ 鼠标状态", padding="10")
        mouse_frame.pack(fill=tk.X)
        
        self.mouse_status = tk.StringVar(value="待机")
        mouse_status_label = ttk.Label(mouse_frame, textvariable=self.mouse_status, 
                                     foreground="orange", font=("Arial", 10, "bold"))
        mouse_status_label.pack()
        
        # 最后一次点击信息
        self.last_click_info = tk.StringVar(value="无")
        ttk.Label(mouse_frame, text="最后点击:").pack(anchor=tk.W)
        ttk.Label(mouse_frame, textvariable=self.last_click_info, font=("Arial", 9)).pack(anchor=tk.W)
    
    def manual_update_display(self):
        """手动更新显示（只在未锁定状态下有效）"""
        if not self.jump_cycle_locked:
            self.update_press_duration_display()
    
    def update_press_duration_display(self, force_update=False):
        """更新点按时长显示"""
        # 如果显示被冻结且不是强制更新，直接返回
        if self.display_frozen and not force_update:
            return
            
        try:
            if self.jump_cycle_locked:
                # 锁定状态显示
                self.press_duration_var.set(f"🔒 锁定时长: {self.locked_duration:.3f}s [距离:{self.locked_distance:.0f}px]")
                self.calculated_duration_var.set(f"锁定时长: {self.locked_duration:.3f}s")
                # 设置显示冻结
                self.display_frozen = True
            else:
                # 正常状态计算显示
                try:
                    factor = self.jump_factor.get()
                    distance = self.current_distance
                    duration = distance * factor
                    duration = max(0.05, min(3.0, duration))
                    
                    self.current_press_duration = duration
                    self.press_duration_var.set(f"预计时长: {duration:.3f}s")
                    self.calculated_duration_var.set(f"预计时长: {duration:.3f}s")
                    # 取消显示冻结
                    self.display_frozen = False
                except:
                    self.press_duration_var.set("预计时长: 0.000s")
                    self.calculated_duration_var.set("预计时长: 0.000s")
                    self.display_frozen = False
        except Exception as e:
            print(f"显示更新错误: {e}")
    
    def start_mouse_selection(self):
        """开始鼠标选择区域"""
        self.selecting_area = True
        self.click_positions = []
        self.mouse_select_btn.config(state="disabled", text="请在屏幕上点击两点...")
        self.area_status.set("请点击游戏区域的左上角和右下角")
        
        # 隐藏主窗口
        self.root.withdraw()
        
        def on_click(x, y, button, pressed):
            if pressed and button == pynput.mouse.Button.left:
                self.click_positions.append((x, y))
                print(f"点击 {len(self.click_positions)}: ({x}, {y})")
                
                if len(self.click_positions) == 2:
                    return False
        
        try:
            self.mouse_listener = pynput.mouse.Listener(on_click=on_click)
            self.mouse_listener.start()
            threading.Thread(target=self.wait_for_mouse_selection, daemon=True).start()
        except Exception as e:
            messagebox.showerror("错误", f"无法启动鼠标监听: {e}")
            self.reset_mouse_selection()
    
    def wait_for_mouse_selection(self):
        """等待鼠标选择完成"""
        try:
            self.mouse_listener.join()
            
            if len(self.click_positions) == 2:
                x1, y1 = self.click_positions[0]
                x2, y2 = self.click_positions[1]
                
                self.root.after(0, self.setup_capture_area, x1, y1, x2, y2)
        except Exception as e:
            print(f"鼠标选择错误: {e}")
            self.root.after(0, self.reset_mouse_selection)
    
    def lock_jump_parameters(self, distance, factor):
        """锁定跳跃参数，开始跳跃周期"""
        self.locked_distance = distance
        self.locked_factor = factor
        self.locked_duration = distance * factor
        self.locked_duration = max(0.05, min(3.0, self.locked_duration))  # 限制范围
        
        self.jump_cycle_locked = True
        
        # 立即更新显示为锁定状态（强制更新）
        self.root.after(0, lambda: self.update_press_duration_display(force_update=True))
        
        print(f"🔒 跳跃参数已锁定 - 距离:{distance:.0f}px × 因子:{factor:.3f} = 时长:{self.locked_duration:.3f}s")
        print(f"📅 时序安排: 画面稳定等待:{self.stable_wait.get():.1f}s + 跳跃间隔:{self.jump_delay.get():.1f}s = 总计:{self.stable_wait.get() + self.jump_delay.get():.1f}s")
    
    def execute_locked_jump(self):
        """执行使用锁定参数的跳跃"""
        self.perform_jump(self.locked_duration, self.locked_distance, self.locked_factor)
    
    def unlock_jump_parameters(self):
        """解锁跳跃参数，结束跳跃周期"""
        self.jump_cycle_locked = False
        self.display_frozen = False  # 解除显示冻结
        self.locked_distance = 0
        self.locked_factor = 0
        self.locked_duration = 0
        
        # 恢复实时显示（强制更新）
        self.root.after(0, lambda: self.update_press_duration_display(force_update=True))
        
        print(f"🔓 跳跃周期结束，参数已解锁")
    
    def setup_capture_area(self, x1, y1, x2, y2):
        """设置捕获区域"""
        left = int(min(x1, x2))
        top = int(min(y1, y2))
        right = int(max(x1, x2))
        bottom = int(max(y1, y2))
        
        self.capture_area = {
            "top": top,
            "left": left,
            "width": right - left,
            "height": bottom - top
        }
        
        # 计算点击中心点
        self.click_center_x = left + (right - left) // 2
        self.click_center_y = top + (bottom - top) // 2
        
        self.root.deiconify()
        self.area_status.set(f"区域: {self.capture_area['width']}x{self.capture_area['height']}")
        self.mouse_select_btn.config(state="normal", text="🖱️ 重新选择游戏区域")
        self.start_stop_btn.config(state="normal")
        
        # 开始检测线程
        self.start_detection_thread()
        
        self.reset_mouse_selection()
    
    def reset_mouse_selection(self):
        """重置鼠标选择状态"""
        self.selecting_area = False
        self.root.deiconify()
    
    def start_detection_thread(self):
        """启动检测线程"""
        if self.detection_thread and self.detection_thread.is_alive():
            return
            
        self.detection_thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.detection_thread.start()
        self.update_display()
    
    def capture_screen(self):
        """使用mss进行屏幕捕获"""
        if not self.capture_area:
            return None
            
        try:
            screenshot = self.sct.grab(self.capture_area)
            img = np.array(screenshot)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img_bgr
        except Exception as e:
            print(f"截图错误: {e}")
            return None
    
    def detection_loop(self):
        """检测循环"""
        while True:
            try:
                if not self.capture_area:
                    time.sleep(0.1)
                    continue
                
                frame = self.capture_screen()
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # YOLO检测
                results = self.model(frame, verbose=False)
                
                # 分析检测结果
                detections = self.analyze_detections(frame, results[0])
                annotated_frame = detections['annotated_frame']
                
                # 放入队列
                if not self.image_queue.full():
                    try:
                        self.image_queue.put_nowait(annotated_frame)
                    except queue.Full:
                        pass
                
                if not self.detection_queue.full():
                    try:
                        self.detection_queue.put_nowait(detections)
                    except queue.Full:
                        pass
                
                time.sleep(0.05)  # 20FPS
                
            except Exception as e:
                print(f"检测错误: {e}")
                time.sleep(0.1)
    
    def analyze_detections(self, frame, result):
        """分析检测结果，找出小人和目标方块"""
        annotated_frame = frame.copy()
        
        person_center = None
        target_block_center = None
        blocks = []
        persons = []
        
        # 解析所有检测结果
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                if conf > self.confidence_threshold.get():
                    if cls == 0:  # 小人
                        # 小人坐标：底部向上3px，模拟圆柱体正中心
                        person_center_x = (x1 + x2) // 2
                        person_center_y = y2 - 3  # 底部向上3px
                        persons.append({
                            'center': (person_center_x, person_center_y),
                            'bbox': (x1, y1, x2, y2),
                            'conf': conf
                        })
                    elif cls == 1:  # 方块
                        # 方块坐标：上半部分中间（3/4位置），模拟平台中心
                        block_center_x = (x1 + x2) // 2
                        # 3/4位置 = y1 + (y2-y1) * 1/4 = y1 + height/4
                        block_center_y = y1 + (y2 - y1) // 4
                        blocks.append({
                            'center': (block_center_x, block_center_y),
                            'bbox': (x1, y1, x2, y2),
                            'conf': conf
                        })
        
        # 选择最佳小人（置信度最高）
        if persons:
            person = max(persons, key=lambda x: x['conf'])
            person_center = person['center']
            
            # 绘制小人
            x1, y1, x2, y2 = person['bbox']
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), self.class_colors[0], 3)
            cv2.putText(annotated_frame, f"小人: {person['conf']:.2f}", 
                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            # 绘制小人计算中心点（底部向上3px）
            cv2.circle(annotated_frame, person_center, 6, (255, 0, 0), -1)
            cv2.putText(annotated_frame, "人心", (person_center[0]-10, person_center[1]-8), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # 找到目标方块（直接选择最上面的方块，不考虑小人位置）
        if blocks:
            # 选择最上面的方块（y坐标最小）
            target_block = min(blocks, key=lambda x: x['center'][1])
            target_block_center = target_block['center']
            
            # 绘制目标方块
            x1, y1, x2, y2 = target_block['bbox']
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 255), 4)  # 黄色边框
            cv2.putText(annotated_frame, f"目标: {target_block['conf']:.2f}", 
                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            # 绘制方块计算中心点（3/4位置，平台中心）
            cv2.circle(annotated_frame, target_block_center, 8, (0, 255, 255), -1)
            cv2.putText(annotated_frame, "台心", (target_block_center[0]-10, target_block_center[1]-8), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # 绘制其他方块
        for block in blocks:
            if target_block_center is None or block['center'] != target_block_center:
                x1, y1, x2, y2 = block['bbox']
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), self.class_colors[1], 2)
                cv2.putText(annotated_frame, f"方块: {block['conf']:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 计算距离并绘制连线
        distance = 0
        if person_center and target_block_center:
            distance = math.sqrt((target_block_center[0] - person_center[0])**2 + 
                               (target_block_center[1] - person_center[1])**2)
            
            # 绘制连线
            cv2.line(annotated_frame, person_center, target_block_center, (255, 255, 0), 2)
            
            # 显示距离
            mid_x = (person_center[0] + target_block_center[0]) // 2
            mid_y = (person_center[1] + target_block_center[1]) // 2
            cv2.putText(annotated_frame, f"{distance:.0f}px", 
                       (mid_x, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        
        # 只有在不执行跳跃时才更新距离
        if not self.is_jumping:
            self.current_distance = distance
            # 只有在未锁定状态下才更新显示
            if not self.jump_cycle_locked:
                self.root.after(0, self.update_press_duration_display)
        
        return {
            'annotated_frame': annotated_frame,
            'person_center': person_center,
            'target_block_center': target_block_center,
            'distance': distance,
            'valid_detection': person_center is not None and target_block_center is not None
        }
    
    def toggle_ai_play(self):
        """开始/停止AI游戏"""
        if not self.is_playing:
            self.start_ai_play()
        else:
            self.stop_ai_play()
    
    def start_ai_play(self):
        """开始AI游戏"""
        self.is_playing = True
        self.jump_count = 0
        self.start_stop_btn.config(text="⏹ 停止AI游戏")
        self.game_status.set("AI游戏运行中...")
        
        self.game_thread = threading.Thread(target=self.ai_game_loop, daemon=True)
        self.game_thread.start()
    
    def stop_ai_play(self):
        """停止AI游戏"""
        self.is_playing = False
        self.start_stop_btn.config(text="▶️ 开始AI游戏")
        self.game_status.set("AI游戏已停止")
        self.mouse_status.set("待机")
        
        # 重置跳跃状态
        if self.jump_cycle_locked:
            self.unlock_jump_parameters()
        self.is_jumping = False
    
    def ai_game_loop(self):
        """AI游戏主循环"""
        while self.is_playing:
            try:
                # 检查是否有检测结果
                if not self.detection_queue.empty():
                    detection_data = self.detection_queue.get_nowait()
                    
                    if detection_data['valid_detection']:
                        distance = detection_data['distance']
                        
                        # 更新当前距离显示
                        self.root.after(0, lambda: self.distance_var.set(f"当前距离: {distance:.0f}px"))
                        
                        # 检查跳跃时序控制
                        current_time = time.time()
                        time_since_last_jump = current_time - self.last_jump_time
                        
                        stable_wait_time = self.stable_wait.get()  # 画面稳定等待时间
                        jump_delay_time = self.jump_delay.get()    # 跳跃间隔时间
                        
                        if time_since_last_jump >= stable_wait_time and not self.is_jumping and not self.jump_cycle_locked:
                            # 画面已稳定，开始新的跳跃周期：锁定参数
                            self.lock_jump_parameters(distance, self.jump_factor.get())
                            
                            # 自动保存训练数据（在画面稳定后）
                            if self.auto_save_enabled.get():
                                self.save_current_frame_data()
                            
                            # 更新统计
                            self.jump_count += 1
                            self.root.after(0, lambda: self.jump_count_var.set(f"跳跃次数: {self.jump_count}"))
                            
                            # 更新状态显示剩余等待时间
                            remaining_wait = jump_delay_time
                            self.root.after(0, lambda: self.game_status.set(f"参数已锁定，{remaining_wait:.1f}秒后执行跳跃"))
                            
                        elif self.jump_cycle_locked and time_since_last_jump >= (stable_wait_time + jump_delay_time):
                            # 总等待时间已到，执行跳跃
                            self.execute_locked_jump()
                            self.last_jump_time = current_time
                        
                        elif time_since_last_jump < stable_wait_time:
                            # 还在等待画面稳定
                            remaining_stable = stable_wait_time - time_since_last_jump
                            self.root.after(0, lambda: self.game_status.set(f"等待画面稳定... {remaining_stable:.1f}s"))
                    
                    else:
                        self.root.after(0, lambda: self.game_status.set("等待检测小人和方块..."))
                
                time.sleep(0.1)
                
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                print(f"AI游戏循环错误: {e}")
                time.sleep(0.5)
    
    def perform_jump(self, duration, locked_distance=None, locked_factor=None):
        """执行跳跃操作"""
        try:
            # 设置跳跃执行锁，防止距离更新干扰
            self.is_jumping = True
            
            # 更新状态显示锁定的参数
            info_text = f"({self.click_center_x}, {self.click_center_y}) - {duration:.3f}s"
            if locked_distance and locked_factor:
                info_text += f" [距离:{locked_distance:.0f}px × 因子:{locked_factor:.3f}]"
            
            self.root.after(0, lambda: self.mouse_status.set("执行跳跃"))
            self.root.after(0, lambda: self.last_click_info.set(info_text))
            
            # 记录实际开始时间
            start_time = time.perf_counter()
            
            # 在游戏区域中心执行长按 - 使用最精确的方法
            pyautogui.mouseDown(self.click_center_x, self.click_center_y)
            time.sleep(duration)  # 这是最准确的延迟方法
            pyautogui.mouseUp()
            
            # 计算实际执行时间
            actual_duration = time.perf_counter() - start_time
            
            # 更新状态显示实际时间对比
            self.root.after(0, lambda: self.mouse_status.set("跳跃完成"))
            self.root.after(0, lambda: self.game_status.set(f"计划:{duration:.3f}s 实际:{actual_duration:.3f}s"))
            
            # 输出详细调试信息
            error_ms = abs(actual_duration - duration) * 1000
            debug_info = f"🎯 跳跃执行 - 计划:{duration:.3f}s, 实际:{actual_duration:.3f}s, 误差:{error_ms:.1f}ms"
            if locked_distance and locked_factor:
                debug_info += f" [锁定距离:{locked_distance:.0f}px × 因子:{locked_factor:.3f}]"
            print(debug_info)
            
            # 如果误差超过10ms，给出警告
            if error_ms > 10:
                print(f"⚠️  时间误差较大: {error_ms:.1f}ms")
            else:
                print(f"✅ 时间精度良好")
            
        except Exception as e:
            print(f"❌ 跳跃执行错误: {e}")
            self.root.after(0, lambda: self.mouse_status.set("跳跃失败"))
        finally:
            # 释放跳跃执行锁
            self.is_jumping = False
            # 解锁跳跃参数，结束本次跳跃周期
            self.unlock_jump_parameters()
    
    def update_display(self):
        """更新显示"""
        try:
            # 获取最新的图像
            if not self.image_queue.empty():
                frame = self.image_queue.get_nowait()
                
                # 调整图像大小适应画布
                canvas_width = self.game_canvas.winfo_width()
                canvas_height = self.game_canvas.winfo_height()
                
                if canvas_width > 1 and canvas_height > 1:
                    h, w = frame.shape[:2]
                    
                    # 保持竖屏比例
                    scale = min(canvas_width / w, canvas_height / h)
                    new_w, new_h = int(w * scale), int(h * scale)
                    
                    frame_resized = cv2.resize(frame, (new_w, new_h))
                    
                    # 转换为PIL图像
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(pil_image)
                    
                    # 更新画布
                    self.game_canvas.delete("all")
                    self.game_canvas.create_image(canvas_width//2, canvas_height//2, 
                                               image=photo, anchor=tk.CENTER)
                    self.game_canvas.image = photo
        
        except queue.Empty:
            pass
        except Exception as e:
            print(f"显示更新错误: {e}")
        
        # 继续更新
        self.root.after(50, self.update_display)
    
    def setup_data_directories(self):
        """创建数据保存目录"""
        try:
            # 创建主数据目录
            self.data_root = Path("auto_generated_data")
            self.data_root.mkdir(exist_ok=True)
            
            # 创建图片和标注子目录
            self.images_dir = self.data_root / "images"
            self.labels_dir = self.data_root / "labels"
            
            self.images_dir.mkdir(exist_ok=True)
            self.labels_dir.mkdir(exist_ok=True)
            
            # 修改目录权限，确保用户laochou可以读写
            import os
            import stat
            
            # 设置目录权限为755 (所有者读写执行，组和其他用户读执行)
            os.chmod(str(self.data_root), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            os.chmod(str(self.images_dir), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            os.chmod(str(self.labels_dir), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            
            # 如果需要，使用chown更改所有者为laochou
            try:
                import pwd
                laochou_uid = pwd.getpwnam('laochou').pw_uid
                laochou_gid = pwd.getpwnam('laochou').pw_gid
                
                os.chown(str(self.data_root), laochou_uid, laochou_gid)
                os.chown(str(self.images_dir), laochou_uid, laochou_gid)
                os.chown(str(self.labels_dir), laochou_uid, laochou_gid)
                print(f"✅ 目录所有者已设置为用户laochou")
            except (KeyError, PermissionError) as e:
                print(f"⚠️  无法更改目录所有者: {e}")
                print("   请手动执行: sudo chown -R laochou:laochou auto_generated_data")
            
            # 统计已有数据
            existing_images = list(self.images_dir.glob("*.jpg"))
            self.data_save_count = len(existing_images)
            
            # 更新UI显示
            if hasattr(self, 'save_count_var'):
                self.save_count_var.set(f"已保存: {self.data_save_count} 张图片")
            
            print(f"✅ 数据目录已准备就绪:")
            print(f"   图片目录: {self.images_dir}")
            print(f"   标注目录: {self.labels_dir}")
            print(f"   已有数据: {self.data_save_count} 张图片")
            
        except Exception as e:
            print(f"❌ 创建数据目录失败: {e}")
            self.auto_save_enabled.set(False)
    
    def save_training_data(self, frame, detections):
        """保存训练数据 - 截图和YOLO标注"""
        if not self.auto_save_enabled.get():
            return
            
        try:
            # 确保目录存在
            if not hasattr(self, 'images_dir') or not hasattr(self, 'labels_dir'):
                self.setup_data_directories()
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"auto_{self.data_save_count:05d}_{timestamp}.jpg"
            label_filename = f"auto_{self.data_save_count:05d}_{timestamp}.txt"
            
            image_path = self.images_dir / image_filename
            label_path = self.labels_dir / label_filename
            
            # 保存图片
            success = cv2.imwrite(str(image_path), frame)
            if not success:
                print(f"❌ 图片保存失败: {image_path}")
                return
            
            # 保存YOLO格式标注
            h, w = frame.shape[:2]
            with open(label_path, 'w', encoding='utf-8') as f:
                for detection in detections:
                    x1, y1, x2, y2 = detection['bbox']
                    cls_id = detection['class_id']
                    conf = detection['confidence']
                    
                    # 转换为YOLO格式 (center_x, center_y, width, height)，相对坐标
                    center_x = ((x1 + x2) / 2) / w
                    center_y = ((y1 + y2) / 2) / h
                    bbox_width = (x2 - x1) / w
                    bbox_height = (y2 - y1) / h
                    
                    # 写入标注文件 (class_id center_x center_y width height)
                    f.write(f"{cls_id} {center_x:.6f} {center_y:.6f} {bbox_width:.6f} {bbox_height:.6f}\n")
            
            # 更新计数
            self.data_save_count += 1
            
            # 更新UI显示
            self.root.after(0, lambda: self.save_count_var.set(f"已保存: {self.data_save_count} 张图片"))
            
            print(f"📊 自动保存训练数据: {image_filename} (总计: {self.data_save_count})")
            
        except Exception as e:
            print(f"❌ 保存训练数据失败: {e}")
            import traceback
            traceback.print_exc()
    
    def save_current_frame_data(self):
        """保存当前帧的训练数据"""
        try:
            # 获取当前帧
            frame = self.capture_screen()
            if frame is None:
                return
                
            # 运行YOLO检测
            results = self.model(frame, verbose=False)
            if not results or results[0].boxes is None:
                return
                
            # 提取检测结果
            detections = []
            confidence_threshold = self.confidence_threshold.get()
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                if conf > confidence_threshold:
                    detections.append({
                        'bbox': (x1, y1, x2, y2),
                        'class_id': cls,
                        'confidence': conf
                    })
            
            # 只有在检测到有效对象时才保存
            if detections:
                self.save_training_data(frame, detections)
                
        except Exception as e:
            print(f"❌ 保存当前帧数据失败: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """运行程序"""
        print("🚀 启动跳一跳AI自动游戏程序...")
        print("🎯 功能: 智能检测小人和方块位置，自动计算跳跃距离")
        print("🤖 AI会自动识别最上方的目标方块并执行精确跳跃")
        self.root.mainloop()

if __name__ == "__main__":
    app = JumpJumpAIPlayer()
    app.run()