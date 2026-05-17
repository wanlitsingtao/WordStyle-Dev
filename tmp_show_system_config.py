def show_system_config():
    """显示系统配置管理页面（可编辑）"""
    st.title("⚙️ 系统配置")
    st.markdown("---")
    
    # 初始化session_state
    if 'config_refresh' not in st.session_state:
        st.session_state.config_refresh = 0
    
    # 顶部操作按钮
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
    
    with col_btn1:
        if st.button("🔄 刷新配置", use_container_width=True):
            st.session_state.config_refresh += 1
            st.rerun()
    
    with col_btn2:
        if st.button("📥 初始化默认配置", use_container_width=True, type="secondary"):
            from data_manager import init_default_configs
            result = init_default_configs()
            if result.get('success'):
                st.success(f"✅ {result.get('message', '初始化成功')}")
                st.session_state.config_refresh += 1
                st.rerun()
            else:
                st.error(f"❌ {result.get('message', '初始化失败')}")
    
    st.markdown("---")
    
    # 获取所有配置
    try:
        from data_manager import get_all_configs, update_config
        
        configs_response = get_all_configs()
        
        if not configs_response.get('success'):
            st.warning("⚠️ 无法加载配置数据")
            st.info("💡 提示：请确保后端服务正常运行，或切换到Supabase模式")
            return
        
        configs_data = configs_response.get('data', [])
        
        # 将配置列表转换为字典
        configs_dict = {}
        for config in configs_data:
            configs_dict[config['config_key']] = config
        
        if not configs_dict:
            st.info("📭 暂无配置项，点击"初始化默认配置"按钮创建默认配置")
            return
        
        # ==================== 计费配置 ====================
        with st.expander("💰 计费配置", expanded=True):
            st.markdown("**段落单价和充值相关配置**")
            
            # 段落单价
            paragraph_price_config = configs_dict.get('paragraph_price', {})
            paragraph_price = st.number_input(
                "段落单价（元/段）",
                value=float(paragraph_price_config.get('config_value', '0.001')),
                min_value=0.0001,
                step=0.0001,
                format="%.4f",
                key="input_paragraph_price"
            )
            
            # 最低充值
            min_recharge_config = configs_dict.get('min_recharge', {})
            min_recharge = st.number_input(
                "最低充值金额（元）",
                value=float(min_recharge_config.get('config_value', '1.0')),
                min_value=0.1,
                step=0.1,
                format="%.1f",
                key="input_min_recharge"
            )
            
            col_save1, col_info1 = st.columns([1, 4])
            with col_save1:
                if st.button("💾 保存计费配置", key="save_billing", use_container_width=True):
                    try:
                        result1 = update_config('paragraph_price', str(paragraph_price))
                        result2 = update_config('min_recharge', str(min_recharge))
                        
                        if result1.get('success') and result2.get('success'):
                            st.success("✅ 计费配置已保存")
                            st.session_state.config_refresh += 1
                            st.rerun()
                        else:
                            st.error("❌ 保存失败")
                    except Exception as e:
                        st.error(f"❌ 保存失败: {str(e)}")
            
            with col_info1:
                st.caption(f"最后更新: {paragraph_price_config.get('updated_at', 'N/A')}")
        
        # ==================== 免费额度 ====================
        with st.expander("🎁 免费额度配置", expanded=True):
            st.markdown("**用户每日免费转换段落数**")
            
            free_paragraphs_config = configs_dict.get('free_paragraphs_daily', {})
            free_paragraphs = st.number_input(
                "每日免费段落数",
                value=int(free_paragraphs_config.get('config_value', '10000')),
                min_value=0,
                step=100,
                key="input_free_paragraphs"
            )
            
            col_save2, col_info2 = st.columns([1, 4])
            with col_save2:
                if st.button("💾 保存免费额度", key="save_free", use_container_width=True):
                    try:
                        result = update_config('free_paragraphs_daily', str(free_paragraphs))
                        if result.get('success'):
                            st.success("✅ 免费额度已保存")
                            st.session_state.config_refresh += 1
                            st.rerun()
                        else:
                            st.error("❌ 保存失败")
                    except Exception as e:
                        st.error(f"❌ 保存失败: {str(e)}")
            
            with col_info2:
                st.caption(f"最后更新: {free_paragraphs_config.get('updated_at', 'N/A')}")
        
        # ==================== 管理员联系 ====================
        with st.expander("👤 管理员联系方式", expanded=True):
            st.markdown("**用户反馈时显示的联系方式**")
            
            admin_contact_config = configs_dict.get('admin_contact', {})
            admin_contact = st.text_area(
                "联系方式",
                value=admin_contact_config.get('config_value', '微信号：your_wechat_id'),
                height=100,
                max_chars=500,
                key="input_admin_contact"
            )
            
            col_save3, col_info3 = st.columns([1, 4])
            with col_save3:
                if st.button("💾 保存联系方式", key="save_contact", use_container_width=True):
                    try:
                        result = update_config('admin_contact', admin_contact)
                        if result.get('success'):
                            st.success("✅ 联系方式已保存")
                            st.session_state.config_refresh += 1
                            st.rerun()
                        else:
                            st.error("❌ 保存失败")
                    except Exception as e:
                        st.error(f"❌ 保存失败: {str(e)}")
            
            with col_info3:
                st.caption(f"最后更新: {admin_contact_config.get('updated_at', 'N/A')}")
        
        # ==================== 文件配置 ====================
        with st.expander("📄 文件限制配置", expanded=False):
            st.markdown("**上传文件的大小和类型限制**")
            
            max_file_size_config = configs_dict.get('max_file_size_mb', {})
            max_file_size = st.number_input(
                "最大文件大小（MB）",
                value=int(max_file_size_config.get('config_value', '50')),
                min_value=1,
                max_value=500,
                step=1,
                key="input_max_file_size"
            )
            
            col_save4, col_info4 = st.columns([1, 4])
            with col_save4:
                if st.button("💾 保存文件配置", key="save_file", use_container_width=True):
                    try:
                        result = update_config('max_file_size_mb', str(max_file_size))
                        if result.get('success'):
                            st.success("✅ 文件配置已保存")
                            st.session_state.config_refresh += 1
                            st.rerun()
                        else:
                            st.error("❌ 保存失败")
                    except Exception as e:
                        st.error(f"❌ 保存失败: {str(e)}")
            
            with col_info4:
                st.caption(f"最后更新: {max_file_size_config.get('updated_at', 'N/A')}")
        
        # ==================== 任务清理 ====================
        with st.expander("🗑️ 任务清理配置", expanded=False):
            st.markdown("**转换任务的保留期限**")
            
            task_expiry_config = configs_dict.get('task_expiry_days', {})
            task_expiry_days = st.number_input(
                "任务保留天数",
                value=int(task_expiry_config.get('config_value', '7')),
                min_value=1,
                max_value=365,
                step=1,
                key="input_task_expiry"
            )
            
            col_save5, col_info5 = st.columns([1, 4])
            with col_save5:
                if st.button("💾 保存清理配置", key="save_cleanup", use_container_width=True):
                    try:
                        result = update_config('task_expiry_days', str(task_expiry_days))
                        if result.get('success'):
                            st.success("✅ 清理配置已保存")
                            st.session_state.config_refresh += 1
                            st.rerun()
                        else:
                            st.error("❌ 保存失败")
                    except Exception as e:
                        st.error(f"❌ 保存失败: {str(e)}")
            
            with col_info5:
                st.caption(f"最后更新: {task_expiry_config.get('updated_at', 'N/A')}")
        
        # ==================== 批量操作 ====================
        st.markdown("---")
        st.subheader("🚀 批量操作")
        
        col_batch1, col_batch2 = st.columns(2)
        
        with col_batch1:
            if st.button("📤 导出当前配置", use_container_width=True):
                import json
                config_export = {k: v['config_value'] for k, v in configs_dict.items()}
                st.json(config_export)
                st.download_button(
                    label="📥 下载配置文件",
                    data=json.dumps(config_export, indent=2, ensure_ascii=False),
                    file_name="system_config.json",
                    mime="application/json"
                )
        
        with col_batch2:
            if st.button("🗑️ 重置为默认值", use_container_width=True, type="secondary"):
                st.warning("⚠️ 此操作将覆盖所有自定义配置")
                if st.button("确认重置", key="confirm_reset"):
                    result = init_default_configs()
                    if result.get('success'):
                        st.success(f"✅ {result.get('message')}")
                        st.session_state.config_refresh += 1
                        st.rerun()
                    else:
                        st.error(f"❌ {result.get('message')}")
        
    except Exception as e:
        st.error(f"❌ 加载配置失败: {str(e)}")
        st.exception(e)
    
    st.markdown("---")
    st.caption("💡 提示：修改配置后立即生效，无需重启服务")
