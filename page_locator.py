# -*- coding: utf-8 -*-
"""用本机 Word 取「物理页码」的定位器（可选能力，失败即回退）。

## 为什么要它

docx 格式**不保存实时分页**，只有 `w:lastRenderedPageBreak` 这种「上次渲染的
快照」。文档一旦被编辑过，这些快照就会失真 —— 实测某 414 页招标文件里写了
449 个分页标记，按标记推算得到 445 页，个别标题偏 1~16 页。纯 XML 推算无法
分辨哪些标记已失效，所以「精确页码」只能让 Word 用真实排版引擎算。

Word 状态栏「第 X 页」= `Range.Information(wdActiveEndPageNumber)`，这正是
**物理页码**（与页脚里手写的「第 X 页 共 Y 页」域无关，后者可能自定义起始值）。

## 性能（实测：414 页 / 314 个标题 / 5864 段）

| 写法 | 耗时 |
|---|---|
| PowerShell 逐条 Find | 36s |
| Python 逐条设置 Find 属性 | 22s |
| **Python 单次 Execute（本模块）** | **12.6s**（打开 2.1s + 定位 9.9s） |

差异主要来自 COM 往返次数：每次属性赋值都是一次跨进程调用，所以这里把
FindText / MatchCase / Wrap … 全部塞进一次 `Execute()`。

## 可用性

仅 Windows + 已装 Microsoft Word + 已装 pywin32 时可用；其余环境
`locate_pages()` 返回 None，调用方回退到 XML 估算，功能不受影响。
"""
from __future__ import annotations

import logging
import re
import sys
import threading
import time
from typing import Iterable, List, Optional, Sequence

logger = logging.getLogger('WordStyle')

# Word 常量
_WD_ACTIVE_END_PAGE_NUMBER = 3      # 物理页码（= 状态栏「第 X 页」）
_WD_FIND_STOP = 0                   # 不绕回文档开头继续找
_MsoAutomationSecurityForceDisable = 3

# Word 只能一次开一个实例做这件事，避免多个请求并发拉起多个 Word 进程
_WORD_LOCK = threading.Lock()

# 每次查找用的文本长度。太短容易命中正文里的同号引用，太长会被 Word 的
# Find 255 字符上限截断，20 字在实测 314 条上零误定位。
_PROBE_LEN = 20


def is_available() -> bool:
    """当前环境能否用 Word 取页码（不实际启动 Word）。"""
    if sys.platform != 'win32':
        return False
    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
    except Exception:
        return False
    return True


def _norm(s: str) -> str:
    """去掉所有空白，用于校验「找到的位置」确实是目标段落。"""
    return re.sub(r'\s+', '', s or '')


def _to_find_text(text: str, n: int = _PROBE_LEN) -> str:
    """把 python 文本转成 Word Find 的非通配符模式文本。

    - `^` 在 Word Find 里是转义字符（^p=段落、^t=制表符…），必须先自己转义；
    - docx 里标题与编号之间常是制表符（`\\t`），Word 文本里也是制表符，
      直接拿空格去搜会**搜不到** —— 实测 314 条里有 17 条因此未命中，
      改成 `^t` 后全部命中。
    """
    # 顺序有讲究：**先截断再转义**。
    # 转义会把每个 ^ 翻倍成 ^^，所以转义后末尾的 ^ 一定是偶数个，
    # 不会出现「悬空转义前缀」—— 若先转义再截断才会切出半个转义对。
    s = (text or '').strip()[:n]
    s = s.replace('^', '^^').replace('\t', '^t').replace('\r', ' ').replace('\n', ' ')
    return s


def locate_pages(docx_path: str, texts: Sequence[str],
                 time_budget: float = 120.0,
                 progress_callback=None) -> Optional[List[Optional[int]]]:
    """返回每个 `texts[i]` 所在段落的物理页码（1-based）。

    Args:
        docx_path: 传给 Word 打开的文件路径（Word 不接受内存流，调用方需先落盘）。
        texts: 按**文档顺序**排列的标题文本，单调向后查找（保证重复文本不会串位）。
        time_budget: 总时间预算（秒），超时后剩余条目返回 None，不抛异常。
        progress_callback: 可选，progress_callback(done, total)。
            这一段动辄十几秒，没有进度回报用户会以为界面卡死。

    Returns:
        - `None`：环境不支持（非 Windows / 无 Word / COM 起不来）→ 调用方回退估算；
        - `list`：与 `texts` 等长，元素为页码或 None（该条没定位到）。

    Note:
        失败一律返回 None 而不是抛异常：页码是「辅助定位」信息，
        不能让它的失败拖垮整个标题查漏功能。
    """
    if not is_available() or not texts:
        return None

    try:
        import pythoncom
        import win32com.client as win32
    except Exception:       # pragma: no cover - 与 is_available 双保险
        return None

    acquired = _WORD_LOCK.acquire(timeout=time_budget)
    if not acquired:
        logger.warning('Word 页码定位：等待其他任务超时，回退估算')
        return None

    started = time.time()
    app = None
    doc = None
    result: List[Optional[int]] = [None] * len(texts)
    try:
        pythoncom.CoInitialize()        # Streamlit 在非主线程跑脚本，必须先初始化 COM
        app = win32.DispatchEx('Word.Application')   # 独立实例，不干扰用户已开的 Word
        app.Visible = False
        app.DisplayAlerts = 0
        try:
            app.AutomationSecurity = _MsoAutomationSecurityForceDisable   # 禁宏，防文档带宏执行
        except Exception:
            pass
        doc = app.Documents.Open(
            FileName=str(docx_path),
            ReadOnly=True,              # 只读：绝不改动用户的文档
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Visible=False,
        )

        rng = doc.Content
        find = rng.Find
        find.ClearFormatting()
        total_end = doc.Content.End
        pos = 0
        _last_report = [0.0]
        for i, text in enumerate(texts):
            if time.time() - started > time_budget:
                logger.warning('Word 页码定位超出时间预算（%.0fs），剩余 %d 条回退估算',
                               time_budget, len(texts) - i)
                break
            probe = _to_find_text(text)
            if not probe:
                continue
            rng.SetRange(pos, total_end)
            # 一次 Execute 传全部参数：每次属性赋值都是一次 COM 往返，
            # 逐条设置会慢一倍以上（实测 22s → 12.6s）。
            ok = find.Execute(
                FindText=probe, MatchCase=False, MatchWholeWord=False,
                MatchWildcards=False, MatchSoundsLike=False, MatchAllWordForms=False,
                Forward=True, Wrap=_WD_FIND_STOP,
                Format=False, ReplaceWith='', Replace=0,
            )
            if not ok:
                continue
            # 校验：Word 找到的段落开头必须与预期一致（忽略空白）。
            # 不做这步的话，短编号（如 "1"）可能命中正文里的同号引用并连锁错位。
            got = rng.Text.replace('\r', '').replace('\x07', '').strip()
            if not _norm(got).startswith(_norm(text)[:8]):
                logger.debug('Word 页码定位：第 %d 条文本校验不符，跳过（expected=%r got=%r）',
                             i, text[:20], got[:20])
                pos = rng.End
                continue
            result[i] = int(rng.Information(_WD_ACTIVE_END_PAGE_NUMBER))
            pos = rng.End

            # 进度回报按时间节流：COM 调用本身是耗时大头，别让回调把速度再拖下去。
            if progress_callback is not None and time.time() - _last_report[0] >= 0.2:
                _last_report[0] = time.time()
                try:
                    progress_callback(i + 1, len(texts))
                except Exception:
                    pass

        hit = sum(1 for v in result if v)
        logger.info('Word 页码定位完成：%d/%d 条命中，耗时 %.1fs',
                    hit, len(texts), time.time() - started)
        return result
    except Exception:
        logger.exception('Word 页码定位失败，回退到分页标记估算')
        return None
    finally:
        try:
            if doc is not None:
                doc.Close(False)        # 不保存
        except Exception:
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        _WORD_LOCK.release()
