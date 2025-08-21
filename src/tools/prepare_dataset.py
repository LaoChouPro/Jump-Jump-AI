#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import random
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

def prepare_yolo_dataset():
    """准备YOLO训练数据集 - 合并手动和自动数据"""
    console.print("[bold green]🚀 准备YOLO训练数据集 - 合并多个数据源[/bold green]")
    
    # 项目路径
    project_root = Path(__file__).parent.parent
    
    # 数据源定义
    data_sources = {
        "手动采集数据": {
            "images": project_root / "data" / "images",
            "labels": project_root / "data" / "labels"
        },
        "自动生成数据": {
            "images": project_root / "auto_generated_data" / "images",
            "labels": project_root / "auto_generated_data" / "labels"
        }
    }
    
    # YOLO数据集目录
    yolo_dir = project_root / "yolo_dataset"
    train_images = yolo_dir / "train" / "images"
    train_labels = yolo_dir / "train" / "labels"
    val_images = yolo_dir / "val" / "images"
    val_labels = yolo_dir / "val" / "labels"
    
    # 创建目录
    console.print("[yellow]📁 创建YOLO数据集目录结构...[/yellow]")
    for dir_path in [train_images, train_labels, val_images, val_labels]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 从多个数据源收集图片-标注对
    all_image_files = []
    
    for source_name, paths in data_sources.items():
        images_dir = paths["images"]
        labels_dir = paths["labels"]
        
        if not images_dir.exists() or not labels_dir.exists():
            console.print(f"[yellow]⚠️ 数据源 {source_name} 不存在，跳过[/yellow]")
            continue
        
        # 获取此数据源的已标注图片列表
        label_files = list(labels_dir.glob("*.txt"))
        source_image_files = []
        
        for label_file in label_files:
            # 查找对应的图片文件
            image_name = label_file.stem
            for ext in ['.jpg', '.jpeg', '.png']:
                image_path = images_dir / f"{image_name}{ext}"
                if image_path.exists() and image_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    # 存储图片路径和对应的标注路径
                    source_image_files.append({
                        'image_path': image_path,
                        'label_path': label_file,
                        'source': source_name
                    })
                    break
        
        console.print(f"[cyan]📊 {source_name}: 找到{len(source_image_files)}对图片-标注数据[/cyan]")
        all_image_files.extend(source_image_files)
    
    console.print(f"[bold cyan]📊 总计: 找到{len(all_image_files)}对图片-标注数据[/bold cyan]")
    
    if len(all_image_files) < 2:
        console.print("[red]❌ 数据量不足，至少需要2对图片-标注数据[/red]")
        return False
    
    # 数据划分（80%训练，20%验证）
    random.seed(42)  # 固定随机种子，确保可重复
    random.shuffle(all_image_files)
    
    split_idx = int(len(all_image_files) * 0.8)
    train_files = all_image_files[:split_idx]
    val_files = all_image_files[split_idx:]
    
    console.print(f"[cyan]📈 数据划分: {len(train_files)}张训练，{len(val_files)}张验证[/cyan]")
    
    # 复制文件
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # 复制训练集
        task1 = progress.add_task("复制训练集文件...", total=len(train_files))
        for file_info in train_files:
            image_path = file_info['image_path']
            label_path = file_info['label_path']
            
            # 生成唯一的文件名（避免不同数据源的同名文件冲突）
            unique_name = f"{file_info['source']}_{image_path.stem}"
            
            # 复制图片
            shutil.copy2(image_path, train_images / f"{unique_name}{image_path.suffix}")
            
            # 复制对应标注
            shutil.copy2(label_path, train_labels / f"{unique_name}.txt")
            
            progress.advance(task1)
        
        # 复制验证集
        task2 = progress.add_task("复制验证集文件...", total=len(val_files))
        for file_info in val_files:
            image_path = file_info['image_path']
            label_path = file_info['label_path']
            
            # 生成唯一的文件名（避免不同数据源的同名文件冲突）
            unique_name = f"{file_info['source']}_{image_path.stem}"
            
            # 复制图片
            shutil.copy2(image_path, val_images / f"{unique_name}{image_path.suffix}")
            
            # 复制对应标注
            shutil.copy2(label_path, val_labels / f"{unique_name}.txt")
            
            progress.advance(task2)
    
    # 显示统计信息
    table = Table(title="数据集统计")
    table.add_column("数据集", style="cyan", no_wrap=True)
    table.add_column("图片数量", style="magenta")
    table.add_column("标注数量", style="green")
    
    train_img_count = len(list(train_images.glob("*")))
    train_label_count = len(list(train_labels.glob("*.txt")))
    val_img_count = len(list(val_images.glob("*")))
    val_label_count = len(list(val_labels.glob("*.txt")))
    
    table.add_row("训练集", str(train_img_count), str(train_label_count))
    table.add_row("验证集", str(val_img_count), str(val_label_count))
    table.add_row("总计", str(train_img_count + val_img_count), str(train_label_count + val_label_count))
    
    console.print(table)
    console.print("[bold green]✅ YOLO数据集准备完成！[/bold green]")
    
    return True

if __name__ == "__main__":
    prepare_yolo_dataset()