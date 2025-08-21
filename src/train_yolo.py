#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import torch
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich import box
import yaml

console = Console()

class JumpJumpTrainer:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_path = self.project_root / "assets" / "config" / "jump_jump.yaml"
        self.dataset_path = self.project_root / "yolo_dataset"
        self.runs_dir = self.project_root / "runs"
        
        # 训练参数
        self.epochs = 100
        self.batch_size = 16   # Small模型可以使用更大batch size
        self.img_size = 640
        self.device = self.detect_device()
        self.model_name = 'yolov8s.pt'  # 使用Small模型
        
        # 确保目录存在
        self.runs_dir.mkdir(exist_ok=True)
    
    def detect_device(self):
        """检测最佳训练设备"""
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            if device_count > 0:
                # 检查第一个GPU的内存
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB
                console.print(f"[green]🎮 检测到GPU: {gpu_name} ({gpu_memory:.1f}GB)[/green]")
                return 0  # 使用第一个GPU
        
        console.print("[yellow]💻 未检测到可用GPU，使用CPU训练[/yellow]")
        return 'cpu'
        
    def check_dataset(self):
        """检查数据集状态"""
        console.print("[bold cyan]🔍 检查数据集状态...[/bold cyan]")
        
        if not self.dataset_path.exists():
            console.print("[red]❌ YOLO数据集目录不存在，请先运行数据集准备脚本[/red]")
            return False
        
        # 统计数据
        train_images = len(list((self.dataset_path / "train" / "images").glob("*")))
        train_labels = len(list((self.dataset_path / "train" / "labels").glob("*.txt")))
        val_images = len(list((self.dataset_path / "val" / "images").glob("*")))
        val_labels = len(list((self.dataset_path / "val" / "labels").glob("*.txt")))
        
        # 显示数据集信息
        table = Table(title="数据集检查", box=box.ROUNDED)
        table.add_column("类型", style="cyan", no_wrap=True)
        table.add_column("图片", style="magenta", justify="right")
        table.add_column("标注", style="green", justify="right")
        table.add_column("状态", style="yellow")
        
        train_status = "✅" if train_images == train_labels and train_images > 0 else "❌"
        val_status = "✅" if val_images == val_labels and val_images > 0 else "❌"
        
        table.add_row("训练集", str(train_images), str(train_labels), train_status)
        table.add_row("验证集", str(val_images), str(val_labels), val_status)
        
        console.print(table)
        
        if train_images == 0 or val_images == 0:
            console.print("[red]❌ 数据集不完整，请先运行数据准备脚本[/red]")
            return False
            
        return True
    
    def create_training_config(self):
        """创建训练配置"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_name = f"jump_jump_small_{timestamp}"
        
        # 根据设备调整配置
        if self.device != 'cpu':
            # GPU配置
            workers = 8
            cache_mode = True  # GPU可以使用缓存
            patience = 30
        else:
            # CPU配置
            workers = 2
            cache_mode = 'ram'
            patience = 50  # CPU训练更慢，增加耐心
        
        config = {
            "model": self.model_name,  # 使用Small模型
            "data": str(self.config_path),
            "epochs": self.epochs,
            "batch": self.batch_size,
            "imgsz": self.img_size,
            "device": self.device,
            "project": str(self.runs_dir),
            "name": self.run_name,
            "save": True,
            "save_period": 1,  # 每1个epoch保存一次
            "patience": patience,
            "cache": cache_mode,
            "workers": workers,
            "verbose": True
        }
        
        return config
    
    def display_training_info(self, config):
        """显示训练信息"""
        device_str = f"GPU {config['device']}" if config['device'] != 'cpu' else "CPU"
        
        info_panel = Panel.fit(
            f"""[bold]🎯 跳一跳YOLO训练配置 - 合并数据集版本[/bold]

[cyan]模型配置[/cyan]
• 模型: YOLOv8 Small (性能优化)
• 图片尺寸: {config['imgsz']}x{config['imgsz']}
• 批次大小: {config['batch']}
• 训练轮数: {config['epochs']}
• 设备: {device_str}
• 工作进程: {config['workers']}

[green]数据配置[/green]
• 数据集: 手动采集 + 自动生成 (合并)
• 类别数: 2 (小人、方块)
• 早停轮数: {config['patience']}
• 缓存模式: {config['cache']}

[yellow]输出配置[/yellow]
• 运行名称: {config['name']}
• 保存目录: {config['project']}/{config['name']}
• 模型保存: 每{config['save_period']}轮保存一次
• 断点续训: 支持
""",
            title="训练配置",
            border_style="green"
        )
        console.print(info_panel)
    
    def find_latest_checkpoint(self):
        """查找最新的检查点"""
        if not self.runs_dir.exists():
            return None
            
        # 查找最新的训练运行
        latest_run = None
        latest_time = 0
        
        for run_dir in self.runs_dir.iterdir():
            if run_dir.is_dir() and (run_dir.name.startswith("jump_jump_nano") or run_dir.name.startswith("jump_jump_small")):
                weights_dir = run_dir / "weights"
                if weights_dir.exists():
                    # 查找last.pt文件
                    last_pt = weights_dir / "last.pt"
                    if last_pt.exists():
                        mod_time = last_pt.stat().st_mtime
                        if mod_time > latest_time:
                            latest_time = mod_time
                            latest_run = last_pt
        
        return latest_run

    def train_model(self):
        """训练YOLO模型"""
        console.print("[bold green]🚀 开始训练YOLO模型...[/bold green]")
        
        # 检查数据集
        if not self.check_dataset():
            return False
        
        # 直接开始新训练，不询问续训
        model = YOLO(self.model_name)
        console.print("[yellow]📥 加载YOLOv8 Nano模型...[/yellow]")
        
        # 创建配置
        config = self.create_training_config()
        self.display_training_info(config)
        
        # 设置训练环境
        if self.device == 'cpu':
            console.print("[cyan]💻 配置CPU训练环境...[/cyan]")
            torch.set_num_threads(4)  # 限制CPU线程数
        else:
            console.print(f"[green]🎮 配置GPU训练环境 (GPU {self.device})...[/green]")
            torch.cuda.set_device(self.device)
        
        try:
            # 开始训练
            console.print("[bold green]🏃‍♂️ 开始训练...[/bold green]")
            
            results = model.train(
                data=str(self.config_path),
                epochs=config['epochs'],
                batch=config['batch'],
                imgsz=config['imgsz'],
                device=config['device'],
                project=config['project'],
                name=config['name'],
                save=config['save'],
                save_period=config['save_period'],
                patience=config['patience'],
                cache=config['cache'],
                workers=config['workers'],
                verbose=config['verbose'],
                pretrained=True,
                optimizer='AdamW',
                lr0=0.01,
                warmup_epochs=5,
                weight_decay=0.0005
            )
            
            # 训练完成
            model_path = self.runs_dir / self.run_name / "weights" / "best.pt"
            
            success_panel = Panel.fit(
                f"""[bold green]🎉 训练完成！[/bold green]

[cyan]模型文件[/cyan]
• 最佳模型: {model_path}
• 运行目录: {self.runs_dir / self.run_name}

[yellow]下一步[/yellow]
• 查看训练结果: {self.runs_dir / self.run_name}
• 测试模型性能: python test_model.py
• 集成到游戏AI: 使用训练好的模型进行推理
""",
                title="训练完成",
                border_style="green"
            )
            console.print(success_panel)
            
            return True
            
        except KeyboardInterrupt:
            console.print("[yellow]⚠️ 训练被用户中断[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red]❌ 训练失败: {e}[/red]")
            return False
    
    def show_system_info(self):
        """显示系统信息"""
        device_info = []
        if torch.cuda.is_available():
            device_info.append(f"• PyTorch版本: {torch.__version__} (CUDA {torch.version.cuda})")
            device_info.append(f"• 训练设备: GPU {self.device}")
            if self.device != 'cpu':
                gpu_name = torch.cuda.get_device_name(self.device)
                gpu_memory = torch.cuda.get_device_properties(self.device).total_memory / 1024**3
                device_info.append(f"• GPU型号: {gpu_name}")
                device_info.append(f"• GPU内存: {gpu_memory:.1f}GB")
        else:
            device_info.append(f"• PyTorch版本: {torch.__version__}")
            device_info.append(f"• 训练设备: CPU")
            device_info.append(f"• CPU线程数: {torch.get_num_threads()}")
        
        info_panel = Panel.fit(
            f"""[bold]💻 系统信息[/bold]

[cyan]设备信息[/cyan]
{chr(10).join(device_info)}

[green]项目信息[/green]
• 项目路径: {self.project_root}
• 数据集路径: {self.dataset_path}
• 配置文件: {self.config_path}
""",
            title="环境检查",
            border_style="blue"
        )
        console.print(info_panel)


def main():
    """主程序"""
    console.print("[bold blue]🎮 跳一跳YOLO模型训练程序 - Small模型 + 合并数据集[/bold blue]")
    
    trainer = JumpJumpTrainer()
    trainer.show_system_info()
    
    # 检查配置文件
    if not trainer.config_path.exists():
        console.print(f"[red]❌ 配置文件不存在: {trainer.config_path}[/red]")
        return
    
    # 检查数据集
    if not trainer.dataset_path.exists():
        console.print("[yellow]⚠️ YOLO数据集不存在，正在准备数据集...[/yellow]")
        from tools.prepare_dataset import prepare_yolo_dataset
        if not prepare_yolo_dataset():
            console.print("[red]❌ 数据集准备失败[/red]")
            return
    
    # 开始训练
    if trainer.train_model():
        console.print("[bold green]🎉 训练流程完成！[/bold green]")
    else:
        console.print("[bold red]❌ 训练失败[/bold red]")


if __name__ == "__main__":
    main()