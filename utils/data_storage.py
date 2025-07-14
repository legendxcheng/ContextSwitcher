"""
数据持久化模块

负责任务数据的保存和加载:
- JSON格式数据存储
- 数据备份和恢复
- 配置文件管理
- 数据迁移
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from utils.config import get_config


class DataStorage:
    """数据存储管理器"""
    
    def __init__(self):
        """初始化数据存储"""
        self.config = get_config()
        self.data_dir = self.config.get_data_dir()
        self.tasks_file = self.data_dir / "tasks.json"
        self.backup_dir = self.data_dir / "backups"
        
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 备份设置
        self.max_backups = self.config.get('data.backup_count', 3)
        self.auto_backup = self.config.get('data.auto_save', True)
    
    def save_tasks(self, tasks: List[Any]) -> bool:
        """保存任务列表到文件
        
        Args:
            tasks: 任务对象列表
            
        Returns:
            是否成功保存
        """
        try:
            # 转换为可序列化的格式
            tasks_data = []
            for task in tasks:
                if hasattr(task, 'to_dict'):
                    tasks_data.append(task.to_dict())
                else:
                    # 如果对象没有to_dict方法，尝试直接序列化
                    tasks_data.append(self._serialize_object(task))
            
            # 创建完整的数据结构
            data = {
                "version": "1.1.0",  # 更新版本号以支持Explorer路径信息
                "saved_at": datetime.now().isoformat(),
                "task_count": len(tasks_data),
                "tasks": tasks_data
            }
            
            # 备份现有文件
            if self.auto_backup and self.tasks_file.exists():
                self._create_backup()
            
            # 保存到临时文件，然后重命名（原子操作）
            temp_file = self.tasks_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 原子替换
            shutil.move(str(temp_file), str(self.tasks_file))
            
            print(f"✓ 已保存 {len(tasks_data)} 个任务到 {self.tasks_file}")
            return True
            
        except Exception as e:
            print(f"保存任务失败: {e}")
            # 清理临时文件
            temp_file = self.tasks_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink()
            return False
    
    def load_tasks(self) -> List[Dict[str, Any]]:
        """从文件加载任务列表
        
        Returns:
            任务数据列表，如果加载失败则返回空列表
        """
        try:
            if not self.tasks_file.exists():
                print("任务文件不存在，返回空任务列表")
                return []
            
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证数据格式
            if not isinstance(data, dict):
                raise ValueError("数据格式错误：根对象不是字典")
            
            if "tasks" not in data:
                raise ValueError("数据格式错误：缺少tasks字段")
            
            tasks_data = data["tasks"]
            if not isinstance(tasks_data, list):
                raise ValueError("数据格式错误：tasks不是列表")
            
            # 数据版本检查和迁移
            version = data.get("version", "unknown")
            if version in ["1.0.0", "1.1.0"]:
                # 支持的版本，正常加载
                pass
            elif version == "unknown":
                print(f"警告: 检测到旧版本数据格式，将自动迁移")
                # 旧版本数据会通过Task.from_dict的向后兼容性处理
            else:
                print(f"警告: 数据版本不匹配 ({version})，尝试向下兼容")
            
            print(f"✓ 已加载 {len(tasks_data)} 个任务")
            return tasks_data
            
        except FileNotFoundError:
            print("任务文件不存在")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            # 尝试从备份恢复
            return self._restore_from_backup()
        except Exception as e:
            print(f"加载任务失败: {e}")
            # 尝试从备份恢复
            return self._restore_from_backup()
    
    def _serialize_object(self, obj: Any) -> Dict[str, Any]:
        """序列化对象为字典"""
        if hasattr(obj, '__dict__'):
            result = {}
            for key, value in obj.__dict__.items():
                if key.startswith('_'):
                    continue  # 跳过私有属性
                
                if hasattr(value, '__dict__'):
                    result[key] = self._serialize_object(value)
                elif isinstance(value, list):
                    result[key] = [self._serialize_object(item) if hasattr(item, '__dict__') 
                                  else item for item in value]
                elif hasattr(value, 'value'):  # 枚举类型
                    result[key] = value.value
                else:
                    result[key] = value
            return result
        else:
            return str(obj)
    
    def _create_backup(self) -> bool:
        """创建当前任务文件的备份"""
        try:
            if not self.tasks_file.exists():
                return True
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"tasks_{timestamp}.json"
            
            shutil.copy2(self.tasks_file, backup_file)
            print(f"✓ 已创建备份: {backup_file.name}")
            
            # 清理旧备份
            self._cleanup_old_backups()
            
            return True
            
        except Exception as e:
            print(f"创建备份失败: {e}")
            return False
    
    def _cleanup_old_backups(self):
        """清理过期的备份文件"""
        try:
            backup_files = list(self.backup_dir.glob("tasks_*.json"))
            
            if len(backup_files) <= self.max_backups:
                return
            
            # 按修改时间排序，删除最旧的文件
            backup_files.sort(key=lambda x: x.stat().st_mtime)
            
            files_to_delete = backup_files[:-self.max_backups]
            for file_path in files_to_delete:
                file_path.unlink()
                print(f"✓ 已删除旧备份: {file_path.name}")
                
        except Exception as e:
            print(f"清理备份失败: {e}")
    
    def _restore_from_backup(self) -> List[Dict[str, Any]]:
        """从最新备份恢复数据"""
        try:
            backup_files = list(self.backup_dir.glob("tasks_*.json"))
            
            if not backup_files:
                print("没有找到备份文件")
                return []
            
            # 找到最新的备份文件
            latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
            print(f"正在从备份恢复: {latest_backup.name}")
            
            with open(latest_backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            tasks_data = data.get("tasks", [])
            print(f"✓ 从备份恢复了 {len(tasks_data)} 个任务")
            
            return tasks_data
            
        except Exception as e:
            print(f"从备份恢复失败: {e}")
            return []
    
    def export_tasks(self, export_path: str, tasks: List[Any]) -> bool:
        """导出任务到指定文件
        
        Args:
            export_path: 导出文件路径
            tasks: 任务列表
            
        Returns:
            是否成功导出
        """
        try:
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换为可序列化的格式
            tasks_data = []
            for task in tasks:
                if hasattr(task, 'to_dict'):
                    tasks_data.append(task.to_dict())
                else:
                    tasks_data.append(self._serialize_object(task))
            
            # 创建导出数据
            export_data = {
                "version": "1.0.0",
                "exported_at": datetime.now().isoformat(),
                "exported_from": "ContextSwitcher",
                "task_count": len(tasks_data),
                "tasks": tasks_data
            }
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ 已导出 {len(tasks_data)} 个任务到 {export_path}")
            return True
            
        except Exception as e:
            print(f"导出任务失败: {e}")
            return False
    
    def import_tasks(self, import_path: str) -> Optional[List[Dict[str, Any]]]:
        """从指定文件导入任务
        
        Args:
            import_path: 导入文件路径
            
        Returns:
            导入的任务数据列表，如果失败则返回None
        """
        try:
            import_file = Path(import_path)
            
            if not import_file.exists():
                print(f"导入文件不存在: {import_path}")
                return None
            
            with open(import_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证数据格式
            if not isinstance(data, dict) or "tasks" not in data:
                raise ValueError("导入文件格式错误")
            
            tasks_data = data["tasks"]
            if not isinstance(tasks_data, list):
                raise ValueError("任务数据格式错误")
            
            print(f"✓ 已导入 {len(tasks_data)} 个任务")
            return tasks_data
            
        except Exception as e:
            print(f"导入任务失败: {e}")
            return None
    
    def get_storage_info(self) -> Dict[str, Any]:
        """获取存储信息"""
        try:
            info = {
                "data_dir": str(self.data_dir),
                "tasks_file": str(self.tasks_file),
                "tasks_file_exists": self.tasks_file.exists(),
                "backup_dir": str(self.backup_dir),
                "max_backups": self.max_backups,
                "auto_backup": self.auto_backup
            }
            
            # 任务文件信息
            if self.tasks_file.exists():
                stat = self.tasks_file.stat()
                info["tasks_file_size"] = stat.st_size
                info["tasks_file_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            # 备份文件信息
            backup_files = list(self.backup_dir.glob("tasks_*.json"))
            info["backup_count"] = len(backup_files)
            
            if backup_files:
                latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
                info["latest_backup"] = latest_backup.name
                info["latest_backup_time"] = datetime.fromtimestamp(
                    latest_backup.stat().st_mtime
                ).isoformat()
            
            return info
            
        except Exception as e:
            print(f"获取存储信息失败: {e}")
            return {"error": str(e)}
    
    def clear_all_data(self) -> bool:
        """清除所有数据（谨慎使用）"""
        try:
            # 先创建最后一次备份
            if self.tasks_file.exists():
                self._create_backup()
            
            # 删除任务文件
            if self.tasks_file.exists():
                self.tasks_file.unlink()
                print("✓ 已删除任务文件")
            
            return True
            
        except Exception as e:
            print(f"清除数据失败: {e}")
            return False