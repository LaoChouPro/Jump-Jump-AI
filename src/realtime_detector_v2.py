#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from PIL import Image, ImageTk
from ultralytics import YOLO
from pathlib import Path
import queue
import sys

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    print("⚠️ mss库未安装，尝试安装...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mss"])
        import mss
        MSS_AVAILABLE = True
        print("✅ mss库安装成功")
    except Exception as e:
        print(f"❌ 无法安装mss库: {e}")
        print("请手动安装: pip install mss")
        sys.exit(1)

try:
    import pynput.mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("⚠️ pynput库未安装，尝试安装...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pynput"])
        import pynput.mouse
        PYNPUT_AVAILABLE = True
        print("✅ pynput库安装成功")
    except Exception as e:
        print(f"❌ 无法安装pynput库: {e}")
        print("请手动安装: pip install pynput")

class RealtimeDetectorV2:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("跳一跳实时检测器 V2.0")
        self.root.geometry("900x700")
        
        # 初始化mss截图工具
        self.sct = mss.mss()
        
        # 加载训练好的模型
        self.load_model()
        
        # 界面变量
        self.capture_area = None
        self.is_detecting = False
        self.detection_thread = None
        self.fps_counter = 0
        self.fps_time = time.time()
        
        # 图像队列用于线程通信
        self.image_queue = queue.Queue(maxsize=5)
        
        # 鼠标选择相关
        self.mouse_listener = None
        self.selecting_area = False
        self.click_positions = []
        
        # 类别名称和颜色
        self.class_names = {0: "小人", 1: "方块"}
        self.class_colors = {0: (255, 0, 0), 1: (0, 0, 255)}  # BGR格式
        
        self.setup_ui()
        
    def load_model(self):
        """加载训练好的YOLO模型"""
        runs_dir = Path("runs")
        best_model = None
        
        for run_dir in runs_dir.glob("jump_jump_nano_*"):
            if run_dir.is_dir():
                model_path = run_dir / "weights" / "best.pt"
                if model_path.exists():
                    best_model = model_path
                    break
        
        if best_model:
            try:
                self.model = YOLO(str(best_model))
                print(f"✅ 成功加载模型: {best_model}")
            except Exception as e:
                print(f"❌ 加载模型失败: {e}")
                messagebox.showerror("错误", f"无法加载YOLO模型: {e}")
                sys.exit(1)
        else:
            messagebox.showerror("错误", "未找到训练好的模型文件！\n请先训练模型。")
            sys.exit(1)
    
    def setup_ui(self):
        """设置用户界面"""
        # 主控制面板
        control_frame = ttk.LabelFrame(self.root, text="控制面板", padding="15")
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 区域选择区域
        area_frame = ttk.LabelFrame(control_frame, text="区域选择", padding="10")
        area_frame.pack(fill=tk.X, pady=5)
        
        # 坐标输入
        coords_frame = ttk.Frame(area_frame)
        coords_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(coords_frame, text="左上角 X:").grid(row=0, column=0, padx=5, sticky="w")
        self.x1_var = tk.StringVar(value="600")
        ttk.Entry(coords_frame, textvariable=self.x1_var, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(coords_frame, text="Y:").grid(row=0, column=2, padx=5, sticky="w")
        self.y1_var = tk.StringVar(value="150")
        ttk.Entry(coords_frame, textvariable=self.y1_var, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(coords_frame, text="右下角 X:").grid(row=0, column=4, padx=5, sticky="w")
        self.x2_var = tk.StringVar(value="1000")
        ttk.Entry(coords_frame, textvariable=self.x2_var, width=10).grid(row=0, column=5, padx=5)
        
        ttk.Label(coords_frame, text="Y:").grid(row=0, column=6, padx=5, sticky="w")
        self.y2_var = tk.StringVar(value="750")
        ttk.Entry(coords_frame, textvariable=self.y2_var, width=10).grid(row=0, column=7, padx=5)
        
        # 按钮区域
        button_frame = ttk.Frame(area_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # 鼠标选择区域按钮
        self.mouse_select_btn = ttk.Button(button_frame, text="🖱️ 鼠标选择区域", command=self.start_mouse_selection)
        self.mouse_select_btn.pack(side=tk.LEFT, padx=5)
        
        # 设置区域按钮
        ttk.Button(button_frame, text="🎯 手动设置区域", command=self.set_capture_area).pack(side=tk.LEFT, padx=5)
        
        # 测试截图按钮
        ttk.Button(button_frame, text="📷 测试截图", command=self.test_screenshot).pack(side=tk.LEFT, padx=5)
        
        # 控制按钮区域
        control_buttons_frame = ttk.LabelFrame(control_frame, text="检测控制", padding="10")
        control_buttons_frame.pack(fill=tk.X, pady=5)
        
        button_control_frame = ttk.Frame(control_buttons_frame)
        button_control_frame.pack(fill=tk.X)
        
        # 开始检测按钮
        self.start_btn = ttk.Button(button_control_frame, text="▶️ 开始检测", command=self.start_detection, state="disabled")
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        # 停止检测按钮
        self.stop_btn = ttk.Button(button_control_frame, text="⏹ 停止检测", command=self.stop_detection, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar(value="请设置检测区域")
        ttk.Label(control_buttons_frame, textvariable=self.status_var, foreground="blue").pack(pady=5)
        
        # 预览画布
        canvas_frame = ttk.LabelFrame(self.root, text="实时检测预览", padding="10")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, bg="black", width=700, height=450)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 统计信息
        stats_frame = ttk.LabelFrame(self.root, text="检测统计", padding="10")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.fps_var = tk.StringVar(value="FPS: 0.0")
        self.detection_var = tk.StringVar(value="检测对象: 0")
        self.area_var = tk.StringVar(value="检测区域: 未设置")
        
        ttk.Label(stats_frame, textvariable=self.fps_var).pack(side=tk.LEFT, padx=15)
        ttk.Label(stats_frame, textvariable=self.detection_var).pack(side=tk.LEFT, padx=15)
        ttk.Label(stats_frame, textvariable=self.area_var).pack(side=tk.LEFT, padx=15)
    
    def start_mouse_selection(self):
        """开始鼠标选择区域"""
        if not PYNPUT_AVAILABLE:
            messagebox.showerror("错误", "pynput库不可用，无法使用鼠标选择功能")
            return
            
        self.selecting_area = True
        self.click_positions = []
        self.mouse_select_btn.config(state="disabled")
        self.status_var.set("请在屏幕上点击两个点来选择区域（左上角和右下角）")
        
        # 隐藏主窗口
        self.root.withdraw()
        
        # 启动鼠标监听
        def on_click(x, y, button, pressed):
            if pressed and button == pynput.mouse.Button.left:
                self.click_positions.append((x, y))
                print(f"点击 {len(self.click_positions)}: ({x}, {y})")
                
                if len(self.click_positions) == 2:
                    # 两次点击完成，停止监听
                    return False
        
        try:
            self.mouse_listener = pynput.mouse.Listener(on_click=on_click)
            self.mouse_listener.start()
            
            # 在新线程中等待监听完成
            threading.Thread(target=self.wait_for_mouse_selection, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"无法启动鼠标监听: {e}")
            self.reset_mouse_selection()
    
    def wait_for_mouse_selection(self):
        """等待鼠标选择完成"""
        try:
            self.mouse_listener.join()  # 等待监听结束
            
            if len(self.click_positions) == 2:
                # 计算区域
                x1, y1 = self.click_positions[0]
                x2, y2 = self.click_positions[1]
                
                # 更新UI中的坐标值
                self.root.after(0, self.update_coordinates_from_mouse, x1, y1, x2, y2)
            
        except Exception as e:
            print(f"鼠标选择错误: {e}")
            self.root.after(0, self.reset_mouse_selection)
    
    def update_coordinates_from_mouse(self, x1, y1, x2, y2):
        """更新坐标值并设置区域"""
        # 更新输入框的值
        self.x1_var.set(str(int(x1)))
        self.y1_var.set(str(int(y1)))
        self.x2_var.set(str(int(x2)))
        self.y2_var.set(str(int(y2)))
        
        # 显示主窗口
        self.root.deiconify()
        
        # 自动设置区域
        self.set_capture_area()
        
        # 重置状态
        self.reset_mouse_selection()
    
    def reset_mouse_selection(self):
        """重置鼠标选择状态"""
        self.selecting_area = False
        self.mouse_select_btn.config(state="normal")
        self.root.deiconify()  # 确保主窗口显示
    
    def set_capture_area(self):
        """设置捕获区域"""
        try:
            x1 = int(self.x1_var.get())
            y1 = int(self.y1_var.get())
            x2 = int(self.x2_var.get())
            y2 = int(self.y2_var.get())
            
            # 确保坐标顺序正确
            left = min(x1, x2)
            top = min(y1, y2)
            right = max(x1, x2)
            bottom = max(y1, y2)
            
            # mss需要的格式: {"top": y, "left": x, "width": w, "height": h}
            self.capture_area = {
                "top": top,
                "left": left,
                "width": right - left,
                "height": bottom - top
            }
            
            self.status_var.set(f"区域已设置: {left},{top} → {right},{bottom}")
            self.area_var.set(f"检测区域: {self.capture_area['width']}x{self.capture_area['height']}")
            self.start_btn.config(state="normal")
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字坐标！")
    
    def test_screenshot(self):
        """测试截图功能"""
        if not self.capture_area:
            messagebox.showwarning("警告", "请先设置检测区域！")
            return
        
        try:
            # 使用mss进行截图
            screenshot = self.sct.grab(self.capture_area)
            
            # 转换为numpy数组
            img = np.array(screenshot)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # 显示在画布上
            self.display_image(img_bgr)
            self.status_var.set("测试截图成功！")
            
        except Exception as e:
            messagebox.showerror("错误", f"截图失败: {e}")
    
    def capture_screen_mss(self):
        """使用mss进行高效屏幕捕获"""
        if not self.capture_area:
            return None
            
        try:
            # 使用mss进行截图 - 这个方法不会触发权限请求
            screenshot = self.sct.grab(self.capture_area)
            
            # 转换为OpenCV格式
            img = np.array(screenshot)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            return img_bgr
        except Exception as e:
            print(f"mss截图错误: {e}")
            return None
    
    def start_detection(self):
        """开始检测"""
        if not self.capture_area:
            messagebox.showwarning("警告", "请先设置检测区域！")
            return
        
        self.is_detecting = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("检测中...")
        
        # 启动检测线程
        self.detection_thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.detection_thread.start()
        
        # 启动显示更新
        self.update_display()
    
    def stop_detection(self):
        """停止检测"""
        self.is_detecting = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("检测已停止")
    
    def detection_loop(self):
        """检测循环"""
        while self.is_detecting:
            try:
                # 捕获屏幕
                frame = self.capture_screen_mss()
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # YOLO检测
                results = self.model(frame, verbose=False)
                
                # 绘制检测结果
                annotated_frame = self.draw_detections(frame, results[0])
                
                # 将结果放入队列
                if not self.image_queue.full():
                    try:
                        self.image_queue.put_nowait(annotated_frame)
                    except queue.Full:
                        pass
                
                # 控制帧率
                time.sleep(0.033)  # 约30FPS
                
            except Exception as e:
                print(f"检测错误: {e}")
                time.sleep(0.1)
    
    def draw_detections(self, frame, result):
        """在图像上绘制检测结果"""
        annotated_frame = frame.copy()
        detection_count = 0
        
        if result.boxes is not None:
            for box in result.boxes:
                # 获取边界框坐标
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                
                # 获取类别和置信度
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                if conf > 0.5:  # 置信度阈值
                    detection_count += 1
                    
                    # 绘制边界框
                    color = self.class_colors.get(cls, (0, 255, 0))
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
                    
                    # 绘制标签
                    label = f"{self.class_names.get(cls, 'Unknown')}: {conf:.2f}"
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                    cv2.rectangle(annotated_frame, (x1, y1 - label_size[1] - 15), 
                                (x1 + label_size[0] + 10, y1), color, -1)
                    cv2.putText(annotated_frame, label, (x1 + 5, y1 - 8), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 更新检测统计
        self.root.after(0, lambda: self.detection_var.set(f"检测对象: {detection_count}"))
        
        return annotated_frame
    
    def display_image(self, frame):
        """在画布上显示图像"""
        try:
            # 调整图像大小以适应画布
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                h, w = frame.shape[:2]
                scale = min(canvas_width / w, canvas_height / h)
                new_w, new_h = int(w * scale), int(h * scale)
                
                frame_resized = cv2.resize(frame, (new_w, new_h))
                
                # 转换为PIL图像
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(pil_image)
                
                # 更新画布
                self.canvas.delete("all")
                self.canvas.create_image(canvas_width//2, canvas_height//2, 
                                       image=photo, anchor=tk.CENTER)
                self.canvas.image = photo  # 保持引用
                
        except Exception as e:
            print(f"显示图像错误: {e}")
    
    def update_display(self):
        """更新显示"""
        if not self.is_detecting:
            return
        
        try:
            # 从队列获取最新图像
            if not self.image_queue.empty():
                frame = self.image_queue.get_nowait()
                
                # 计算FPS
                self.fps_counter += 1
                current_time = time.time()
                if current_time - self.fps_time >= 1.0:
                    fps = self.fps_counter / (current_time - self.fps_time)
                    self.fps_var.set(f"FPS: {fps:.1f}")
                    self.fps_counter = 0
                    self.fps_time = current_time
                
                # 显示图像
                self.display_image(frame)
        
        except queue.Empty:
            pass
        except Exception as e:
            print(f"显示更新错误: {e}")
        
        # 继续更新
        if self.is_detecting:
            self.root.after(30, self.update_display)  # 约33FPS
    
    def run(self):
        """运行程序"""
        self.root.mainloop()

if __name__ == "__main__":
    print("🚀 启动跳一跳实时检测器 V2.0...")
    print("📋 使用mss库进行高性能屏幕捕获")
    detector = RealtimeDetectorV2()
    detector.run()