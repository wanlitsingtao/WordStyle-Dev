# -*- coding: utf-8 -*-
"""
转换配置区组件
从 app.py 提取
"""
import streamlit as st

@st.fragment
def render_conversion_config():
    """
    渲染转换配置区（使用fragment优化性能）
    
    优化点：
    1. 使用@st.fragment隔离，避免用户交互导致全局重渲染
    2. 仅在值真正改变时才更新session_state
    3. 预计算索引，避免重复遍历
    """
    
    # 第一行:四个选项横向等距分布
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📊 样式映射", key="open_style_mapping_btn", use_container_width=True, help="如果不采用系统给的默认配置,可自定义样式映射"):
            # 直接调用对话框,不使用session_state标记
            show_style_mapping_dialog()
            # [FIX] 对话框显示后,返回默认值避免解包错误
            return (
                st.session_state.do_mood_config,
                st.session_state.do_answer_config,
                st.session_state.list_bullet_config,
                st.session_state.answer_text_config,
                st.session_state.answer_style_config,
                st.session_state.answer_mode_config
            )

    with col2:
        do_mood = st.checkbox(
            "祈使语气转换", 
            value=st.session_state.do_mood_config, 
            help="将文档中的祈使语气转换为投标人语气",
            key="mood_checkbox"
        )
        # 仅在值改变时更新session_state，避免不必要的重渲染
        if do_mood != st.session_state.get('do_mood_config'):
            st.session_state.do_mood_config = do_mood

    with col3:
        do_answer = st.checkbox(
            "插入应答句", 
            value=st.session_state.do_answer_config, 
            help="在标题后插入应答句",
            key="answer_checkbox"
        )
        # 仅在值改变时更新session_state
        if do_answer != st.session_state.get('do_answer_config'):
            st.session_state.do_answer_config = do_answer

    with col4:
        list_bullet = st.text_input(
            "列表符号", 
            value=st.session_state.list_bullet_config, 
            help="列表段落的符号",
            key="bullet_input"
        )
        # 仅在值改变时更新session_state
        if list_bullet != st.session_state.get('list_bullet_config'):
            st.session_state.list_bullet_config = list_bullet

    # 第二行：应答句详细配置（仅当勾选"插入应答句"时显示）
    if do_answer:
        st.markdown("---")
        st.markdown("**ℹ️ 应答句配置**")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            answer_text = st.text_input(
                "应答句文本",
                value=st.session_state.answer_text_config,
                help="插入的应答句内容",
                key="answer_text_input"
            )
            # 仅在值改变时更新
            if answer_text != st.session_state.get('answer_text_config'):
                st.session_state.answer_text_config = answer_text
        
        with col_b:
            # 获取模板样式列表（使用缓存的引用）
            template_styles = st.session_state.get('template_styles', ["Normal"])
            
            # 预计算index，避免每次渲染都查找
            style_index = 0
            if st.session_state.answer_style_config in template_styles:
                try:
                    style_index = template_styles.index(st.session_state.answer_style_config)
                except ValueError:
                    style_index = 0
            
            answer_style = st.selectbox(
                "应答句样式",
                options=template_styles,
                index=style_index,
                help="应答句的段落样式",
                key="answer_style_select"
            )
            # 实时更新 session_state
            st.session_state.answer_style_config = answer_style
        
        with col_c:
            # 使用缓存的options，保持引用稳定
            answer_mode_options = get_answer_mode_options()
            
            # 预计算mode_keys和index，避免每次渲染都创建新列表
            if 'answer_mode_keys_cache' not in st.session_state:
                st.session_state.answer_mode_keys_cache = list(answer_mode_options.keys())
            mode_keys = st.session_state.answer_mode_keys_cache
            
            # 预计算index
            mode_index = 0
            if st.session_state.answer_mode_config in answer_mode_options:
                try:
                    mode_index = mode_keys.index(st.session_state.answer_mode_config)
                except ValueError:
                    mode_index = 0
            
            answer_mode = st.selectbox(
                "插入模式",
                options=mode_keys,
                format_func=lambda x: answer_mode_options[x],
                index=mode_index,
                help="应答句的插入位置模式",
                key="answer_mode_select"
            )
            # 仅在值改变时更新
            if answer_mode != st.session_state.get('answer_mode_config'):
                st.session_state.answer_mode_config = answer_mode
    else:
        # 未勾选时设置默认值
        answer_text = st.session_state.answer_text_config
        answer_style = st.session_state.answer_style_config
        answer_mode = st.session_state.answer_mode_config
    
    # 返回配置值供后续使用
    return do_mood, do_answer, list_bullet, answer_text, answer_style, answer_mode

# 调用fragment函数渲染配置区
do_mood, do_answer, list_bullet, answer_text, answer_style, answer_mode = render_conversion_config()

# 不插入应答句时使用默认值（确保变量存在）
if not do_answer:
    answer_text = st.session_state.get('answer_text_config', '应答：本投标人理解并满足要求。')
    answer_style = st.session_state.get('answer_style_config', 'Normal')
    answer_mode = st.session_state.get('answer_mode_config', 'before_heading')

# 开始转换按钮
st.markdown("---")

# 检查是否正在前台转换中
is_converting = st.session_state.get('is_converting', False)

if is_converting:
    # 如果正在转换，显示提示信息
    st.warning("⏳ **正在进行前台转换，请稍候...**\n\n转换期间无法进行其他操作，请耐心等待转换完成。")
    st.info("💡 转换完成后将自动恢复操作权限")
else:
    # 正常状态，显示开始转换按钮
    if st.button("🚀 开始转换", type="primary", use_container_width=True):
            # [OK] 提前定义进度条和状态文本（必须在所有使用之前）
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            progress_bar = progress_placeholder.progress(0)
            
            # 验证输入（从session_state中恢复文件变量）
            # [OK] 修复：从session_state获取文件，而不是依赖局部变量（页面刷新后会丢失）
            current_source_files = st.session_state.get('current_source_files', None)
            current_temp_template = st.session_state.get('current_temp_template', None)
                        
            if not current_source_files or not current_temp_template:
                st.error("❌ 请上传源文档和模板文档")
                status_placeholder.text("[ERROR] 验证失败：缺少文件")
                progress_bar.progress(0)
            elif not os.path.exists(current_temp_template):
                st.error("❌ 文件上传失败，请重试")
                status_placeholder.text("[ERROR] 验证失败：文件上传错误")
                progress_bar.progress(0)
            else:
                # 设置转换标志，禁用后续操作
                st.session_state.is_converting = True
                
                # [HIGH_VOLTAGE] 性能优化：立即更新进度条，不要等验证完成
                status_placeholder.text("⏳ 正在验证输入...")
                progress_bar.progress(5)
            
            # [HIGH_VOLTAGE] 性能优化：使用分析阶段已计算的段落数（file_paragraph_counts已在第886-899行计算）
            # 如果file_paragraph_counts不存在（异常情况），使用兜底逻辑
            if 'file_paragraph_counts' in st.session_state and st.session_state.file_paragraph_counts:
                file_paragraph_counts = st.session_state.file_paragraph_counts
                file_info = [(sf.name, file_paragraph_counts[sf.name]) for sf in current_source_files]
                total_paragraphs = sum(file_paragraph_counts.values())
            else:
                # 兜底逻辑：重新计算（不应该发生）
                logger.warning("file_paragraph_counts 不存在，使用兜底逻辑重新计算")
                total_paragraphs = 0
                file_info = []
                for sf in current_source_files:
                    temp_source = f"temp_source_{st.session_state.user_id}_{sf.name}"
                    paragraphs = count_paragraphs(temp_source)
                    total_paragraphs += paragraphs
                    file_info.append((sf.name, paragraphs))
            
            
            progress_bar.progress(10)
            status_placeholder.text("⏳ 准备转换...")
            
            # [HIGH_VOLTAGE] 性能优化：使用缓存的文件信息，避免重复读取
            source_files_info = []
            for fname, fpara in file_info:
                temp_source = f"temp_source_{st.session_state.user_id}_{fname}"
                source_files_info.append((fname, temp_source, fpara))
            
            # 配置字典
            config = {
                'do_mood': do_mood,
                'answer_text': answer_text,
                'answer_style': answer_style,
                'list_bullet': list_bullet if list_bullet else "•",
                'do_answer_insertion': do_answer,
                'answer_mode': answer_mode,
                'custom_style_map': st.session_state.get('style_mapping', None)  # 用户配置的样式映射
            }
                        
            # ========== 前台转换模式 ==========
            # 进度条已在按钮点击时创建
                        
            # 添加"转为后台"按钮（使用session_state标记）
            if 'switch_to_background' not in st.session_state:
                st.session_state.switch_to_background = False
                        
            try:
                # 更新进度提示
                status_placeholder.text("⏳ 正在初始化转换器...")
                progress_bar.progress(10)
                                
                # 创建转换器
                converter = DocumentConverter()
                progress_bar.progress(10)
                
                # 处理每个文件
                output_files = []
                success_count = 0
                fail_count = 0
                total_success_paragraphs = 0  # 成功转换的段落数
                
                # [OK] 初始化文件级结果列表（用于持久化保存）
                st.session_state.conversion_file_results = []
                
                for idx, source_file_obj in enumerate(current_source_files):
                    # 输出文件路径 - 保存到conversion_results目录
                    base_name = os.path.splitext(source_file_obj.name)[0]
                    output_filename = f"result_{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                    output_file = os.path.join("conversion_results", output_filename)
                    temp_source = f"temp_source_{st.session_state.user_id}_{source_file_obj.name}"
                    
                    # [HIGH_VOLTAGE] 性能优化：从缓存中获取段落数，避免重复读取
                    file_paragraphs = 0
                    for fname, fpara in file_info:
                        if fname == source_file_obj.name:
                            file_paragraphs = fpara
                            break
                    
                    status_placeholder.text(f" 正在转换第 {idx+1}/{len(current_source_files)} 个文件: {source_file_obj.name} ({file_paragraphs:,} 段落)")
                    
                    # [OK] 修复：使用每个文件各自的样式映射配置（与桌面版一致）
                    file_mapping = None
                    if 'file_style_mappings' in st.session_state and source_file_obj.name in st.session_state.file_style_mappings:
                        file_mapping = st.session_state.file_style_mappings[source_file_obj.name]
                        if file_mapping:
                            st.info(f"📋 {source_file_obj.name}: 使用自定义样式映射 ({len(file_mapping)} 个样式)")
                    
                    # 警告收集
                    warnings_list = []
                    def warning_callback(msg):
                        warnings_list.append(msg)
                    
                    # 进度回调函数 - 实时更新进度条
                    def make_progress_callback(file_idx, total_files):
                        def callback(step, message):
                            # 计算总体进度 (10% - 80%)
                            base_progress = 10 + int((file_idx / total_files) * 70)
                            step_progress = int((step / 7) * (70 / total_files))
                            current_progress = min(base_progress + step_progress, 80)
                            progress_bar.progress(current_progress)
                            status_placeholder.text(f"⏳ {message}")
                        return callback
                    
                    # [HIGH_VOLTAGE] 性能优化：传递缓存的样式列表，避免重复分析
                    source_styles_for_file = st.session_state.file_styles_map.get(source_file_obj.name, None)
                    
                    # 执行转换
                    success, actual_file, msg = converter.full_convert(
                        source_file=temp_source,
                        template_file=current_temp_template,
                        output_file=output_file,
                        custom_style_map=file_mapping,  # [OK] 修复：使用每个文件各自的映射配置
                        do_mood=do_mood,
                        answer_text=answer_text,
                        answer_style=answer_style,
                        list_bullet=list_bullet if list_bullet else "•",
                        do_answer_insertion=do_answer,
                        answer_mode=answer_mode,
                        progress_callback=make_progress_callback(idx, len(current_source_files)),
                        warning_callback=warning_callback,
                        source_styles_cache=source_styles_for_file  # [HIGH_VOLTAGE] 传递缓存的样式列表
                    )
                    
                    if success:
                        output_files.append(actual_file)
                        success_count += 1
                        total_success_paragraphs += file_paragraphs
                        
                        # [OK] 保存文件级结果到 session_state（防止重渲染后丢失）
                        st.session_state.conversion_file_results.append({
                            'name': source_file_obj.name,
                            'status': 'success',
                            'paragraphs': file_paragraphs,
                            'warnings': warnings_list.copy()  # 复制列表，避免后续修改影响
                        })
                    else:
                        fail_count += 1
                        
                        # [OK] 保存文件级失败结果到 session_state
                        st.session_state.conversion_file_results.append({
                            'name': source_file_obj.name,
                            'status': 'fail',
                            'msg': msg
                        })
                
                progress_bar.progress(90)
                
                if success_count > 0:
                    progress_bar.progress(100)
                    
                    # [OK] 扣除段落脚额（只扣段落数，不涉及费用）
                    if user_data['paragraphs_remaining'] >= total_success_paragraphs:
                        user_data['paragraphs_remaining'] -= total_success_paragraphs
                    else:
                        # 如果余额不足，只扣除剩余部分，最低为0
                        user_data['paragraphs_remaining'] = 0
                    
                    # 更新用户统计
                    user_data['total_converted'] += success_count
                    user_data['total_paragraphs_used'] += total_success_paragraphs
                    
                    # 记录转换历史（不包含费用）
                    conversion_record = {
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'files': len(current_source_files),
                        'success': success_count,
                        'failed': fail_count,
                        'paragraphs_charged': total_success_paragraphs,
                        'mode': 'foreground'
                    }
                    
                    # [OK] 防御性编程：确保conversion_history字段存在
                    if 'conversion_history' not in user_data:
                        user_data['conversion_history'] = []
                    
                    user_data['conversion_history'].append(conversion_record)
                    
                    # [OK] 修复：调用add_conversion_record写入conversion_tasks表（API模式）
                    from data_manager import add_conversion_record
                    add_conversion_record(
                        files_count=len(current_source_files),
                        success_count=success_count,
                        failed_count=fail_count,
                        user_id=st.session_state.user_id,
                        paragraphs=total_success_paragraphs  # [OK] 新增：传递段落数
                    )
                    
                    # 保存用户数据（使用统一数据接口）
                    from data_manager import save_user_data
                    save_user_data(user_data, st.session_state.user_id)
                    
                    # [OK] 修复：将转换结果文件路径保存到 session_state，防止刷新后丢失
                    if 'recent_results' not in st.session_state:
                        st.session_state.recent_results = []
                    
                    # 添加本次转换的结果文件
                    for output_file in output_files:
                        if os.path.exists(output_file):
                            file_info = {
                                'path': output_file,
                                'name': os.path.basename(output_file),
                                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            st.session_state.recent_results.append(file_info)
                    
                    # 重置转换标志
                    st.session_state.is_converting = False
                    
                    # [OK] 保存转换总结信息到session_state（在下载区域统一显示，防止重复）
                    st.session_state.conversion_summary = {
                        'success_count': success_count,
                        'fail_count': fail_count,
                        'total_paragraphs': total_success_paragraphs
                    }
                    
                    # [OK] 清理临时文件（源文件和模板文件）
                    try:
                        from file_manager import get_file_manager
                        fm = get_file_manager()
                        cleanup_stats = fm.cleanup_temp_files(st.session_state.user_id)
                        logger.info(f"临时文件清理完成: {cleanup_stats}")
                    except Exception as cleanup_error:
                        logger.warning(f"临时文件清理失败（不影响转换结果）: {cleanup_error}")
                    
                    # [OK] 标记显示下载按钮（用于页面刷新后保持状态）
                    st.session_state.show_download_buttons = True
                    
                    # [OK] 强制重新渲染，避免在同一轮渲染中重复显示转换总结
                    st.rerun()
                else:
                    # 所有文件都转换失败
                    status_placeholder.text("[ERROR] 转换失败！")
                    progress_bar.progress(100)
                    st.session_state.is_converting = False
                    st.error("❌ 所有文件转换失败，请检查错误信息")
                    st.info("💡 请查看上方的错误提示，修正后重试")
        
            except Exception as e:
                # 重置转换标志
                st.session_state.is_converting = False
                
                st.error(f"发生错误: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

# [OK] 转换完成后显示下载按钮和转换总结信息（在按钮之后，从session_state读取）
if 'show_download_buttons' in st.session_state and st.session_state.show_download_buttons:
    # [OK] 显示转换总结信息（从session_state读取，防止刷新后丢失）
    if 'conversion_summary' in st.session_state and st.session_state.conversion_summary:
        summary = st.session_state.conversion_summary
        st.success(f"🎉 转换完成！成功: {summary['success_count']} 个，失败: {summary['fail_count']} 个")
        if summary['fail_count'] > 0:
            st.warning(f"⚠️ 有 {summary['fail_count']} 个文件转换失败")
        st.info(f"处理 {summary['total_paragraphs']:,} 个段落")
    
    # [OK] 恢复每个文件的转换结果（从 session_state 读取，防止重渲染后丢失）
    if 'conversion_file_results' in st.session_state:
        for result in st.session_state.conversion_file_results:
            if result['status'] == 'success':
                st.success(f"✅ {result['name']} 转换成功")
                # 显示警告信息（如果有）
                if result.get('warnings'):
                    with st.expander(f"⚠️ {result['name']} 的警告信息"):
                        for w in result['warnings']:
                            st.warning(w)
            else:
                st.error(f"❌ {result['name']} 转换失败: {result.get('msg', '')}")
    
    st.subheader("📥 下载转换结果")
    
    # 显示所有转换结果文件
    if 'recent_results' in st.session_state and st.session_state.recent_results:
        for idx, file_info in enumerate(st.session_state.recent_results):
            if os.path.exists(file_info['path']):
                with open(file_info['path'], 'rb') as f:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.download_button(
                            label=f"[DOWNLOAD] 下载: {file_info['name']}",
                            data=f.read(),
                            file_name=file_info['name'],
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key=f"download_recent_{file_info['name']}"
                        )
                    with col2:
                        st.caption(f"转换时间: {file_info['time']}")
            else:
                st.warning(f"⚠️ 文件已过期或不存在: {file_info['name']}")
    
    st.markdown("---")

