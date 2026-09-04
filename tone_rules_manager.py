# -*- coding: utf-8 -*-
"""
语气规则管理引擎（T02）
无 Streamlit 依赖，可独立测试。

职责：
1. 提供默认规则集（re-export doc_converter.get_default_tone_rules）
2. 规则 CRUD（浏览/增/删/改）
3. 规则校验
4. 测试转换（用当前规则集模拟祈使语气转换）
5. 导入/导出 JSON
6. 持久化（读写 data_manager 的 style_mappings._tone_rules）
"""
import json
import re
from typing import Dict, List, Optional, Tuple

from doc_converter import get_default_tone_rules, build_word_pattern


class ToneRulesManager:
    """祈使语气规则管理器（无状态工具类）"""

    # 规则结构中的分类键
    CATEGORY_MULTI = "multi_imperative"
    CATEGORY_SINGLE = "single_imperative"
    CATEGORY_BIDDER = "bidder_terms"
    CATEGORY_EXCEPTIONS = "exceptions"
    CATEGORY_YING_DUI = "ying_dui_verbs"

    EXCEPTION_KEYS = ("multi", "ying", "xu")

    # 中文分类展示名
    CATEGORY_LABELS = {
        CATEGORY_MULTI: "多字祈使词替换",
        CATEGORY_SINGLE: "单字祈使词替换",
        CATEGORY_BIDDER: "投标人称谓替换",
    }

    # ==================== 默认规则 ====================

    @staticmethod
    def default_rules() -> Dict:
        """返回默认规则集（深拷贝，避免外部修改污染默认值）"""
        return get_default_tone_rules()

    # ==================== 校验 ====================

    @staticmethod
    def normalize_rules(rules: Optional[Dict]) -> Dict:
        """规范化规则字典，确保所有必需键存在且类型正确。

        输入为 None 或部分缺失时，用默认规则补齐缺失部分。
        返回规范化后的规则字典。
        """
        defaults = get_default_tone_rules()
        if not isinstance(rules, dict):
            return defaults

        normalized = {
            "multi_imperative": dict(rules.get("multi_imperative", {}) or {}),
            "single_imperative": dict(rules.get("single_imperative", {}) or {}),
            "bidder_terms": dict(rules.get("bidder_terms", {}) or {}),
            "exceptions": {
                "multi": list(rules.get("exceptions", {}).get("multi", []) or []),
                "ying": list(rules.get("exceptions", {}).get("ying", []) or []),
                "xu": list(rules.get("exceptions", {}).get("xu", []) or []),
            },
            "ying_dui_verbs": list(rules.get("ying_dui_verbs", []) or []),
        }
        return normalized

    @staticmethod
    def validate_rules(rules: Dict) -> Tuple[bool, str]:
        """校验规则字典，返回 (是否有效, 错误信息)。

        规则：
        - 替换映射的原词/替换词必须为非空字符串
        - 例外词、ying_dui_verbs 列表元素必须为非空字符串
        """
        if not isinstance(rules, dict):
            return False, "规则必须为字典结构"

        for cat in ("multi_imperative", "single_imperative", "bidder_terms"):
            mapping = rules.get(cat, {})
            if mapping is None:
                continue
            if not isinstance(mapping, dict):
                return False, f"分类 {cat} 必须为字典（原词→替换词）"
            for k, v in mapping.items():
                if not isinstance(k, str) or not k.strip():
                    return False, f"分类 {cat} 中存在空原词"
                if not isinstance(v, str) or not v.strip():
                    return False, f"分类 {cat} 中「{k}」的替换词为空"

        exc = rules.get("exceptions", {}) or {}
        if not isinstance(exc, dict):
            return False, "exceptions 必须为字典"
        for key in ("multi", "ying", "xu"):
            lst = exc.get(key, []) or []
            if not isinstance(lst, list):
                return False, f"exceptions.{key} 必须为列表"
            for item in lst:
                if not isinstance(item, str) or not item.strip():
                    return False, f"exceptions.{key} 中存在空字符串"

        verbs = rules.get("ying_dui_verbs", []) or []
        if not isinstance(verbs, list):
            return False, "ying_dui_verbs 必须为列表"
        for v in verbs:
            if not isinstance(v, str) or not v.strip():
                return False, "ying_dui_verbs 中存在空字符串"

        return True, ""

    # ==================== CRUD ====================

    @staticmethod
    def add_replace_rule(rules: Dict, category: str, source: str, target: str) -> Tuple[bool, str, Dict]:
        """在指定替换分类中新增规则。返回 (成功, 消息, 新规则)。"""
        if category not in ("multi_imperative", "single_imperative", "bidder_terms"):
            return False, f"未知分类 {category}", rules
        source = (source or "").strip()
        target = (target or "").strip()
        if not source:
            return False, "原词不能为空", rules
        if not target:
            return False, "替换词不能为空", rules
        if category not in rules:
            rules[category] = {}
        rules[category][source] = target
        return True, f"已添加规则：{source} → {target}", rules

    @staticmethod
    def update_replace_rule(rules: Dict, category: str, old_source: str, new_source: str, new_target: str) -> Tuple[bool, str, Dict]:
        """编辑替换规则。返回 (成功, 消息, 新规则)。"""
        if category not in ("multi_imperative", "single_imperative", "bidder_terms"):
            return False, f"未知分类 {category}", rules
        mapping = rules.get(category, {})
        if old_source not in mapping:
            return False, f"原词「{old_source}」不存在", rules
        new_source = (new_source or "").strip()
        new_target = (new_target or "").strip()
        if not new_source or not new_target:
            return False, "原词和替换词不能为空", rules
        # 先删旧键，再写新键（避免键名变化时残留）
        del mapping[old_source]
        mapping[new_source] = new_target
        return True, f"已更新规则：{new_source} → {new_target}", rules

    @staticmethod
    def delete_replace_rule(rules: Dict, category: str, source: str) -> Tuple[bool, str, Dict]:
        """删除替换规则。返回 (成功, 消息, 新规则)。"""
        if category not in ("multi_imperative", "single_imperative", "bidder_terms"):
            return False, f"未知分类 {category}", rules
        mapping = rules.get(category, {})
        if source not in mapping:
            return False, f"原词「{source}」不存在", rules
        del mapping[source]
        return True, f"已删除规则：{source}", rules

    @staticmethod
    def add_exception(rules: Dict, key: str, word: str) -> Tuple[bool, str, Dict]:
        """在例外词列表（multi/ying/xu）中新增。"""
        if key not in ("multi", "ying", "xu"):
            return False, f"未知例外词分类 {key}", rules
        word = (word or "").strip()
        if not word:
            return False, "例外词不能为空", rules
        if "exceptions" not in rules:
            rules["exceptions"] = {}
        lst = rules["exceptions"].setdefault(key, [])
        if word in lst:
            return False, f"例外词「{word}」已存在", rules
        lst.append(word)
        return True, f"已添加例外词：{word}", rules

    @staticmethod
    def delete_exception(rules: Dict, key: str, word: str) -> Tuple[bool, str, Dict]:
        """删除例外词。"""
        if key not in ("multi", "ying", "xu"):
            return False, f"未知例外词分类 {key}", rules
        lst = (rules.get("exceptions", {}) or {}).get(key, []) or []
        if word not in lst:
            return False, f"例外词「{word}」不存在", rules
        lst.remove(word)
        return True, f"已删除例外词：{word}", rules

    @staticmethod
    def add_ying_dui_verb(rules: Dict, verb: str) -> Tuple[bool, str, Dict]:
        """新增"应+对"分离结构标志动词。"""
        verb = (verb or "").strip()
        if not verb:
            return False, "标志动词不能为空", rules
        verbs = rules.setdefault("ying_dui_verbs", [])
        if verb in verbs:
            return False, f"标志动词「{verb}」已存在", rules
        verbs.append(verb)
        return True, f"已添加标志动词：{verb}", rules

    @staticmethod
    def delete_ying_dui_verb(rules: Dict, verb: str) -> Tuple[bool, str, Dict]:
        """删除"应+对"分离结构标志动词。"""
        verbs = rules.get("ying_dui_verbs", []) or []
        if verb not in verbs:
            return False, f"标志动词「{verb}」不存在", rules
        verbs.remove(verb)
        return True, f"已删除标志动词：{verb}", rules

    # ==================== 测试转换 ====================

    @staticmethod
    def test_convert(rules: Dict, text: str) -> str:
        """用当前规则集模拟祈使语气转换（用于测试预览）。

        复用 DocumentConverter 的实例级正则构建 + 简化版替换逻辑。
        注意：此方法不处理跨 run / 零宽字符，仅做纯文本级替换，足够用于规则测试。
        """
        rules = ToneRulesManager.normalize_rules(rules)
        if not text:
            return ""

        # 构建正则（复用 doc_converter.build_word_pattern）
        multi_map = rules.get("multi_imperative", {})
        single_map = rules.get("single_imperative", {})
        bidder_map = rules.get("bidder_terms", {})
        exc = rules.get("exceptions", {})
        multi_exc = exc.get("multi", [])
        ying_exc = exc.get("ying", [])
        xu_exc = exc.get("xu", [])
        ying_dui_verbs = rules.get("ying_dui_verbs", [])

        def _word_re(words):
            return re.compile('|'.join(build_word_pattern(w) for w in words)) if words else None

        bidder_re = None
        if bidder_map:
            patterns = []
            for w in bidder_map:
                if w.startswith("投标人"):
                    patterns.append(r'(?<![本])' + re.escape(w) + r'(?![a-zA-Z0-9])')
                else:
                    patterns.append(build_word_pattern(w))
            bidder_re = re.compile('|'.join(patterns))

        multi_re = _word_re(multi_map.keys())
        single_re = _word_re(single_map.keys())

        def is_multi_exc(full, start, end, word):
            s = max(0, start - 20)
            e = min(len(full), end + 20)
            sub = full[s:e]
            for exc_word in multi_exc:
                pos = sub.find(exc_word)
                while pos != -1:
                    es = s + pos
                    ee = es + len(exc_word)
                    if es <= start < ee:
                        return True
                    pos = sub.find(exc_word, pos + 1)
            return False

        def is_single_exc(full, start, end, word):
            exceptions = ying_exc if word == "应" else (xu_exc if word == "须" else [])
            s = max(0, start - 20)
            e = min(len(full), end + 20)
            sub = full[s:e]
            for exc_word in exceptions:
                pos = sub.find(exc_word)
                while pos != -1:
                    es = s + pos
                    ee = es + len(exc_word)
                    if es <= start < ee:
                        if exc_word == "应对":
                            # 检查是否"应+对"分离结构
                            after_dui = full[end:end + 25]
                            verb_re = re.compile('(' + '|'.join(re.escape(v) for v in ying_dui_verbs) + ')') if ying_dui_verbs else None
                            if verb_re:
                                for m in verb_re.finditer(after_dui):
                                    if m.start() > 2:
                                        return False
                        return True
                    pos = sub.find(exc_word, pos + 1)
            return False

        result = text

        # 1. 投标人称谓
        if bidder_re:
            result = bidder_re.sub(lambda m: bidder_map.get(m.group(0), m.group(0)), result)
        # 2. 多字祈使词
        if multi_re:
            def _multi_repl(m):
                word = m.group(0)
                if is_multi_exc(result, m.start(), m.end(), word):
                    return word
                return multi_map.get(word, word)
            result = multi_re.sub(_multi_repl, result)
        # 3. 单字祈使词
        if single_re:
            def _single_repl(m):
                word = m.group(0)
                if is_single_exc(result, m.start(), m.end(), word):
                    return word
                return single_map.get(word, word)
            result = single_re.sub(_single_repl, result)

        result = result.replace('将将', '将把')
        return result

    # ==================== 导入 / 导出 ====================

    @staticmethod
    def export_json(rules: Dict) -> str:
        """导出规则为 JSON 字符串。"""
        return json.dumps(ToneRulesManager.normalize_rules(rules), ensure_ascii=False, indent=2)

    @staticmethod
    def import_json(json_str: str) -> Tuple[bool, str, Optional[Dict]]:
        """从 JSON 字符串导入规则。返回 (成功, 消息, 规则或 None)。"""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return False, f"JSON 解析失败：{e}", None
        if not isinstance(data, dict):
            return False, "JSON 顶层必须为对象", None
        ok, msg = ToneRulesManager.validate_rules(data)
        if not ok:
            return False, msg, None
        return True, "导入成功", ToneRulesManager.normalize_rules(data)

    # ==================== 持久化 ====================

    @staticmethod
    def load(user_id: str) -> Dict:
        """从用户数据加载语气规则（无配置时返回默认规则）。"""
        try:
            from data_manager import load_user_data
            user_data = load_user_data(user_id)
            style_mappings = (user_data or {}).get('style_mappings', {}) or {}
            rules = style_mappings.get('_tone_rules')
            if not rules:
                return ToneRulesManager.default_rules()
            return ToneRulesManager.normalize_rules(rules)
        except Exception:
            return ToneRulesManager.default_rules()

    @staticmethod
    def save(user_id: str, rules: Dict) -> Tuple[bool, str]:
        """保存语气规则到用户数据 style_mappings._tone_rules。"""
        ok, msg = ToneRulesManager.validate_rules(rules)
        if not ok:
            return False, msg
        try:
            from data_manager import load_user_data, save_user_data
            user_data = load_user_data(user_id) or {}
            if 'style_mappings' not in user_data or not isinstance(user_data.get('style_mappings'), dict):
                user_data['style_mappings'] = {}
            user_data['style_mappings']['_tone_rules'] = ToneRulesManager.normalize_rules(rules)
            save_user_data(user_data, user_id)
            return True, "规则已保存"
        except Exception as e:
            return False, f"保存失败：{e}"

    @staticmethod
    def reset(user_id: str) -> Tuple[bool, str]:
        """恢复默认规则并保存。"""
        return ToneRulesManager.save(user_id, ToneRulesManager.default_rules())
