# -*- coding: utf-8 -*-
"""
祈使语气配置页（T02）
加载规则 → 编辑 → 测试转换 → 保存全部 / 恢复默认 / 导入导出。
"""
import logging

import streamlit as st

from state import app_state
from ui_theme import render_page_title, render_section_title

logger = logging.getLogger('WordStyle')

# 转换测试区两个框的高度（px）：输入文本框与转换结果框等高，
# 避免"高度太小、只有一行"的局促感；结果框始终显示，无结果时显示占位提示。
TEST_BOX_HEIGHT = 200
TEST_RESULT_PLACEHOLDER = "点击「测试转换」后在此显示结果"


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
    """渲染转换测试区：输入文本框 → 测试转换按钮 → 转换结果框（三列等高）。

    结果框始终显示且始终与输入框等高；点击按钮后用当前编辑中的临时规则
    模拟转换，结果直接写入 session_state，本轮即可显示（无需 rerun）。
    """
    from tone_rules_manager import ToneRulesManager

    st.markdown("---")
    render_section_title("🧪 转换测试")

    col_input, col_btn, col_result = st.columns([5, 1.6, 5])

    with col_input:
        st.caption("输入文本")
        test_text = st.text_area(
            "输入文本",
            placeholder="例如：投标人必须理解并应对招标文件中的要求负责。",
            key="tone_test_input",
            height=TEST_BOX_HEIGHT,
            label_visibility="collapsed",
        )

    with col_btn:
        # Streamlit 的列默认顶部对齐，用一段空白把按钮压到与两个框大致齐平的位置
        st.markdown(
            "<div style='height:%dpx'></div>" % (TEST_BOX_HEIGHT // 2),
            unsafe_allow_html=True,
        )
        test_clicked = st.button("测试转换 →", key="tone_test_btn", use_container_width=True)

    # 先处理按钮、再渲染结果框：本轮就能显示本次结果，不必 rerun
    if test_clicked:
        if not test_text.strip():
            st.warning("⚠️ 请输入要测试的文本。")
        else:
            st.session_state.tone_test_result = ToneRulesManager.test_convert(rules, test_text)

    with col_result:
        st.caption("转换结果")
        st.text_area(
            "转换结果",
            value=st.session_state.get("tone_test_result") or TEST_RESULT_PLACEHOLDER,
            height=TEST_BOX_HEIGHT,
            disabled=True,
            label_visibility="collapsed",
        )

    st.caption("转换结果框始终显示；点击「测试转换」后用当前编辑中的规则模拟转换。")


def render_tone_config_page():
    """语气配置页入口（供 st.navigation 调用）。"""
    from tone_rules_manager import ToneRulesManager
    from components.sidebar import render_sidebar
    from components.tone_rules import render_tone_rules_editor, clear_tone_editor_state

    render_sidebar("tone_config")

    # 页面级标题：与侧边栏品牌「标书编写神器」顶对齐，文案与功能菜单项一致。
    # 必须紧跟 render_sidebar() 之后 —— 详见 ui_theme.PAGE_TITLE_MARGIN_TOP 的说明。
    render_page_title("⚙️ 祈使语气配置")

    st.markdown(
        "管理文档转换时的祈使语气替换规则。修改后保存到您的账户，"
        "所有转换均使用您的自定义规则。"
    )

    rules = _ensure_rules_loaded()

    # 操作反馈占位：按钮渲染在页面顶部，事件处理在编辑区之后，
    # 反馈仍显示在操作区正下方（而不是掉到页面最底部）。
    action_status = st.empty()

    # ===== 1. 操作区（置顶：先保存 / 恢复 / 导入导出，再编辑）=====
    col_reset, col_save = st.columns(2)
    with col_reset:
        reset_clicked = st.button("🔄 恢复默认规则", key="tone_reset_btn", use_container_width=True)
    with col_save:
        save_clicked = st.button("💾 保存全部", key="tone_save_btn", type="primary", use_container_width=True)

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
                    # st.rerun() 会丢弃本轮输出，故把提示存到 session_state，下一轮再显示
                    st.session_state.tone_flash = ("success", msg + "，点击「保存全部」生效。")
                    st.rerun()
                else:
                    action_status.error(msg)

    st.markdown("---")

    # ===== 2. 编辑区（@st.fragment，局部刷新）=====
    rules = render_tone_rules_editor(rules)
    app_state.set_tone_rules(rules)

    # ===== 3. 转换测试区 =====
    _render_test_section(rules)

    # ===== 操作事件处理 =====
    # 必须放在编辑区之后：编辑组件返回的是本轮渲染后的最新工作副本，
    # 顶部按钮只负责渲染，事件在这里统一读取最新 rules 处理。
    flash = st.session_state.pop("tone_flash", None)
    if flash:
        getattr(action_status, flash[0])(flash[1])

    if save_clicked:
        ok, msg = ToneRulesManager.validate_rules(rules)
        if not ok:
            action_status.error(f"❌ 校验失败：{msg}")
        else:
            user_id = app_state.get_user_id()
            if not user_id:
                action_status.error("❌ 用户未初始化，无法保存。")
            else:
                ok2, msg2 = ToneRulesManager.save(user_id, rules)
                if ok2:
                    app_state.set_tone_rules(ToneRulesManager.normalize_rules(rules))
                    app_state.set_tone_rules_dirty(False)
                    action_status.success(f"✅ {msg2}，下次转换生效。")
                else:
                    action_status.error(f"❌ {msg2}")

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
                    st.session_state.tone_flash = ("success", f"✅ {msg}")
                    st.rerun()
                else:
                    action_status.error(f"❌ {msg}")
            else:
                app_state.set_tone_rules(ToneRulesManager.default_rules())
                clear_tone_editor_state()
                st.session_state.tone_reset_confirm = False
                st.session_state.tone_flash = ("success", "✅ 已恢复默认规则")
                st.rerun()
        else:
            st.session_state.tone_reset_confirm = True
            action_status.warning("⚠️ 确定要恢复为默认规则吗？当前编辑中的自定义规则将被覆盖。请再次点击「恢复默认规则」确认。")
