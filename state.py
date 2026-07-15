# -*- coding: utf-8 -*-
"""
统一状态管理器
封装所有 st.session_state 操作，提供类型安全的访问接口

优化点：
1. 集中管理所有 session_state 键（当前 33 个）
2. 提供类型安全的 getter/setter
3. 避免魔法字符串分散在代码中
4. 便于后续添加默认值和验证逻辑
"""
import streamlit as st
from typing import Optional, List, Dict, Any


class AppState:
    """应用状态管理器 - 统一管理所有 session_state"""
    
    # ==================== 用户相关 ====================
    
    @staticmethod
    def get_user_id() -> str:
        """获取当前用户ID"""
        return st.session_state.get('user_id', '')
    
    @staticmethod
    def set_user_id(user_id: str):
        """设置当前用户ID"""
        st.session_state.user_id = user_id
    
    @staticmethod
    def get_device_fingerprint() -> Optional[str]:
        """获取设备指纹"""
        return st.session_state.get('device_fingerprint')
    
    @staticmethod
    def set_device_fingerprint(fingerprint: str):
        """设置设备指纹"""
        st.session_state.device_fingerprint = fingerprint
    
    @staticmethod
    def is_user_init_failed() -> bool:
        """检查用户初始化是否失败"""
        return st.session_state.get('user_init_failed', False)
    
    @staticmethod
    def set_user_init_failed(failed: bool):
        """设置用户初始化失败标志"""
        st.session_state.user_init_failed = failed
    
    # ==================== 文件上传相关 ====================
    
    @staticmethod
    def get_source_files_uploaded() -> bool:
        """检查源文件是否已上传"""
        return st.session_state.get('source_files_uploaded', False)
    
    @staticmethod
    def set_source_files_uploaded(uploaded: bool):
        """设置源文件上传状态"""
        st.session_state.source_files_uploaded = uploaded
    
    @staticmethod
    def get_template_file_uploaded() -> bool:
        """检查模板文件是否已上传"""
        return st.session_state.get('template_file_uploaded', False)
    
    @staticmethod
    def set_template_file_uploaded(uploaded: bool):
        """设置模板文件上传状态"""
        st.session_state.template_file_uploaded = uploaded
    
    @staticmethod
    def get_current_source_files() -> List[Any]:
        """获取当前源文件列表"""
        return st.session_state.get('current_source_files', [])
    
    @staticmethod
    def set_current_source_files(files: List[Any]):
        """设置当前源文件列表"""
        st.session_state.current_source_files = files
    
    @staticmethod
    def get_current_temp_template() -> Optional[str]:
        """获取当前临时模板路径"""
        return st.session_state.get('current_temp_template')
    
    @staticmethod
    def set_current_temp_template(path: str):
        """设置当前临时模板路径"""
        st.session_state.current_temp_template = path
    
    @staticmethod
    def get_last_template_name() -> Optional[str]:
        """获取上次使用的模板名称"""
        return st.session_state.get('last_template_name')
    
    @staticmethod
    def set_last_template_name(name: str):
        """设置上次使用的模板名称"""
        st.session_state.last_template_name = name
    
    # ==================== 样式分析相关 ====================
    
    @staticmethod
    def get_source_styles() -> Optional[Dict]:
        """获取源文档样式映射"""
        return st.session_state.get('source_styles')
    
    @staticmethod
    def set_source_styles(styles: Dict):
        """设置源文档样式映射"""
        st.session_state.source_styles = styles
    
    @staticmethod
    def get_template_styles() -> Optional[Dict]:
        """获取模板文档样式映射"""
        return st.session_state.get('template_styles')
    
    @staticmethod
    def set_template_styles(styles: Dict):
        """设置模板文档样式映射"""
        st.session_state.template_styles = styles
    
    @staticmethod
    def get_file_styles_map() -> Optional[Dict]:
        """获取文件样式映射"""
        return st.session_state.get('file_styles_map')
    
    @staticmethod
    def set_file_styles_map(styles_map: Dict):
        """设置文件样式映射"""
        st.session_state.file_styles_map = styles_map
    
    @staticmethod
    def get_file_style_mappings() -> Optional[Dict]:
        """获取文件样式映射配置"""
        return st.session_state.get('file_style_mappings')
    
    @staticmethod
    def set_file_style_mappings(mappings: Dict):
        """设置文件样式映射配置"""
        st.session_state.file_style_mappings = mappings
    
    @staticmethod
    def get_file_paragraph_counts() -> Optional[Dict]:
        """获取文件段落数统计"""
        return st.session_state.get('file_paragraph_counts')
    
    @staticmethod
    def set_file_paragraph_counts(counts: Dict):
        """设置文件段落数统计"""
        st.session_state.file_paragraph_counts = counts
    
    # ==================== 转换配置相关 ====================
    
    @staticmethod
    def get_do_mood_config() -> bool:
        """获取语气转换配置"""
        return st.session_state.get('do_mood_config', True)
    
    @staticmethod
    def set_do_mood_config(enabled: bool):
        """设置语气转换配置"""
        st.session_state.do_mood_config = enabled
    
    
    @staticmethod
    def get_do_answer_config() -> bool:
        """获取应答句插入配置"""
        return st.session_state.get('do_answer_config', True)
    
    @staticmethod
    def set_do_answer_config(enabled: bool):
        """设置应答句插入配置"""
        st.session_state.do_answer_config = enabled
    
    
    @staticmethod
    def get_answer_mode_config() -> str:
        """获取应答句插入模式"""
        return st.session_state.get('answer_mode_config', 'before_heading')
    
    @staticmethod
    def set_answer_mode_config(mode: str):
        """设置应答句插入模式"""
        st.session_state.answer_mode_config = mode
    
    @staticmethod
    def get_answer_text_config() -> str:
        """获取应答句文本配置"""
        return st.session_state.get('answer_text_config', '')
    
    @staticmethod
    def set_answer_text_config(text: str):
        """设置应答句文本配置"""
        st.session_state.answer_text_config = text
    
    @staticmethod
    def get_answer_style_config() -> str:
        """获取应答句样式配置"""
        return st.session_state.get('answer_style_config', '正文')
    
    @staticmethod
    def set_answer_style_config(style: str):
        """设置应答句样式配置"""
        st.session_state.answer_style_config = style
    
    # ========== 章节提示语配置 ==========
    
    @staticmethod
    def get_do_hint_config() -> bool:
        """获取是否插入章节提示语"""
        return st.session_state.get('do_hint_config', False)
    
    @staticmethod
    def set_do_hint_config(enabled: bool):
        """设置是否插入章节提示语"""
        st.session_state.do_hint_config = enabled
    
    @staticmethod
    def get_hint_type_config() -> str:
        """获取提示语类型"""
        return st.session_state.get('hint_type_config', 'text')
    
    @staticmethod
    def set_hint_type_config(type_: str):
        """设置提示语类型"""
        st.session_state.hint_type_config = type_
    
    @staticmethod
    def get_hint_text_config() -> str:
        """获取提示语文本"""
        return st.session_state.get('hint_text_config', '招标文件原文')
    
    @staticmethod
    def set_hint_text_config(text: str):
        """设置提示语文本"""
        st.session_state.hint_text_config = text
    
    @staticmethod
    def get_hint_image_config() -> str:
        """获取提示语图片路径"""
        return st.session_state.get('hint_image_config', None)
    
    @staticmethod
    def set_hint_image_config(path: str):
        """设置提示语图片路径"""
        st.session_state.hint_image_config = path
    
    @staticmethod
    def get_hint_style_config() -> str:
        """获取提示语样式"""
        return st.session_state.get('hint_style_config', 'Normal')
    
    @staticmethod
    def set_hint_style_config(style: str):
        """设置提示语样式"""
        st.session_state.hint_style_config = style
    
    # ==================== 表格/图片样式配置 ====================
    
    @staticmethod
    def get_enable_table_style_config() -> bool:
        """获取是否启用表格样式覆盖"""
        return st.session_state.get('enable_table_style_config', False)
    
    @staticmethod
    def set_enable_table_style_config(enabled: bool):
        """设置是否启用表格样式覆盖"""
        st.session_state.enable_table_style_config = enabled
    
    @staticmethod
    def get_table_style_config() -> str:
        """获取表格样式配置"""
        return st.session_state.get('table_style_config', 'Body Text')
    
    @staticmethod
    def set_table_style_config(style: str):
        """设置表格样式配置"""
        st.session_state.table_style_config = style
    
    @staticmethod
    def get_enable_image_style_config() -> bool:
        """获取是否启用图片样式覆盖"""
        return st.session_state.get('enable_image_style_config', False)
    
    @staticmethod
    def set_enable_image_style_config(enabled: bool):
        """设置是否启用图片样式覆盖"""
        st.session_state.enable_image_style_config = enabled
    
    @staticmethod
    def get_image_style_config() -> str:
        """获取图片样式配置"""
        return st.session_state.get('image_style_config', 'Body Text')
    
    @staticmethod
    def set_image_style_config(style: str):
        """设置图片样式配置"""
        st.session_state.image_style_config = style
    
    @staticmethod
    def get_answer_mode_keys_cache() -> List[str]:
        """获取应答模式缓存键"""
        return st.session_state.get('answer_mode_keys_cache', [])
    
    @staticmethod
    def set_answer_mode_keys_cache(keys: List[str]):
        """设置应答模式缓存键"""
        st.session_state.answer_mode_keys_cache = keys
    
    @staticmethod
    def get_list_bullet_config() -> str:
        """获取列表符号配置"""
        return st.session_state.get('list_bullet_config', '•')
    
    @staticmethod
    def set_list_bullet_config(bullet: str):
        """设置列表符号配置"""
        st.session_state.list_bullet_config = bullet
    
    # ==================== 转换执行相关 ====================
    
    @staticmethod
    def get_is_converting() -> bool:
        """检查是否正在转换"""
        return st.session_state.get('is_converting', False)
    
    @staticmethod
    def set_is_converting(converting: bool):
        """设置转换状态"""
        st.session_state.is_converting = converting
    
    @staticmethod
    def get_switch_to_background() -> bool:
        """检查是否切换到后台"""
        return st.session_state.get('switch_to_background', False)
    
    @staticmethod
    def set_switch_to_background(background: bool):
        """设置后台切换状态"""
        st.session_state.switch_to_background = background
    
    @staticmethod
    def get_conversion_summary() -> Optional[Dict]:
        """获取转换摘要"""
        return st.session_state.get('conversion_summary')
    
    @staticmethod
    def set_conversion_summary(summary: Dict):
        """设置转换摘要"""
        st.session_state.conversion_summary = summary
    
    @staticmethod
    def get_conversion_file_results() -> Optional[List[Dict]]:
        """获取转换文件结果"""
        return st.session_state.get('conversion_file_results')
    
    @staticmethod
    def set_conversion_file_results(results: List[Dict]):
        """设置转换文件结果"""
        st.session_state.conversion_file_results = results
    
    @staticmethod
    def get_recent_results() -> Optional[List[Dict]]:
        """获取最近的转换结果"""
        return st.session_state.get('recent_results')
    
    @staticmethod
    def set_recent_results(results: List[Dict]):
        """设置最近的转换结果"""
        st.session_state.recent_results = results
    
    @staticmethod
    def get_show_download_buttons() -> bool:
        """检查是否显示下载按钮"""
        return st.session_state.get('show_download_buttons', False)
    
    @staticmethod
    def set_show_download_buttons(show: bool):
        """设置下载按钮显示状态"""
        st.session_state.show_download_buttons = show
    
    # ==================== 进度条相关 ====================
    
    @staticmethod
    def get_progress_update() -> Optional[Dict]:
        """获取进度更新信息"""
        return st.session_state.get('_progress_update')
    
    @staticmethod
    def set_progress_update(update: Dict):
        """设置进度更新信息"""
        st.session_state._progress_update = update
    
    # ==================== 免费额度相关 ====================
    
    @staticmethod
    def get_free_paragraphs_claimed() -> bool:
        """检查是否已领取免费段落"""
        return st.session_state.get('free_paragraphs_claimed', False)
    
    @staticmethod
    def set_free_paragraphs_claimed(claimed: bool):
        """设置免费段落领取状态"""
        st.session_state.free_paragraphs_claimed = claimed
    
    @staticmethod
    def get_free_claimed_today() -> bool:
        """检查今日是否已领取免费额度"""
        return st.session_state.get('free_claimed_today', False)
    
    @staticmethod
    def set_free_claimed_today(claimed: bool):
        """设置今日免费额度领取状态"""
        st.session_state.free_claimed_today = claimed
    
    # ==================== 反馈表单相关 ====================
    
    @staticmethod
    def get_feedback_form_reset() -> int:
        """获取反馈表单重置计数器"""
        return st.session_state.get('feedback_form_reset', 0)
    
    @staticmethod
    def set_feedback_form_reset(value: int):
        """设置反馈表单重置计数器"""
        st.session_state.feedback_form_reset = value
    
    @staticmethod
    def increment_feedback_form_reset():
        """递增反馈表单重置计数器"""
        st.session_state.feedback_form_reset = st.session_state.get('feedback_form_reset', 0) + 1
    
    @staticmethod
    def reset_feedback_form():
        """重置反馈表单"""
        st.session_state.feedback_form_reset = 0
    
    # ==================== 评论相关 ====================
    
    @staticmethod
    def get_comment_refresh_needed() -> bool:
        """检查是否需要刷新评论"""
        return st.session_state.get('comment_refresh_needed', False)
    
    @staticmethod
    def set_comment_refresh_needed(refresh: bool):
        """设置评论刷新标志"""
        st.session_state.comment_refresh_needed = refresh
    
    # ==================== 引导相关 ====================
    
    @staticmethod
    def get_has_seen_guide() -> bool:
        """检查是否已看过引导"""
        return st.session_state.get('has_seen_guide', False)
    
    @staticmethod
    def set_has_seen_guide(seen: bool):
        """设置引导查看状态"""
        st.session_state.has_seen_guide = seen
    
    # ==================== 工具方法 ====================
    
    @staticmethod
    def initialize_all_defaults():
        """初始化所有默认值（在应用启动时调用）"""
        defaults = {
            'user_id': '',
            'device_fingerprint': None,
            'user_init_failed': False,
            'source_files_uploaded': False,
            'template_file_uploaded': False,
            'current_source_files': [],
            'current_temp_template': None,
            'last_template_name': None,
            'source_styles': None,
            'template_styles': None,
            'file_styles_map': None,
            'file_style_mappings': None,
            'file_paragraph_counts': None,
            'do_mood_config': True,
            'answer_mode_config': 'before_heading',
            'answer_text_config': '',
            'answer_style_config': '正文',
            'answer_mode_keys_cache': [],
            'list_bullet_config': '•',
            'do_hint_config': False,
            'hint_type_config': 'text',
            'hint_text_config': '招标文件原文',
            'hint_image_config': None,
            'hint_style_config': 'Normal',
            'enable_table_style_config': False,
            'table_style_config': 'Body Text',
            'enable_image_style_config': False,
            'image_style_config': 'Body Text',
            'is_converting': False,
            'switch_to_background': False,
            'conversion_summary': None,
            'conversion_file_results': None,
            'recent_results': None,
            'show_download_buttons': False,
            '_progress_update': None,
            'free_paragraphs_claimed': False,
            'free_claimed_today': False,
            'feedback_form_reset': 0,
            'comment_refresh_needed': False,
            'has_seen_guide': False,
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def delete_key(key: str):
        """删除指定的 session_state 键（如果存在）"""
        if key in st.session_state:
            del st.session_state[key]
    
    @staticmethod
    def clear_conversion_state():
        """清除转换相关状态（在重新上传文件时调用）"""
        keys_to_clear = [
            'source_styles',
            'template_styles',
            'file_styles_map',
            'file_style_mappings',
            'file_paragraph_counts',
            'conversion_summary',
            'conversion_file_results',
            'recent_results',
            'show_download_buttons',
            '_progress_update',
        ]
        
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]


# 导出便捷实例
app_state = AppState()
