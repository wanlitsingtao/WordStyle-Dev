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
"""


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
