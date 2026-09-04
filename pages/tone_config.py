# -*- coding: utf-8 -*-
"""
祈使语气配置页（T02）
加载规则 → 编辑 → 测试转换 → 保存全部 / 恢复默认 / 导入导出。
"""
import logging

import streamlit as st

from state import app_state

logger = logging.getLogger('WordStyle')


def _ensure_rules_loaded():
    """确保会话中存在工作副本规则（首次进入时从用户数据加载）。"""
    if app_state.get_tone_rules() is None:
        user_id = app_state.get_user_id()
        if user_id:
            from data_manager import get_tone_rules
            rules = get_tone_rules(user_id)
        else:
            from tone_rules_manager import ToneRulesManager
            rules = ToneRulesManager.default_rules()
        app_state.set_tone_rules(rules)
    return app_state.get_tone_rules()


def _render_test_section(rules):
    """渲染测试转换区（用当前编辑中的临时规则模拟转换）。"""
    from tone_rules_manager import ToneRulesManager

    st.markdown("---")
    st.markdown("### 🧪 转换测试")
    test_text = st.text_area(
        "输入文本",
        placeholder="例如：投标人必须理解并应对招标文件中的要求负责。",
        key="tone_test_input",
        height=90,
    )
    if st.button("🧪 测试转换", key="tone_test_btn", use_container_width=True):
        if not test_text.strip():
            st.warning("⚠️ 请输入要测试的文本。")
        else:
            result = ToneRulesManager.test_convert(rules, test_text)
            st.session_state.tone_test_result = result

    if st.session_state.get('tone_test_result'):
        st.markdown("**转换结果：**")
        st.code(st.session_state.tone_test_result, language=None)


def render_tone_config_page():
    """语气配置页入口（供 st.navigation 调用）。"""
    from tone_rules_manager import ToneRulesManager
    from components.sidebar import render_sidebar
    render_sidebar("tone_config")

    st.title("⚙️ 祈使语气转换规则配置")
    st.markdown(
        "管理文档转换时的祈使语气替换规则。修改后保存到您的账户，"
        "所有转换均使用您的自定义规则。"
    )

    rules = _ensure_rules_loaded()

    # 编辑区（@st.fragment，局部刷新）
    from components.tone_rules import render_tone_rules_editor, clear_tone_editor_state
    rules = render_tone_rules_editor(rules)
    app_state.set_tone_rules(rules)

    st.markdown("---")

    # 操作按钮行（在编辑区之后，保证点击时能读取最新编辑值）
    col_reset, col_save, col_test = st.columns(3)
    with col_reset:
        reset_clicked = st.button("🔄 恢复默认规则", key="tone_reset_btn", use_container_width=True)
    with col_save:
        save_clicked = st.button("💾 保存全部", key="tone_save_btn", type="primary", use_container_width=True)
    with col_test:
        st.caption("测试转换见下方区域")

    # 导入 / 导出（P2）
    with st.expander("📥 导入 / 导出规则（JSON）", expanded=False):
        col_export, col_import = st.columns(2)
        with col_export:
            st.download_button(
                "⬇️ 导出当前规则",
                data=ToneRulesManager.export_json(rules),
                file_name="tone_rules.json",
                mime="application/json",
                key="tone_export_btn",
                use_container_width=True,
            )
        with col_import:
            import_json = st.text_area(
                "粘贴 JSON 内容",
                key="tone_import_json",
                height=120,
                placeholder='{"multi_imperative": {...}, ...}',
            )
            if st.button("⬆️ 导入", key="tone_import_btn", use_container_width=True):
                ok, msg, new_rules = ToneRulesManager.import_json(import_json)
                if ok:
                    app_state.set_tone_rules(new_rules)
                    app_state.set_tone_rules_dirty(True)
                    clear_tone_editor_state()
                    st.success(msg + "，点击「保存全部」生效。")
                    st.rerun()
                else:
                    st.error(msg)

    # 处理保存 / 恢复默认
    if save_clicked:
        ok, msg = ToneRulesManager.validate_rules(rules)
        if not ok:
            st.error(f"❌ 校验失败：{msg}")
        else:
            user_id = app_state.get_user_id()
            if not user_id:
                st.error("❌ 用户未初始化，无法保存。")
            else:
                ok2, msg2 = ToneRulesManager.save(user_id, rules)
                if ok2:
                    app_state.set_tone_rules(ToneRulesManager.normalize_rules(rules))
                    app_state.set_tone_rules_dirty(False)
                    st.success(f"✅ {msg2}，下次转换生效。")
                else:
                    st.error(f"❌ {msg2}")

    if reset_clicked:
        if st.session_state.get('tone_reset_confirm', False):
            user_id = app_state.get_user_id()
            if user_id:
                ok, msg = ToneRulesManager.reset(user_id)
                if ok:
                    app_state.set_tone_rules(ToneRulesManager.default_rules())
                    app_state.set_tone_rules_dirty(False)
                    clear_tone_editor_state()
                    st.session_state.tone_reset_confirm = False
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            else:
                app_state.set_tone_rules(ToneRulesManager.default_rules())
                clear_tone_editor_state()
                st.session_state.tone_reset_confirm = False
                st.rerun()
        else:
            st.session_state.tone_reset_confirm = True
            st.warning("⚠️ 确定要恢复为默认规则吗？当前编辑中的自定义规则将被覆盖。请再次点击「恢复默认规则」确认。")

    # 测试转换区
    _render_test_section(rules)
