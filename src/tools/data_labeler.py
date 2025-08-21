#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os


class DataLabeler:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("跳一跳数据标注工具")
        self.root.geometry("1400x900")
        
        # 数据路径（使用绝对路径）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 支持多个数据源
        self.data_sources = {
            "手动采集数据": {
                "images": os.path.join(project_root, "data", "images"),
                "labels": os.path.join(project_root, "data", "labels")
            },
            "自动生成数据": {
                "images": os.path.join(project_root, "auto_generated_data", "images"),
                "labels": os.path.join(project_root, "auto_generated_data", "labels")
            }
        }
        
        # 默认使用手动采集数据
        self.current_source = "手动采集数据"
        self.images_path = self.data_sources[self.current_source]["images"]
        self.labels_path = self.data_sources[self.current_source]["labels"]
        
        # 确保标注目录存在
        if not os.path.exists(self.labels_path):
            os.makedirs(self.labels_path)
        
        # 类别定义（更新为2类）
        self.classes = {
            "小人": 0,
            "方块": 1
        }
        
        # 类别颜色
        self.class_colors = {
            0: "red",      # 小人
            1: "blue"     # 方块
        }
        
        # 当前状态
        self.current_image_index = 0
        self.image_files = []
        self.current_image = None
        self.current_photo = None
        self.annotations = []
        self.selected_class = 0
        
        # 快速标注模式
        self.fast_mode = False
        self.target_annotations_count = 0  # 不限制标注数量，每次框选自动保存
        self.annotation_sequence = [0, 1]  # 标注顺序：小人 -> 方块
        
        # 鼠标操作状态
        self.drawing = False
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        
        # 显示比例
        self.display_scale = 1.0
        self.display_width = 1000
        self.display_height = 700
        
        self.load_image_list()
        self.setup_ui()
        self.update_source_status()
        self.load_current_image()
        
    def load_image_list(self):
        """加载图片列表"""
        if not os.path.exists(self.images_path):
            messagebox.showerror("错误", f"图片目录不存在: {self.images_path}")
            return
            
        self.image_files = [f for f in os.listdir(self.images_path) 
                           if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        self.image_files.sort()
        
        if not self.image_files:
            messagebox.showwarning("警告", "图片目录中没有找到图片文件")
            
    def setup_ui(self):
        """设置用户界面 - 上下分割布局"""
        # 顶部控制栏
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 底部图片显示区域
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        self.setup_control_panel(top_frame)
        self.setup_image_panel(bottom_frame)
        
    def setup_control_panel(self, parent):
        """设置控制面板 - 水平布局"""
        # 主控制容器
        main_control = ttk.Frame(parent)
        main_control.pack(fill=tk.X, pady=5)
        
        # 左侧：数据源选择和文件导航
        left_control = ttk.LabelFrame(main_control, text="数据源控制", padding="10")
        left_control.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 数据源选择
        data_source_frame = ttk.Frame(left_control)
        data_source_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(data_source_frame, text="数据源:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        self.source_var = tk.StringVar(value=self.current_source)
        for source_name in self.data_sources.keys():
            rb = ttk.Radiobutton(data_source_frame, text=source_name, 
                               variable=self.source_var, value=source_name,
                               command=self.switch_data_source)
            rb.pack(anchor=tk.W, pady=1)
        
        # 数据源状态
        self.source_status_label = ttk.Label(data_source_frame, text="", 
                                           font=("Arial", 9), foreground="green")
        self.source_status_label.pack(anchor=tk.W, pady=(5, 0))
        
        # 文件信息
        self.file_info_label = ttk.Label(left_control, text="", font=("Arial", 10))
        self.file_info_label.pack(pady=(10, 10))
        
        # 导航按钮
        nav_frame = ttk.Frame(left_control)
        nav_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.prev_button = ttk.Button(nav_frame, text="◀ 上一张", command=self.prev_image)
        self.prev_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.next_button = ttk.Button(nav_frame, text="下一张 ▶", command=self.next_image)
        self.next_button.pack(side=tk.LEFT)
        
        # 快速模式开关
        self.fast_mode_var = tk.BooleanVar(value=True)  # 默认开启自动保存
        fast_mode_check = ttk.Checkbutton(left_control, text="自动保存模式", 
                                        variable=self.fast_mode_var, command=self.toggle_fast_mode)
        fast_mode_check.pack(pady=(10, 0))
        self.fast_mode = True  # 默认开启
        
        # 中间：类别选择
        class_control = ttk.LabelFrame(main_control, text="标注类别", padding="10")
        class_control.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.class_var = tk.IntVar(value=0)
        for class_name, class_id in self.classes.items():
            color = self.class_colors[class_id]
            rb = ttk.Radiobutton(class_control, text=f"{class_name}", 
                               variable=self.class_var, value=class_id,
                               command=self.on_class_changed)
            rb.pack(anchor=tk.W, pady=2)
            
        # 类别提示和录捷键说明
        color_info = ttk.Label(class_control, text="红色=小人, 蓝色=方块", 
                             font=("Arial", 9), foreground="gray")
        color_info.pack(pady=(5, 0))
        
        # 快捷键说明
        shortcut_info = ttk.Label(class_control, text="Tab=切换类别, 空格=下一张", 
                                font=("Arial", 9), foreground="blue")
        shortcut_info.pack(pady=(2, 0))
        
        # 当前类别提示
        self.current_class_label = ttk.Label(class_control, text="", 
                                           font=("Arial", 10, "bold"), foreground="blue")
        self.current_class_label.pack(pady=(5, 0))
        
        # 右侧：标注操作和列表
        right_control = ttk.LabelFrame(main_control, text="标注管理", padding="10")
        right_control.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 操作按钮行
        button_row = ttk.Frame(right_control)
        button_row.pack(fill=tk.X, pady=(0, 10))
        
        # 手动保存按钮（备用）
        save_button = ttk.Button(button_row, text="手动保存", command=self.save_annotations)
        save_button.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_button = ttk.Button(button_row, text="清除所有", command=self.clear_annotations)
        clear_button.pack(side=tk.LEFT, padx=(0, 5))
        
        auto_next_button = ttk.Button(button_row, text="跳转未标注", command=self.find_next_unlabeled)
        auto_next_button.pack(side=tk.LEFT)
        
        # 进度信息
        self.progress_label = ttk.Label(button_row, text="", font=("Arial", 10, "bold"))
        self.progress_label.pack(side=tk.RIGHT)
        
        # 当前标注列表（水平滚动）
        list_frame = ttk.Frame(right_control)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标注列表
        self.annotation_listbox = tk.Listbox(list_frame, height=4, font=("Arial", 10))
        list_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.annotation_listbox.yview)
        self.annotation_listbox.configure(yscrollcommand=list_scrollbar.set)
        
        self.annotation_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定删除事件
        self.annotation_listbox.bind('<Delete>', self.delete_selected_annotation)
        self.annotation_listbox.bind('<Double-Button-1>', self.delete_selected_annotation)
        
    def setup_image_panel(self, parent):
        """设置图片显示面板"""
        # 图片画布容器
        canvas_container = ttk.Frame(parent)
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        # 创建画布和滚动条
        self.canvas = tk.Canvas(canvas_container, bg="white")
        
        h_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        
        # 布局
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        # 绑定鼠标事件
        self.canvas.bind("<Button-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        
        # 绑定键盘事件
        self.canvas.focus_set()  # 设置焦点以接收键盘事件
        self.root.bind("<KeyPress-Tab>", self.on_tab_press)
        self.root.bind("<KeyPress-space>", self.on_space_press)
        self.canvas.bind("<KeyPress-Tab>", self.on_tab_press)
        self.canvas.bind("<KeyPress-space>", self.on_space_press)
        
    def toggle_fast_mode(self):
        """切换快速标注模式"""
        self.fast_mode = self.fast_mode_var.get()
        if self.fast_mode:
            # 重置到第一个类别
            self.reset_fast_mode_state()
            self.update_progress_info()
            messagebox.showinfo("自动保存模式", 
                              "自动保存模式已启用！\n"
                              "每次框选、删除、清除操作后\n"
                              "都会自动保存到文件！")
        else:
            self.progress_label.config(text="")
            
    def reset_fast_mode_state(self):
        """重置快速模式状态"""
        # 设置为第一个类别（小人）
        self.selected_class = self.annotation_sequence[0]
        self.class_var.set(self.selected_class)
        
    def set_fast_mode_class_based_on_annotations(self):
        """根据已有标注数量设置当前应该标注的类别"""
        if not self.fast_mode:
            return
            
        current_count = len(self.annotations)
        
        # 根据已标注数量确定下一个应该标注的类别
        if current_count < len(self.annotation_sequence):
            next_class = self.annotation_sequence[current_count]
            self.selected_class = next_class
            self.class_var.set(next_class)
        else:
            # 如果已经标注完成，保持最后一个类别
            self.selected_class = self.annotation_sequence[-1]
            self.class_var.set(self.selected_class)
        
    def update_progress_info(self):
        """更新进度信息"""
        if self.fast_mode:
            current_count = len(self.annotations)
            class_names = {v: k for k, v in self.classes.items()}
            current_class_name = class_names.get(self.selected_class, "")
            
            self.progress_label.config(text=f"已标注: {current_count}个 - 当前: {current_class_name}")
            self.current_class_label.config(text=f"→ {current_class_name} (Tab切换)", 
                                          foreground=self.class_colors.get(self.selected_class, "blue"))
        else:
            self.progress_label.config(text="")
            self.current_class_label.config(text="")
            
    def auto_save_to_file(self):
        """自动保存到文件"""
        if not self.image_files:
            return
            
        filename = self.image_files[self.current_image_index]
        label_filename = os.path.splitext(filename)[0] + ".txt"
        label_path = os.path.join(self.labels_path, label_filename)
        
        try:
            # 如果没有标注，删除文件（如果存在）
            if not self.annotations:
                if os.path.exists(label_path):
                    os.remove(label_path)
            else:
                # 保存标注到文件
                with open(label_path, 'w') as f:
                    for ann in self.annotations:
                        f.write(f"{ann['class_id']} {ann['center_x']:.6f} {ann['center_y']:.6f} {ann['width']:.6f} {ann['height']:.6f}\n")
            
            # 更新文件状态显示
            status = "已标注" if self.annotations else "未标注"
            self.file_info_label.config(text=f"{self.current_image_index + 1}/{len(self.image_files)}: {filename} ({status})")
            
        except Exception as e:
            print(f"自动保存失败: {e}")
            
    def next_or_find_unlabeled(self):
        """跳转下一张或查找未标注图片"""
        if self.current_image_index < len(self.image_files) - 1:
            self.next_image()
        else:
            self.find_next_unlabeled()
        
    def on_tab_press(self, event=None):
        """按Tab键快速切换类别"""
        # 在小人(0)和方块(1)之间切换
        current_class = self.class_var.get()
        new_class = 1 if current_class == 0 else 0
        
        self.class_var.set(new_class)
        self.selected_class = new_class
        
        # 更新显示
        class_names = {v: k for k, v in self.classes.items()}
        class_name = class_names.get(new_class, "")
        
        # 短暂显示切换提示
        original_text = self.current_class_label.cget("text")
        self.current_class_label.config(text=f"✓ 已切换到: {class_name}", foreground="orange")
        self.root.after(1000, lambda: self.update_progress_info())
        
        return "break"  # 阻止Tab键的默认行为
    
    def on_space_press(self, event=None):
        """按空格键自动下一张图片"""
        if self.current_image_index < len(self.image_files) - 1:
            self.next_image()
        else:
            # 如果已是最后一张，查找未标注的
            self.find_next_unlabeled()
        
        return "break"  # 阻止空格键的默认行为
    
    def smart_class_switch(self):
        """智能类别切换：标注完小人后自动切换到方块"""
        # 统计当前各类别的标注数量
        class_counts = {0: 0, 1: 0}  # 小人, 方块
        for ann in self.annotations:
            class_counts[ann['class_id']] += 1
        
        # 如果刚标注了小人，且当前还是小人类别，且已有1个小人标注
        if (self.selected_class == 0 and 
            class_counts[0] >= 1):
            
            # 自动切换到方块类别
            self.class_var.set(1)
            self.selected_class = 1
            
            # 显示切换提示
            self.current_class_label.config(text="✓ 小人已标注，自动切换到方块", foreground="green")
            self.root.after(1500, self.update_progress_info)
        
    def on_class_changed(self):
        """类别选择改变"""
        self.selected_class = self.class_var.get()
    
    def switch_data_source(self):
        """切换数据源"""
        new_source = self.source_var.get()
        if new_source != self.current_source:
            self.current_source = new_source
            self.images_path = self.data_sources[self.current_source]["images"]
            self.labels_path = self.data_sources[self.current_source]["labels"]
            
            # 确保标注目录存在
            if not os.path.exists(self.labels_path):
                os.makedirs(self.labels_path)
            
            # 重新加载图片列表
            self.current_image_index = 0
            self.load_image_list()
            self.update_source_status()
            self.load_current_image()
            
            print(f"✅ 切换到数据源: {new_source}")
            print(f"   图片目录: {self.images_path}")
            print(f"   标注目录: {self.labels_path}")
    
    def update_source_status(self):
        """更新数据源状态显示"""
        if hasattr(self, 'source_status_label'):
            image_count = len(self.image_files)
            if image_count > 0:
                self.source_status_label.config(text=f"已找到 {image_count} 张图片", foreground="green")
            else:
                self.source_status_label.config(text="未找到图片文件", foreground="orange")
        
    def load_current_image(self):
        """加载当前图片"""
        if not self.image_files or self.current_image_index >= len(self.image_files):
            self.file_info_label.config(text="没有更多图片")
            return
            
        filename = self.image_files[self.current_image_index]
        image_path = os.path.join(self.images_path, filename)
        
        try:
            # 加载图片
            self.current_image = Image.open(image_path)
            original_width, original_height = self.current_image.size
            
            # 计算显示比例
            self.display_scale = min(self.display_width / original_width, 
                                   self.display_height / original_height, 1.0)
            
            new_width = int(original_width * self.display_scale)
            new_height = int(original_height * self.display_scale)
            
            # 调整图片大小
            display_image = self.current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(display_image)
            
            # 显示图片
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_photo)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # 加载已有标注
            self.load_annotations()
            self.draw_annotations()
            
            # 更新文件信息
            status = "已标注" if self.has_annotations() else "未标注"
            self.file_info_label.config(text=f"{self.current_image_index + 1}/{len(self.image_files)}: {filename} ({status})")
            
            # 快速模式：根据已有标注设置当前类别
            if self.fast_mode:
                self.set_fast_mode_class_based_on_annotations()
            
            # 更新进度信息
            self.update_progress_info()
            
            # 更新按钮状态
            self.prev_button.config(state="normal" if self.current_image_index > 0 else "disabled")
            self.next_button.config(state="normal" if self.current_image_index < len(self.image_files) - 1 else "disabled")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载图片失败: {e}")
            
    def has_annotations(self):
        """检查当前图片是否有标注"""
        filename = self.image_files[self.current_image_index]
        label_filename = os.path.splitext(filename)[0] + ".txt"
        label_path = os.path.join(self.labels_path, label_filename)
        return os.path.exists(label_path)
        
    def load_annotations(self):
        """加载当前图片的标注"""
        self.annotations = []
        if not self.image_files:
            return
            
        filename = self.image_files[self.current_image_index]
        label_filename = os.path.splitext(filename)[0] + ".txt"
        label_path = os.path.join(self.labels_path, label_filename)
        
        if os.path.exists(label_path):
            try:
                with open(label_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 5:
                            class_id = int(parts[0])
                            center_x = float(parts[1])
                            center_y = float(parts[2])
                            width = float(parts[3])
                            height = float(parts[4])
                            
                            self.annotations.append({
                                'class_id': class_id,
                                'center_x': center_x,
                                'center_y': center_y,
                                'width': width,
                                'height': height
                            })
            except Exception as e:
                print(f"加载标注失败: {e}")
        
        self.update_annotation_list()
        
    def update_annotation_list(self):
        """更新标注列表显示"""
        self.annotation_listbox.delete(0, tk.END)
        class_names = {v: k for k, v in self.classes.items()}
        
        for i, ann in enumerate(self.annotations):
            base_class_name = class_names.get(ann['class_id'], f"类别{ann['class_id']}")
            
            if ann['class_id'] == 1:  # 方块类别
                # 为方块编号：按y坐标排序（从上到下），相同y坐标按x坐标排序（从左到右）
                blocks = [a for a in self.annotations if a['class_id'] == 1]
                blocks_sorted = sorted(blocks, key=lambda x: (x['center_y'], x['center_x']))
                block_index = blocks_sorted.index(ann) + 1
                class_name = f"方块{block_index}"
            else:
                class_name = base_class_name
            
            color = self.class_colors.get(ann['class_id'], "black")
            text = f"{i+1}. {class_name} - ({ann['center_x']:.3f}, {ann['center_y']:.3f})"
            self.annotation_listbox.insert(tk.END, text)
            
    def draw_annotations(self):
        """在画布上绘制标注框"""
        if not self.current_image:
            return
            
        # 删除之前的标注框
        self.canvas.delete("annotation")
        
        img_width, img_height = self.current_image.size
        
        for ann in self.annotations:
            # 转换YOLO格式坐标到像素坐标
            center_x = ann['center_x'] * img_width * self.display_scale
            center_y = ann['center_y'] * img_height * self.display_scale
            width = ann['width'] * img_width * self.display_scale
            height = ann['height'] * img_height * self.display_scale
            
            x1 = center_x - width / 2
            y1 = center_y - height / 2
            x2 = center_x + width / 2
            y2 = center_y + height / 2
            
            color = self.class_colors.get(ann['class_id'], "black")
            
            # 绘制矩形框
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=3, tags="annotation")
            
            # 添加类别标签，为方块显示编号
            class_names = {v: k for k, v in self.classes.items()}
            base_class_name = class_names.get(ann['class_id'], f"类别{ann['class_id']}")
            
            if ann['class_id'] == 1:  # 方块类别
                # 为方块编号：按y坐标排序（从上到下），相同y坐标按x坐标排序（从左到右）
                blocks = [a for a in self.annotations if a['class_id'] == 1]
                blocks_sorted = sorted(blocks, key=lambda x: (x['center_y'], x['center_x']))
                block_index = blocks_sorted.index(ann) + 1
                class_name = f"方块{block_index}"
            else:
                class_name = base_class_name
                
            self.canvas.create_text(x1, y1-15, text=class_name, fill=color, anchor=tk.SW, 
                                  tags="annotation", font=("Arial", 12, "bold"))
            
    def on_mouse_press(self, event):
        """鼠标按下事件"""
        if not self.current_image:
            return
            
        self.drawing = True
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        
        # 删除之前的临时矩形
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            
    def on_mouse_drag(self, event):
        """鼠标拖拽事件"""
        if not self.drawing or not self.current_image:
            return
            
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        
        # 删除之前的临时矩形
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            
        # 绘制新的临时矩形
        color = self.class_colors.get(self.selected_class, "black")
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, 
                                                   current_x, current_y, 
                                                   outline=color, width=3)
        
    def on_mouse_release(self, event):
        """鼠标释放事件"""
        if not self.drawing or not self.current_image:
            return
            
        self.drawing = False
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        
        # 删除临时矩形
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        
        # 检查是否是有效的矩形（最小尺寸）
        if abs(end_x - self.start_x) < 10 or abs(end_y - self.start_y) < 10:
            return
            
        # 转换为YOLO格式并添加标注
        self.add_annotation(self.start_x, self.start_y, end_x, end_y)
        
    def add_annotation(self, x1, y1, x2, y2):
        """添加标注"""
        if not self.current_image:
            return
            
        # 确保坐标顺序正确
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
            
        img_width, img_height = self.current_image.size
        
        # 转换为YOLO格式（相对坐标）
        center_x = ((x1 + x2) / 2) / (img_width * self.display_scale)
        center_y = ((y1 + y2) / 2) / (img_height * self.display_scale)
        width = (x2 - x1) / (img_width * self.display_scale)
        height = (y2 - y1) / (img_height * self.display_scale)
        
        # 确保坐标在[0, 1]范围内
        center_x = max(0, min(1, center_x))
        center_y = max(0, min(1, center_y))
        width = max(0, min(1, width))
        height = max(0, min(1, height))
        
        annotation = {
            'class_id': self.selected_class,
            'center_x': center_x,
            'center_y': center_y,
            'width': width,
            'height': height
        }
        
        self.annotations.append(annotation)
        self.update_annotation_list()
        self.draw_annotations()
        
        # 每次框选后自动保存到文件
        self.auto_save_to_file()
        
        # 智能类别切换：标注完小人自动切换到方块
        self.smart_class_switch()
        
        self.update_progress_info()
        
    def delete_selected_annotation(self, event=None):
        """删除选中的标注"""
        selection = self.annotation_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.annotations):
                del self.annotations[index]
                self.update_annotation_list()
                self.draw_annotations()
                
                # 删除后自动保存到文件
                self.auto_save_to_file()
                self.update_progress_info()
                
    def clear_annotations(self):
        """清除所有标注"""
        if self.annotations and messagebox.askyesno("确认", "确定要清除所有标注吗？"):
            self.annotations = []
            self.update_annotation_list()
            self.draw_annotations()
            
            # 清除后自动保存到文件
            self.auto_save_to_file()
            self.update_progress_info()
            
    def save_annotations(self):
        """保存标注到文件"""
        if not self.image_files:
            return
            
        filename = self.image_files[self.current_image_index]
        label_filename = os.path.splitext(filename)[0] + ".txt"
        label_path = os.path.join(self.labels_path, label_filename)
        
        try:
            with open(label_path, 'w') as f:
                for ann in self.annotations:
                    f.write(f"{ann['class_id']} {ann['center_x']:.6f} {ann['center_y']:.6f} {ann['width']:.6f} {ann['height']:.6f}\n")
            
            status = "已标注" if self.annotations else "已清空"
            self.file_info_label.config(text=f"{self.current_image_index + 1}/{len(self.image_files)}: {filename} ({status})")
            
            messagebox.showinfo("保存成功", f"标注已保存: {label_filename}")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存标注失败: {e}")
            
    def prev_image(self):
        """上一张图片"""
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_current_image()
            
    def next_image(self):
        """下一张图片"""
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.load_current_image()
        
    def find_next_unlabeled(self):
        """查找下一个未标注的图片"""
        start_index = self.current_image_index + 1
        for i in range(start_index, len(self.image_files)):
            filename = self.image_files[i]
            label_filename = os.path.splitext(filename)[0] + ".txt"
            label_path = os.path.join(self.labels_path, label_filename)
            
            if not os.path.exists(label_path):
                self.current_image_index = i
                self.load_current_image()
                return
                
        # 如果没找到，从头开始找
        for i in range(0, start_index):
            filename = self.image_files[i]
            label_filename = os.path.splitext(filename)[0] + ".txt"
            label_path = os.path.join(self.labels_path, label_filename)
            
            if not os.path.exists(label_path):
                self.current_image_index = i
                self.load_current_image()
                return
                
        messagebox.showinfo("完成", "所有图片都已标注完成！")
        
    def run(self):
        """运行应用"""
        # 自动跳转到第一个未标注的图片
        self.find_next_unlabeled()
        self.root.mainloop()


def main():
    app = DataLabeler()
    app.run()


if __name__ == "__main__":
    main()