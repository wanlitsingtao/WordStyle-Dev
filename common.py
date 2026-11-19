# -*- coding: utf-8 -*-
"""工程公共方法模块 —— 跨模块复用的公共方法集中放在这里。

[2026-10-06 建立] 本工程按「职责」分模块（data_manager / style_cleaner /
title_preprocessor / tone_rules_manager …）。此前被多处复用的公共方法散落在各领域
模块里，最后连文档转换引擎 doc_converter.py 都被当成了存放处 —— 转换引擎不该背负
这类职责。本模块就是这些「公共方法」的唯一落点。

收录准则（三条都满足才放这里）：
  1) 被 ≥2 个模块（或界面）复用；只服务单一调用方的，留在它自己的模块里；
  2) 不属于某个单一领域模块的职责；属于的，放回那个领域模块；
  3) 不是文档转换引擎专属逻辑；专属的留在 doc_converter.py，且不再往里加工具函数。

与 utils.py 的分工（两个文件并存，不合并 —— 2026-10-06 用户拍板，不再讨论搬迁）：
  - utils.py：通用小工具（HTML 转义、文件名清理、时间转换…），现状保持不变；
  - common.py：跟业务/文档相关的公共方法，可以 import 其它工程模块。

新增公共方法的落点判据 —— 不看"是否通用"，看**是否需要工程内的业务上下文**：
  - 需要业务上下文（识别模板样式、读 config 里的业务参数…）→ common.py；
  - 纯字符串 / 路径 / 时间处理，不需要业务上下文 → utils.py。

写法约定：会牵出重依赖（doc_converter / python-docx / streamlit 等）的 import
一律写在**函数内**（本工程既有写法），这样 `import common` 不会拖起整条依赖链。

当前收录：
  - collect_template_style_names(doc)：模板文档「样式识别」的唯一实现
  - select_non_overlapping(candidates)：重叠替换区间的全局最优消解
    （祈使语气转换 doc_converter / 配置页测试框 tone_rules_manager 共用）
"""


def select_non_overlapping(candidates):
    """从候选替换区间中选出互不重叠、总覆盖长度最大的子集（加权区间调度）。

    [2026-11-19 新增] 祈使语气转换「重叠消解」的实现。旧消解按
    「长匹配优先、同长按起始位置」贪心，对**同长重叠**（如称谓词「投标人需」
    (0,4) 与多字词「需要提供」(3,7)）会错杀右侧那条，把句子转成
    「本投标人要提供…」这类残留。本方法改为全局求最优：

      1) 主目标：选中区间**总覆盖长度**最大（尽量多地应用用户规则）；
      2) 次目标：总覆盖相同时，**区间数更少**的方案优先
         （单条更具体的长规则优先于多条短规则拼接）。

    Example:
        「投标人需要提供」候选：投标人(0,3)、投标人需(0,4)、需要提供(3,7)
        贪心会选 (0,4)，残留「要」；本方法选 (0,3)+(3,7)，得「本投标人提供…」。

    Args:
        candidates: [(start, end, repl, ...), ...]，至少含 start/end/repl
            三元组（后续元素参与去重与排序稳定性，不影响语义）。
    Returns:
        选中子集（原元组），按 start 升序。
    """
    if not candidates:
        return []
    items = sorted(set(candidates), key=lambda c: (c[1], c[0], c[2]))
    n = len(items)
    # dp[i] = (score, 选中下标元组)：考虑 items[0..i] 范围内的最优（i 可选可不选）。
    # score = (总覆盖长度, -区间数)：主目标覆盖最长，次目标区间最少。
    dp = []
    for i in range(n):
        s_i, e_i = items[i][0], items[i][1]
        # 找最后一个 end <= s_i 的 j，以其 dp 为「选 items[i]」的前置状态；
        # items 按 end 升序，dp[j] 内所有区间 end <= items[j].end <= s_i，必不重叠。
        base_score, base_sel = (0, 0), ()
        for j in range(i - 1, -1, -1):
            if items[j][1] <= s_i:
                base_score, base_sel = dp[j]
                break
        take = ((base_score[0] + e_i - s_i, base_score[1] - 1), base_sel + (i,))
        if i > 0 and dp[i - 1][0] >= take[0]:
            dp.append(dp[i - 1])
        else:
            dp.append(take)
    result = [items[k] for k in dp[-1][1]]
    result.sort(key=lambda c: c[0])
    return result


def collect_template_style_names(doc):
    """模板文档「样式识别」的唯一实现（样式映射 / 模板样式精简共用）。

    [2026-10-06] 两个消费方必须调用这里，禁止各处另写一份识别逻辑：
      - 样式映射：components/upload.get_template_styles_list
      - 模板样式精简：style_cleaner.StyleCleaner.analyze_styles

    返回 (real_names, snapshot_names)：
      1) real_names：模板里真实存在的段落样式名（type == 段落 且有名），按名排序；
      2) snapshot_names：模板段落上「样式 + 直接格式」快照显示名
         （形如「标题 1 + 四号」），剔除与真实样式重名的，按名排序。

    两者拼起来就是「可选目标样式」清单，顺序固定为「真实样式在前、快照在后」。

    快照提取复用转换引擎里既有的 extract_template_format_snapshots，
    依赖方向是单向只读的：本模块 → doc_converter；doc_converter 不知道本模块存在。
    """
    from docx.enum.style import WD_STYLE_TYPE
    from doc_converter import extract_template_format_snapshots

    real_names = []
    for style in doc.styles:
        try:
            stype = style.type
        except Exception:
            continue
        if stype != WD_STYLE_TYPE.PARAGRAPH:
            continue
        name = style.name or ""
        if not name:
            continue
        real_names.append(name)
    real_names = sorted(real_names)

    real_set = set(real_names)
    try:
        snapshots = extract_template_format_snapshots(doc)
    except Exception:
        snapshots = {}
    snapshot_names = sorted(n for n in snapshots if n not in real_set)
    return real_names, snapshot_names
