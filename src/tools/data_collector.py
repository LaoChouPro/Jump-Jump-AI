#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
from PIL import Image, ImageTk
import os
import time
import threading
from datetime import datetime
from pynput import mouse, keyboard


class DataCollector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("跳一跳数据采集工具")
        self.root.geometry("400x600")
        
        # 截图区域坐标
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        
        # 鼠标监听相关
        self.mouse_listener = None
        self.selecting_area = False
        self.click_count = 0
        
        # 实时预览相关
        self.preview_active = False
        self.preview_job = None
        self.preview_fps = 10  # 预览帧率
        
        # 键盘快捷键相关
        self.keyboard_listener = None
        self.hotkey_enabled = False
        self.pressed_keys = set()
        
        # 数据保存路径（使用绝对路径）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.save_path = os.path.join(project_root, "data", "images")
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        
        # 截图计数器
        self.image_count = len([f for f in os.listdir(self.save_path) if f.endswith('.jpg')])
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题
        title_label = ttk.Label(main_frame, text="跳一跳数据采集工具", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # 区域选择说明
        instruction_label = ttk.Label(main_frame, text="1. 点击'选择区域'按钮\n2. 在屏幕上点击两个点定义截图区域\n3. 启用快捷键或点击截图按钮采集数据", 
                                    justify=tk.LEFT)
        instruction_label.grid(row=1, column=0, columnspan=2, pady=(0, 20), sticky=tk.W)
        
        # 选择区域按钮
        self.select_button = ttk.Button(main_frame, text="选择区域", command=self.select_area)
        self.select_button.grid(row=2, column=0, columnspan=2, pady=(0, 10), sticky=(tk.W, tk.E))
        
        # 区域信息显示
        self.area_info_label = ttk.Label(main_frame, text="未选择区域")
        self.area_info_label.grid(row=3, column=0, columnspan=2, pady=(0, 20))
        
        # 预览标签
        preview_label = ttk.Label(main_frame, text="区域预览:", font=("Arial", 12, "bold"))
        preview_label.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # 预览画布
        self.preview_canvas = tk.Canvas(main_frame, width=200, height=150, bg="lightgray")
        self.preview_canvas.grid(row=5, column=0, columnspan=2, pady=(0, 20))
        
        # 控制按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(0, 10), sticky=(tk.W, tk.E))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        # 截图按钮
        self.capture_button = ttk.Button(button_frame, text="截图", command=self.capture_screenshot, state="disabled")
        self.capture_button.grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))
        
        # 实时预览开关按钮
        self.preview_button = ttk.Button(button_frame, text="开启预览", command=self.toggle_preview, state="disabled")
        self.preview_button.grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))
        
        # 帧率控制
        fps_frame = ttk.Frame(main_frame)
        fps_frame.grid(row=7, column=0, columnspan=2, pady=(0, 10), sticky=(tk.W, tk.E))
        
        ttk.Label(fps_frame, text="预览帧率:").pack(side=tk.LEFT)
        self.fps_var = tk.IntVar(value=10)
        fps_scale = ttk.Scale(fps_frame, from_=1, to=30, variable=self.fps_var, orient=tk.HORIZONTAL, command=self.update_fps)
        fps_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.fps_label = ttk.Label(fps_frame, text="10 FPS")
        self.fps_label.pack(side=tk.RIGHT)
        
        # 状态显示
        self.status_label = ttk.Label(main_frame, text="准备就绪")
        self.status_label.grid(row=8, column=0, columnspan=2, pady=(0, 10))
        
        # 已采集数量显示
        self.count_label = ttk.Label(main_frame, text=f"已采集图片: {self.image_count}")
        self.count_label.grid(row=9, column=0, columnspan=2, pady=(0, 10))
        
        # 快捷键控制
        hotkey_frame = ttk.Frame(main_frame)
        hotkey_frame.grid(row=10, column=0, columnspan=2, pady=(0, 10), sticky=(tk.W, tk.E))
        hotkey_frame.grid_columnconfigure(1, weight=1)
        
        self.hotkey_var = tk.BooleanVar()
        hotkey_check = ttk.Checkbutton(hotkey_frame, text="启用快捷键", variable=self.hotkey_var, command=self.toggle_hotkey)
        hotkey_check.grid(row=0, column=0, sticky=tk.W)
        
        hotkey_info = ttk.Label(hotkey_frame, text="Cmd+Opt+E 截图", font=("Arial", 10), foreground="gray")
        hotkey_info.grid(row=0, column=1, sticky=tk.E)
        
        # 退出按钮
        exit_button = ttk.Button(main_frame, text="退出", command=self.on_closing)
        exit_button.grid(row=11, column=0, columnspan=2, pady=(20, 0), sticky=(tk.W, tk.E))
        
    def select_area(self):
        """选择截图区域"""
        if self.selecting_area:
            self.stop_area_selection()
            return
            
        self.selecting_area = True
        self.click_count = 0
        self.select_button.config(text="停止选择", state="normal")
        self.status_label.config(text="请在屏幕上点击第一个点（左上角）")
        
        # 启动全局鼠标监听
        self.start_mouse_listener()
        
    def start_mouse_listener(self):
        """启动全局鼠标监听"""
        def on_click(x, y, button, pressed):
            if pressed and button == mouse.Button.left and self.selecting_area:
                self.handle_mouse_click(x, y)
        
        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.start()
        
    def handle_mouse_click(self, x, y):
        """处理鼠标点击事件"""
        self.click_count += 1
        
        if self.click_count == 1:
            self.start_x = int(x)
            self.start_y = int(y)
            self.root.after(0, lambda: self.status_label.config(text="请点击第二个点（右下角）"))
            
        elif self.click_count == 2:
            self.end_x = int(x)
            self.end_y = int(y)
            
            # 确保坐标顺序正确
            if self.start_x > self.end_x:
                self.start_x, self.end_x = self.end_x, self.start_x
            if self.start_y > self.end_y:
                self.start_y, self.end_y = self.end_y, self.start_y
                
            # 在主线程中更新UI
            self.root.after(0, self.finish_area_selection)
            
    def finish_area_selection(self):
        """完成区域选择"""
        self.stop_area_selection()
        self.update_area_info()
        self.update_preview()
        
        # 自动开启实时预览
        self.start_preview()
        
    def stop_area_selection(self):
        """停止区域选择"""
        self.selecting_area = False
        self.select_button.config(text="选择区域")
        
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
            
        if self.click_count >= 2:
            self.status_label.config(text="区域选择完成")
        else:
            self.status_label.config(text="区域选择已取消")

    def update_area_info(self):
        """更新区域信息显示"""
        if all(coord is not None for coord in [self.start_x, self.start_y, self.end_x, self.end_y]):
            width = self.end_x - self.start_x
            height = self.end_y - self.start_y
            self.area_info_label.config(text=f"区域: ({self.start_x}, {self.start_y}) - ({self.end_x}, {self.end_y})\n大小: {width} x {height}")
            self.capture_button.config(state="normal")
            self.preview_button.config(state="normal")

    def update_preview(self):
        """更新预览图像（单次）"""
        if all(coord is not None for coord in [self.start_x, self.start_y, self.end_x, self.end_y]):
            try:
                self._capture_and_show_preview()
            except Exception as e:
                print(f"预览更新失败: {e}")
                
    def _capture_and_show_preview(self):
        """截取并显示预览图像"""
        # 计算区域参数，确保都是整数
        region_x = int(self.start_x)
        region_y = int(self.start_y)
        region_width = int(self.end_x - self.start_x)
        region_height = int(self.end_y - self.start_y)
        
        # 截取预览图像
        screenshot = pyautogui.screenshot(region=(region_x, region_y, region_width, region_height))
        
        # 转换颜色模式（如果需要）
        if screenshot.mode == 'RGBA':
            rgb_screenshot = Image.new('RGB', screenshot.size, (255, 255, 255))
            rgb_screenshot.paste(screenshot, mask=screenshot.split()[-1])
            screenshot = rgb_screenshot
        elif screenshot.mode != 'RGB':
            screenshot = screenshot.convert('RGB')
        
        # 调整大小适应预览窗口
        screenshot.thumbnail((200, 150), Image.Resampling.LANCZOS)
        
        # 转换为tkinter可用格式
        photo = ImageTk.PhotoImage(screenshot)
        
        # 更新画布
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(100, 75, image=photo)
        self.preview_canvas.image = photo  # 保持引用
        
    def toggle_preview(self):
        """切换实时预览状态"""
        if self.preview_active:
            self.stop_preview()
        else:
            self.start_preview()
            
    def start_preview(self):
        """开启实时预览"""
        if not all(coord is not None for coord in [self.start_x, self.start_y, self.end_x, self.end_y]):
            messagebox.showwarning("警告", "请先选择截图区域")
            return
            
        self.preview_active = True
        self.preview_button.config(text="关闭预览")
        self.update_live_preview()
        
    def stop_preview(self):
        """停止实时预览"""
        self.preview_active = False
        self.preview_button.config(text="开启预览")
        
        if self.preview_job:
            self.root.after_cancel(self.preview_job)
            self.preview_job = None
            
    def update_live_preview(self):
        """实时更新预览画面"""
        if not self.preview_active:
            return
            
        try:
            self._capture_and_show_preview()
        except Exception as e:
            print(f"实时预览更新失败: {e}")
            
        # 安排下次更新（控制帧率）
        if self.preview_active:
            delay = int(1000 / self.preview_fps)  # 转换为毫秒
            self.preview_job = self.root.after(delay, self.update_live_preview)
            
    def update_fps(self, value):
        """更新预览帧率"""
        self.preview_fps = int(float(value))
        self.fps_label.config(text=f"{self.preview_fps} FPS")
        
    def toggle_hotkey(self):
        """切换快捷键启用状态"""
        if self.hotkey_var.get():
            self.start_hotkey_listener()
        else:
            self.stop_hotkey_listener()
            
    def start_hotkey_listener(self):
        """启动快捷键监听"""
        if not all(coord is not None for coord in [self.start_x, self.start_y, self.end_x, self.end_y]):
            messagebox.showwarning("警告", "请先选择截图区域")
            self.hotkey_var.set(False)
            return
            
        try:
            # 检查权限
            import platform
            if platform.system() == "Darwin":
                # macOS权限检查
                try:
                    # 尝试创建一个测试监听器
                    test_listener = keyboard.Listener(on_press=lambda key: None)
                    test_listener.start()
                    test_listener.stop()
                except Exception as perm_error:
                    messagebox.showerror("权限错误", 
                                       "需要授予辅助功能权限:\n"
                                       "1. 打开'系统偏好设置'\n"
                                       "2. 进入'安全性与隐私'\n"
                                       "3. 点击'辅助功能'\n"
                                       "4. 添加Terminal或Python到允许列表")
                    self.hotkey_var.set(False)
                    return
            
            self.hotkey_enabled = True
            
            def safe_on_key_press(key):
                try:
                    # 安全的键处理
                    key_name = None
                    if hasattr(key, 'name'):
                        key_name = key.name.lower()
                    elif hasattr(key, 'char') and key.char:
                        key_name = key.char.lower()
                    
                    if key_name:
                        self.pressed_keys.add(key_name)
                        
                    # 检查快捷键组合（简化判断逻辑）
                    has_modifier = ('cmd' in self.pressed_keys or 'ctrl_l' in self.pressed_keys or 'ctrl_r' in self.pressed_keys)
                    has_alt = ('alt' in self.pressed_keys or 'alt_l' in self.pressed_keys or 'alt_r' in self.pressed_keys)
                    has_e = 'e' in self.pressed_keys
                    
                    if has_modifier and has_alt and has_e and self.hotkey_enabled:
                        # 使用线程安全的方式调用截图
                        self.root.after_idle(self.hotkey_capture)
                        
                except Exception as e:
                    print(f"按键处理错误: {e}")
                    
            def safe_on_key_release(key):
                try:
                    key_name = None
                    if hasattr(key, 'name'):
                        key_name = key.name.lower()
                    elif hasattr(key, 'char') and key.char:
                        key_name = key.char.lower()
                    
                    if key_name:
                        self.pressed_keys.discard(key_name)
                except Exception as e:
                    print(f"按键释放处理错误: {e}")
            
            # 在单独线程中启动监听器
            def start_listener():
                try:
                    self.keyboard_listener = keyboard.Listener(
                        on_press=safe_on_key_press,
                        on_release=safe_on_key_release,
                        suppress=False  # 不抑制按键，避免系统冲突
                    )
                    self.keyboard_listener.start()
                    # 在主线程中更新状态
                    self.root.after(0, lambda: self.status_label.config(text="快捷键已启用: Cmd+Opt+E"))
                except Exception as e:
                    print(f"监听器启动失败: {e}")
                    self.root.after(0, lambda: [
                        self.hotkey_var.set(False),
                        self.status_label.config(text=f"快捷键启动失败: {str(e)}")
                    ])
                    self.hotkey_enabled = False
            
            # 使用线程启动监听器，避免阻塞主线程
            listener_thread = threading.Thread(target=start_listener, daemon=True)
            listener_thread.start()
            
        except Exception as e:
            print(f"快捷键启动失败: {e}")
            messagebox.showerror("错误", f"快捷键启动失败: {e}")
            self.hotkey_var.set(False)
            self.hotkey_enabled = False
            
    def stop_hotkey_listener(self):
        """停止快捷键监听"""
        self.hotkey_enabled = False
        
        try:
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
                
            self.pressed_keys.clear()
            self.status_label.config(text="快捷键已禁用")
        except Exception as e:
            print(f"停止快捷键监听时出错: {e}")
            # 强制清理
            self.keyboard_listener = None
            self.pressed_keys.clear()
        
    def hotkey_capture(self):
        """快捷键触发的截图功能"""
        try:
            if all(coord is not None for coord in [self.start_x, self.start_y, self.end_x, self.end_y]):
                self.capture_screenshot()
                # 显示快捷键截图反馈
                try:
                    original_text = self.status_label.cget("text")
                    self.status_label.config(text="快捷键截图完成!")
                    self.root.after(2000, lambda: self.status_label.config(text=original_text) if self.status_label.winfo_exists() else None)
                except Exception as ui_error:
                    print(f"UI更新错误: {ui_error}")
        except Exception as e:
            print(f"快捷键截图错误: {e}")
    
    def capture_screenshot(self):
        """截取屏幕截图并保存"""
        if all(coord is not None for coord in [self.start_x, self.start_y, self.end_x, self.end_y]):
            try:
                # 计算区域参数，确保都是整数
                region_x = int(self.start_x)
                region_y = int(self.start_y)
                region_width = int(self.end_x - self.start_x)
                region_height = int(self.end_y - self.start_y)
                
                # 截取指定区域
                screenshot = pyautogui.screenshot(region=(region_x, region_y, region_width, region_height))
                
                # 生成文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"jump_jump_{self.image_count:04d}_{timestamp}.jpg"
                filepath = os.path.join(self.save_path, filename)
                
                # 转换为RGB模式（JPEG不支持透明通道）
                if screenshot.mode == 'RGBA':
                    # 创建白色背景
                    rgb_screenshot = Image.new('RGB', screenshot.size, (255, 255, 255))
                    rgb_screenshot.paste(screenshot, mask=screenshot.split()[-1])  # 使用alpha通道作为mask
                    screenshot = rgb_screenshot
                elif screenshot.mode != 'RGB':
                    screenshot = screenshot.convert('RGB')
                
                # 保存图片
                screenshot.save(filepath, "JPEG", quality=95)
                
                # 更新计数器和状态
                self.image_count += 1
                self.count_label.config(text=f"已采集图片: {self.image_count}")
                self.status_label.config(text=f"已保存: {filename}")
                
                print(f"图片已保存: {filepath}")
                
            except Exception as e:
                messagebox.showerror("错误", f"截图失败: {e}")
                print(f"截图失败: {e}")
    
    def on_closing(self):
        """关闭应用时的清理工作"""
        try:
            # 停止实时预览
            self.stop_preview()
            
            # 停止快捷键监听
            self.stop_hotkey_listener()
            
            # 停止鼠标监听
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
                
        except Exception as e:
            print(f"清理资源时出错: {e}")
        finally:
            # 确保窗口关闭
            try:
                self.root.destroy()
            except:
                pass
        
    def run(self):
        """运行应用"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 检查是否需要辅助功能权限提示（macOS）
        try:
            import platform
            if platform.system() == "Darwin":
                self.status_label.config(text="macOS用户可能需要授予辅助功能权限")
        except:
            pass
            
        self.root.mainloop()


def main():
    app = DataCollector()
    app.run()


if __name__ == "__main__":
    main()