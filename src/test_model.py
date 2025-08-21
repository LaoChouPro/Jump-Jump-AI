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
from rich.table import Table
from rich import box
import yaml

console = Console()

class ModelTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_path = self.project_root / "assets" / "config" / "jump_jump.yaml"
        self.dataset_path = self.project_root / "yolo_dataset"
        
        # 模型路径
        self.model_dir = self.project_root / "assets" / "models"
        self.model_dir.mkdir(exist_ok=True)
        
        # 结果目录
        self.results_dir = self.project_root / "test_results"
        self.results_dir.mkdir(exist_ok=True)
        
    def copy_model_from_desktop(self, model_name="epoch92.pt"):
        """从桌面复制模型到工作目录"""
        # macOS桌面路径
        desktop_path = Path.home() / "Desktop" / model_name
        
        console.print(f"[cyan]📂 寻找模型文件 {model_name}...[/cyan]")
        
        if desktop_path.exists():
            target_path = self.model_dir / model_name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            console.print(f"[green]✅ 找到模型: {desktop_path}[/green]")
            console.print(f"[yellow]📋 复制到: {target_path}[/yellow]")
            
            import shutil
            shutil.copy2(desktop_path, target_path)
            
            console.print(f"[green]✅ 模型复制完成![/green]")
            return target_path
        
        console.print(f"[red]❌ 未找到模型文件: {desktop_path}[/red]")
        return None
    
    def load_model(self, model_path):
        """加载YOLO模型"""
        try:
            model = YOLO(str(model_path))
            console.print(f"[green]✅ 成功加载模型: {model_path}[/green]")
            return model
        except Exception as e:
            console.print(f"[red]❌ 加载模型失败: {e}[/red]")
            return None
    
    def check_dataset(self):
        """检查测试数据集"""
        if not self.dataset_path.exists():
            console.print("[red]❌ 数据集目录不存在[/red]")
            return False
        
        val_images = self.dataset_path / "val" / "images"
        val_labels = self.dataset_path / "val" / "labels"
        
        if not val_images.exists() or not val_labels.exists():
            console.print("[red]❌ 验证集不存在[/red]")
            return False
        
        image_count = len(list(val_images.glob("*")))
        label_count = len(list(val_labels.glob("*.txt")))
        
        console.print(f"[cyan]📊 验证集: {image_count} 张图片, {label_count} 个标注文件[/cyan]")
        
        if image_count == 0:
            console.print("[red]❌ 验证集为空[/red]")
            return False
        
        return True
    
    def evaluate_model(self, model, model_name="epoch92"):
        """评估模型性能"""
        console.print("[bold green]🔍 开始模型评估...[/bold green]")
        
        try:
            # 运行验证
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            console.print(f"[cyan]🔧 使用设备: {device}[/cyan]")
            
            results = model.val(
                data=str(self.config_path),
                imgsz=640,
                batch=8 if device == 'cuda' else 4,
                device=device,
                save_json=True,
                save=True,
                project=str(self.results_dir),
                name=f"{model_name}_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                verbose=True
            )
            
            # 显示评估结果
            self.display_results(results, model_name)
            
            return results
            
        except Exception as e:
            console.print(f"[red]❌ 模型评估失败: {e}[/red]")
            return None
    
    def display_results(self, results, model_name):
        """显示评估结果"""
        console.print("\n")
        
        # 创建结果表格
        table = Table(title=f"{model_name} 模型评估结果", box=box.ROUNDED)
        table.add_column("指标", style="cyan", no_wrap=True)
        table.add_column("小人 (Person)", style="magenta", justify="right")
        table.add_column("方块 (Block)", style="green", justify="right")
        table.add_column("总体 (Overall)", style="yellow", justify="right")
        
        # 获取结果数据
        try:
            # mAP@0.5
            map50 = results.results_dict.get('metrics/mAP50(B)', 0)
            map50_person = getattr(results, 'map50', [0, 0])[0] if hasattr(results, 'map50') else 0
            map50_block = getattr(results, 'map50', [0, 0])[1] if hasattr(results, 'map50') and len(getattr(results, 'map50', [])) > 1 else 0
            
            # mAP@0.5:0.95
            map = results.results_dict.get('metrics/mAP50-95(B)', 0)
            
            # Precision and Recall
            precision = results.results_dict.get('metrics/precision(B)', 0)
            recall = results.results_dict.get('metrics/recall(B)', 0)
            
            table.add_row("mAP@0.5", f"{map50_person:.3f}", f"{map50_block:.3f}", f"{map50:.3f}")
            table.add_row("mAP@0.5:0.95", "—", "—", f"{map:.3f}")
            table.add_row("Precision", "—", "—", f"{precision:.3f}")
            table.add_row("Recall", "—", "—", f"{recall:.3f}")
            
        except Exception as e:
            console.print(f"[yellow]⚠️ 解析结果时出错: {e}[/yellow]")
            table.add_row("总体mAP@0.5", "—", "—", "计算中...")
        
        console.print(table)
        
        # 显示总结面板
        summary_panel = Panel.fit(
            f"""[bold green]🎯 模型评估总结[/bold green]

[cyan]模型信息[/cyan]
• 模型名称: {model_name}
• 评估数据集: 验证集
• 图片尺寸: 640x640
• 批次大小: 8

[green]性能指标[/green]
• mAP@0.5: {map50:.1%} (越高越好)
• mAP@0.5:0.95: {map:.1%} (越高越好)
• Precision: {precision:.1%} (精确率)
• Recall: {recall:.1%} (召回率)

[yellow]评估建议[/yellow]
{'• 🎉 模型性能优秀!' if map50 > 0.8 else '• 📈 模型性能良好，可考虑继续训练' if map50 > 0.6 else '• ⚠️ 模型性能有待提高，建议增加训练数据或调整参数'}
""",
            title="评估完成",
            border_style="green"
        )
        console.print(summary_panel)
    
    def show_system_info(self):
        """显示系统信息"""
        device_info = []
        if torch.cuda.is_available():
            device_info.append(f"• PyTorch版本: {torch.__version__} (CUDA {torch.version.cuda})")
            device_info.append(f"• GPU设备: {torch.cuda.get_device_name(0)}")
            device_info.append(f"• GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
        else:
            device_info.append(f"• PyTorch版本: {torch.__version__}")
            device_info.append(f"• 设备: CPU")
        
        info_panel = Panel.fit(
            f"""[bold]🖥️ 测试环境信息[/bold]

[cyan]设备信息[/cyan]
{chr(10).join(device_info)}

[green]项目信息[/green]
• 项目路径: {self.project_root}
• 数据集路径: {self.dataset_path}
• 配置文件: {self.config_path}
• 模型目录: {self.model_dir}
• 结果目录: {self.results_dir}
""",
            title="环境检查",
            border_style="blue"
        )
        console.print(info_panel)

def main():
    """主程序"""
    console.print("[bold blue]🎮 跳一跳YOLO模型测试程序[/bold blue]")
    
    tester = ModelTester()
    tester.show_system_info()
    
    # 检查配置文件
    if not tester.config_path.exists():
        console.print(f"[red]❌ 配置文件不存在: {tester.config_path}[/red]")
        return
    
    # 检查数据集
    if not tester.check_dataset():
        console.print("[red]❌ 测试数据集检查失败[/red]")
        return
    
    # 复制模型
    model_path = tester.copy_model_from_desktop("epoch92.pt")
    if not model_path:
        console.print("[red]❌ 模型文件复制失败[/red]")
        return
    
    # 加载模型
    model = tester.load_model(model_path)
    if not model:
        console.print("[red]❌ 模型加载失败[/red]")
        return
    
    # 评估模型
    results = tester.evaluate_model(model, "epoch92")
    
    if results:
        console.print("[bold green]🎉 模型评估完成！[/bold green]")
        console.print(f"[cyan]详细结果保存在: {tester.results_dir}[/cyan]")
    else:
        console.print("[bold red]❌ 模型评估失败[/bold red]")

if __name__ == "__main__":
    main()