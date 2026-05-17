# -*- coding: utf-8 -*-
"""
文件清理工具模块
负责清理临时文件和过期的转换结果文件
"""
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class FileManager:
    """文件管理器 - 处理文件清理和查询"""
    
    def __init__(self, base_dir: str = ".", results_dir: str = "conversion_results"):
        """
        初始化文件管理器
        
        Args:
            base_dir: 基础目录（工作目录）
            results_dir: 转换结果目录
        """
        self.base_dir = Path(base_dir)
        self.results_dir = self.base_dir / results_dir
        
        # 确保结果目录存在
        self.results_dir.mkdir(exist_ok=True)
        
        # 文件保留天数
        self.retention_days = 7
    
    def cleanup_temp_files(self, user_id: str = None) -> Dict[str, int]:
        """
        清理临时文件
        
        Args:
            user_id: 用户ID，如果提供则只清理该用户的临时文件
            
        Returns:
            清理统计信息
        """
        stats = {
            'source_files': 0,
            'template_files': 0,
            'failed': 0
        }
        
        try:
            # 清理源文件 temp_source_{user_id}_*
            pattern = f"temp_source_{user_id}_*" if user_id else "temp_source_*"
            for file_path in self.base_dir.glob(pattern):
                try:
                    file_path.unlink()
                    stats['source_files'] += 1
                    logger.debug(f"已删除临时源文件: {file_path.name}")
                except Exception as e:
                    logger.error(f"删除临时源文件失败 {file_path}: {e}")
                    stats['failed'] += 1
            
            # 清理模板文件 temp_template_{user_id}.docx
            pattern = f"temp_template_{user_id}.docx" if user_id else "temp_template_*.docx"
            for file_path in self.base_dir.glob(pattern):
                try:
                    file_path.unlink()
                    stats['template_files'] += 1
                    logger.debug(f"已删除临时模板文件: {file_path.name}")
                except Exception as e:
                    logger.error(f"删除临时模板文件失败 {file_path}: {e}")
                    stats['failed'] += 1
                    
        except Exception as e:
            logger.error(f"清理临时文件时出错: {e}")
        
        return stats
    
    def cleanup_expired_results(self, retention_days: int = None) -> Dict[str, int]:
        """
        清理过期的转换结果文件
        
        Args:
            retention_days: 保留天数，默认使用实例配置
            
        Returns:
            清理统计信息
        """
        if retention_days is None:
            retention_days = self.retention_days
        
        stats = {
            'cleaned': 0,
            'failed': 0,
            'total_size_mb': 0.0
        }
        
        try:
            if not self.results_dir.exists():
                logger.warning(f"结果目录不存在: {self.results_dir}")
                return stats
            
            now = time.time()
            cutoff_time = now - (retention_days * 24 * 3600)
            
            for file_path in self.results_dir.glob("*.docx"):
                try:
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        stats['cleaned'] += 1
                        stats['total_size_mb'] += file_size / (1024 * 1024)
                        logger.info(f"已删除过期结果文件: {file_path.name} ({file_size/1024:.1f}KB)")
                except Exception as e:
                    logger.error(f"删除结果文件失败 {file_path}: {e}")
                    stats['failed'] += 1
                    
        except Exception as e:
            logger.error(f"清理过期结果文件时出错: {e}")
        
        if stats['cleaned'] > 0:
            logger.info(f"清理完成: 删除{stats['cleaned']}个文件, 释放{stats['total_size_mb']:.2f}MB空间")
        
        return stats
    
    def get_file_list(self, page: int = 1, page_size: int = 50) -> Dict:
        """
        获取文件列表（用于管理页面）
        
        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            
        Returns:
            包含文件列表和分页信息的字典
        """
        files = []
        
        try:
            # 扫描临时文件（源文件）
            for file_path in self.base_dir.glob("temp_source_*"):
                stat = file_path.stat()
                files.append({
                    'file_id': f"source_{file_path.name}",
                    'user_id': self._extract_user_id(file_path.name, 'temp_source_'),
                    'filename': file_path.name,
                    'file_type': '源文件',
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'size_bytes': stat.st_size,
                    'size_kb': round(stat.st_size / 1024, 2),
                    'is_expired': False,  # 临时文件应立即清理，不过期
                    'path': str(file_path)
                })
            
            # 扫描临时文件（模板文件）
            for file_path in self.base_dir.glob("temp_template_*.docx"):
                stat = file_path.stat()
                files.append({
                    'file_id': f"template_{file_path.name}",
                    'user_id': self._extract_user_id(file_path.name, 'temp_template_'),
                    'filename': file_path.name,
                    'file_type': '模板文件',
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'size_bytes': stat.st_size,
                    'size_kb': round(stat.st_size / 1024, 2),
                    'is_expired': False,
                    'path': str(file_path)
                })
            
            # 扫描转换结果文件
            if self.results_dir.exists():
                now = time.time()
                cutoff_time = now - (self.retention_days * 24 * 3600)
                
                for file_path in self.results_dir.glob("*.docx"):
                    stat = file_path.stat()
                    file_age_days = (now - stat.st_mtime) / (24 * 3600)
                    
                    files.append({
                        'file_id': f"result_{file_path.name}",
                        'user_id': self._extract_user_id_from_result(file_path.name),
                        'filename': file_path.name,
                        'file_type': '转换结果',
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'size_bytes': stat.st_size,
                        'size_kb': round(stat.st_size / 1024, 2),
                        'is_expired': stat.st_mtime < cutoff_time,
                        'age_days': round(file_age_days, 1),
                        'path': str(file_path)
                    })
            
        except Exception as e:
            logger.error(f"获取文件列表时出错: {e}")
        
        # 按创建时间排序（最新的在前）
        files.sort(key=lambda x: x['created_at'], reverse=True)
        
        # 分页
        total_count = len(files)
        total_pages = (total_count + page_size - 1) // page_size
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_files = files[start_idx:end_idx]
        
        return {
            'files': page_files,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
    
    def delete_files(self, file_ids: List[str]) -> Dict[str, int]:
        """
        删除指定的文件
        
        Args:
            file_ids: 文件ID列表
            
        Returns:
            删除统计信息
        """
        stats = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for file_id in file_ids:
            try:
                # 解析文件路径
                if file_id.startswith('source_'):
                    filename = file_id.replace('source_', '', 1)
                    file_path = self.base_dir / filename
                elif file_id.startswith('template_'):
                    filename = file_id.replace('template_', '', 1)
                    file_path = self.base_dir / filename
                elif file_id.startswith('result_'):
                    filename = file_id.replace('result_', '', 1)
                    file_path = self.results_dir / filename
                else:
                    stats['failed'] += 1
                    stats['errors'].append(f"未知的文件ID格式: {file_id}")
                    continue
                
                # 删除文件
                if file_path.exists():
                    file_path.unlink()
                    stats['success'] += 1
                    logger.info(f"已删除文件: {file_path.name}")
                else:
                    stats['failed'] += 1
                    stats['errors'].append(f"文件不存在: {file_id}")
                    
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"删除失败 {file_id}: {str(e)}")
                logger.error(f"删除文件失败 {file_id}: {e}")
        
        return stats
    
    def cleanup_all_expired(self) -> Dict[str, int]:
        """
        清理所有过期文件（包括临时文件和结果文件）
        
        Returns:
            清理统计信息
        """
        total_stats = {
            'temp_source': 0,
            'temp_template': 0,
            'results': 0,
            'failed': 0
        }
        
        # 清理所有临时文件（不限制用户）
        temp_stats = self.cleanup_temp_files()
        total_stats['temp_source'] = temp_stats['source_files']
        total_stats['temp_template'] = temp_stats['template_files']
        total_stats['failed'] += temp_stats['failed']
        
        # 清理过期结果文件
        result_stats = self.cleanup_expired_results()
        total_stats['results'] = result_stats['cleaned']
        total_stats['failed'] += result_stats['failed']
        
        return total_stats
    
    def _extract_user_id(self, filename: str, prefix: str) -> str:
        """从文件名提取用户ID"""
        try:
            # temp_source_{user_id}_{filename}
            # temp_template_{user_id}.docx
            name_without_prefix = filename.replace(prefix, '', 1)
            if '_' in name_without_prefix:
                return name_without_prefix.split('_')[0]
            elif '.' in name_without_prefix:
                return name_without_prefix.split('.')[0]
            return "unknown"
        except:
            return "unknown"
    
    def _extract_user_id_from_result(self, filename: str) -> str:
        """从结果文件名提取用户ID（如果有的话）"""
        # result_{basename}_{timestamp}.docx
        # 这个格式中没有直接的用户ID，返回unknown
        return "unknown"
    
    def get_storage_stats(self) -> Dict:
        """
        获取存储空间统计信息
        
        Returns:
            存储统计信息
        """
        stats = {
            'temp_source_count': 0,
            'temp_source_size_mb': 0.0,
            'temp_template_count': 0,
            'temp_template_size_mb': 0.0,
            'results_count': 0,
            'results_size_mb': 0.0,
            'expired_results_count': 0,
            'total_size_mb': 0.0
        }
        
        try:
            # 统计临时源文件
            for file_path in self.base_dir.glob("temp_source_*"):
                stats['temp_source_count'] += 1
                stats['temp_source_size_mb'] += file_path.stat().st_size / (1024 * 1024)
            
            # 统计临时模板文件
            for file_path in self.base_dir.glob("temp_template_*.docx"):
                stats['temp_template_count'] += 1
                stats['temp_template_size_mb'] += file_path.stat().st_size / (1024 * 1024)
            
            # 统计结果文件
            if self.results_dir.exists():
                now = time.time()
                cutoff_time = now - (self.retention_days * 24 * 3600)
                
                for file_path in self.results_dir.glob("*.docx"):
                    stats['results_count'] += 1
                    file_size = file_path.stat().st_size
                    stats['results_size_mb'] += file_size / (1024 * 1024)
                    
                    if file_path.stat().st_mtime < cutoff_time:
                        stats['expired_results_count'] += 1
            
            stats['total_size_mb'] = (
                stats['temp_source_size_mb'] + 
                stats['temp_template_size_mb'] + 
                stats['results_size_mb']
            )
            
        except Exception as e:
            logger.error(f"获取存储统计时出错: {e}")
        
        # 四舍五入到2位小数
        for key in stats:
            if isinstance(stats[key], float):
                stats[key] = round(stats[key], 2)
        
        return stats


# 全局文件管理器实例
_file_manager = None


def get_file_manager() -> FileManager:
    """获取全局文件管理器实例"""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager()
    return _file_manager


def cleanup_on_startup():
    """服务启动时清理过期文件"""
    logger.info("开始执行启动时文件清理...")
    fm = get_file_manager()
    stats = fm.cleanup_all_expired()
    logger.info(f"启动清理完成: {stats}")


def schedule_daily_cleanup():
    """
    安排每日清理任务
    注意：这需要配合APScheduler或其他定时任务框架使用
    这里只提供清理逻辑，实际调度需要在主应用中配置
    """
    logger.info("执行每日定时文件清理...")
    fm = get_file_manager()
    stats = fm.cleanup_all_expired()
    logger.info(f"每日清理完成: {stats}")
    return stats
