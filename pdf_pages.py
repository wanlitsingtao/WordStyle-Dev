# -*- coding: utf-8 -*-
"""【已停用 2026-11-05】云端页码定位：docx → PDF（LibreOffice 无头渲染）→ 按页文本定位标题。

⚠️ 本模块当前**不在任何生产路径上**。停用原因（用户实测，硬指标）：
    用户 578 页的标书里某标题，Word 页脚显示 573，本模块给出 **645**。
    645 已超过 PDF 的 578 页总数 → 不是定位找错，而是 LibreOffice 与 Word
    的排版引擎差异导致**整篇重排膨胀约 12%**（字体替换、行高、表格行高累计）。
    继续展示这种数字比没有更糟。用户因此定的验收标准是：
    「与 Word 里的页码一致就保留，做不到就把页码显示去掉」→ 只保留 Word 路径
    （见 page_locator.py / title_preprocessor._apply_word_pages）。
    随之删除：`packages.txt`（不再装 libreoffice-writer / fonts-noto-cjk）。

    保留本文件与配套测试的原因：里面「按文档顺序单调匹配 + 跳过目录条目」
    的算法与 Word 无关，将来若能在云端拿到与 Word 一致的渲染器（或做
    Word→PDF 离线预处理）可以直接复用。若确定不再需要，连同
    `temp/test_title_leak_check.py::TestPdfPageMatching` 一起删掉。

原始说明（保留以备恢复）
------------------------
docx 不保存「实时分页」，只有 Word 保存时写下的 ``w:lastRenderedPageBreak``
快照。程序生成/格式转换得到的 docx 往往一条标记都没有，按标记推算就会把
578 页的文档算成 25 页（用户 2026-11-05 报的就是这个）。

本机 Windows 可以用 Word COM 取物理页码（见 page_locator.py）；Streamlit
社区云跑在 Linux 上，没有 Word，只能用 LibreOffice 真渲染一遍拿到真实分页，
再在 PDF 每页的文本里按文档顺序找标题 —— 这就是本模块的职责（现已停用）。

精度说明
--------
LibreOffice 与 Word 的排版引擎不同，字体替换/行距细节会让页码相差几页
（装齐中文字体后可显著减小）。所以本模块的页码只承诺「真实渲染页」，
界面文案必须写明来源，不能宣称与 Word 完全一致。

失败策略
--------
任何一步失败（没装 LibreOffice、转换超时、PDF 解析失败）都返回 ``None``，
由调用方退回「分页标记估算」或「页码不可用」，绝不抛异常拖垮标题查漏。

依赖声明（原 packages.txt，现已删除）
------------------------------------
Streamlit Community Cloud 会在部署时执行 apt-get install packages.txt 里的包，
**该文件不支持 `#` 注释**——每行都会原样当作包名传给 apt，注释会被报成
「Unable to locate package #」（2026-11-05 首次部署就是这么失败的）。
原内容是 ``libreoffice-writer`` 与 ``fonts-noto-cjk`` 两行，现随本模块停用一起删除。
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import List, Optional, Sequence

logger = logging.getLogger('WordStyle')

# LibreOffice 转换大文档（数百页）需要时间，但必须有上限，否则界面像卡死。
CONVERT_TIMEOUT = 240.0
# 单个 PDF 页的文本提取很便宜；整篇定位再给一个总预算兜底。
TOTAL_TIMEOUT = 600.0

_SUFFIXES = ('',)


def _find_soffice() -> Optional[str]:
    """定位 LibreOffice 可执行文件（可用环境变量 SOFFICE_PATH 强制指定）。"""
    forced = os.environ.get('SOFFICE_PATH')
    if forced and os.path.exists(forced):
        return forced
    for name in ('soffice', 'libreoffice', 'soffice.bin'):
        path = shutil.which(name)
        if path:
            return path
    # PATH 里没有时补几个常见安装位置（云端的 apt 安装一般在 /usr/bin）
    candidates = [
        '/usr/bin/soffice',
        '/usr/lib/libreoffice/program/soffice',
        '/opt/libreoffice/program/soffice',
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def is_available() -> bool:
    """当前环境能不能走 LibreOffice 渲染（检测可执行文件 + pypdf）。"""
    if not _find_soffice():
        return False
    try:
        import pypdf  # noqa: F401
    except Exception:
        return False
    return True


def convert_to_pdf(docx_path: str, timeout: float = CONVERT_TIMEOUT) -> Optional[str]:
    """用 LibreOffice 无头模式把 docx 转成 PDF，返回 PDF 路径（失败返回 None）。

    注意 ``-env:UserInstallation``：云端以非 root 用户运行，LibreOffice 默认
    会往 HOME 写配置；并发调用时还会互相抢同一个 profile 导致卡死。这里给
    每次转换一个独立临时 profile，既避免权限问题也避免并发冲突。
    """
    soffice = _find_soffice()
    if not soffice:
        return None
    outdir = tempfile.mkdtemp(prefix='ws_pdf_out_')
    profile = tempfile.mkdtemp(prefix='ws_lo_profile_')
    try:
        cmd = [
            soffice,
            '-env:UserInstallation=file:///' + profile.replace('\\', '/').lstrip('/'),
            '--headless', '--norestore', '--invisible', '--nolockcheck',
            '--convert-to', 'pdf', '--outdir', outdir, docx_path,
        ]
        logger.info('[PAGES] 调用 LibreOffice 渲染 PDF…')
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout,
        )
        base = os.path.splitext(os.path.basename(docx_path))[0] + '.pdf'
        pdf_path = os.path.join(outdir, base)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path
        logger.warning('[PAGES] LibreOffice 未产出 PDF（rc=%s, stderr=%s）',
                       proc.returncode, (proc.stderr or b'')[:300])
        return None
    except subprocess.TimeoutExpired:
        logger.warning('[PAGES] LibreOffice 转换超时（%.0fs）', timeout)
        return None
    except Exception as e:
        logger.warning('[PAGES] LibreOffice 转换失败：%s', e)
        return None
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _normalize(text: str) -> str:
    """去掉所有空白/零宽字符，用于跨行、跨栏的宽松匹配。"""
    text = (text or '').replace('\u00a0', ' ').replace('\u3000', ' ')
    text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)
    return re.sub(r'\s+', '', text)


def _looks_like_toc_tail(concat: str, end: int, remaining: int = 0) -> bool:
    """匹配位置之后是否跟着「点线 + 页码」→ 命中的是目录条目，不是正文标题。

    目录形如「7.4.17轨旁AP和天线…………578」，正文标题后面接的是正文文字。
    不排掉目录的话，每个标题都会定位到目录页（实测会把 578 页算成 25 页，
    正是用户报的错）。

    `remaining`：探针只截了标题前 N 个字符时，标题剩余部分的长度。
    必须把它一起纳入窗口，否则短探针命中的目录条目会因为「点线还没出现」
    而被误判成正文。
    """
    # 窗口要留够：目录点线常常十几个字符（"………………578"），
    # 只取 8 个字符会连页码都框不进来，判定直接失效。
    window = concat[end:end + max(remaining, 0) + 40]
    if not window:
        return False
    # 点线可能是多个半角点/间隔号，也可能是一个省略号（U+2026）。
    return bool(re.search(r'(?:[.·]{2,}|…)\s*\d', window))


def extract_page_texts(pdf_path: str, progress_callback=None) -> List[str]:
    """提取 PDF 每页文本（已归一化），失败返回空列表。"""
    try:
        from pypdf import PdfReader
    except Exception as e:
        logger.info('[PAGES] 未安装 pypdf，无法解析 PDF：%s', e)
        return []
    try:
        reader = PdfReader(pdf_path)
        total = len(reader.pages)
        pages: List[str] = []
        for i, page in enumerate(reader.pages):
            try:
                pages.append(_normalize(page.extract_text() or ''))
            except Exception:
                pages.append('')
            if progress_callback is not None and total and (i % 5 == 0 or i == total - 1):
                try:
                    progress_callback(i + 1, total)
                except Exception:
                    pass
        return pages
    except Exception as e:
        logger.warning('[PAGES] PDF 解析失败：%s', e)
        return []


def locate_in_pdf(pdf_path: str, texts: Sequence[str],
                  progress_callback=None) -> Optional[List[Optional[int]]]:
    """在一份 PDF 里按文档顺序定位各标题所在页（1-based），找不到为 None。"""
    pages = extract_page_texts(pdf_path, progress_callback=progress_callback)
    if not pages:
        return None

    # 把整份文档拼成一个串，并记录每页起点，便于「位置 → 页码」O(log n) 换算。
    starts: List[int] = []
    buf: List[str] = []
    pos = 0
    for p in pages:
        starts.append(pos)
        buf.append(p)
        pos += len(p)
    concat = ''.join(buf)

    results: List[Optional[int]] = []
    cursor = 0
    for raw in texts:
        probe_full = _normalize(raw)
        if not probe_full:
            results.append(None)
            continue
        found = -1
        end = -1
        # 由长到短试几个探针长度：太长容易受断行/软连字符影响，太短会误命中。
        for n in (24, 14, 9):
            probe = probe_full[:n]
            if len(probe) < 4:
                continue
            search_from = cursor
            for _ in range(3):       # 最多跳过 3 个目录式命中
                idx = concat.find(probe, search_from)
                if idx < 0:
                    break
                if _looks_like_toc_tail(concat, idx + len(probe),
                                        remaining=len(probe_full) - len(probe)):
                    search_from = idx + len(probe)
                    continue
                found, end = idx, idx + len(probe)
                break
            if found >= 0:
                break
        if found < 0:
            results.append(None)
            continue
        # 二分找所在页
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= found:
                lo = mid
            else:
                hi = mid - 1
        results.append(lo + 1)
        cursor = end
    return results


def locate_pages_pdf(docx_path: str, texts: Sequence[str],
                     progress_callback=None,
                     timeout: float = CONVERT_TIMEOUT) -> Optional[List[Optional[int]]]:
    """docx → PDF → 定位页码。环境不可用或失败返回 None（调用方回退估算）。"""
    if not texts or not is_available():
        return None
    pdf_path = convert_to_pdf(docx_path, timeout=timeout)
    if not pdf_path:
        return None
    try:
        return locate_in_pdf(pdf_path, texts, progress_callback=progress_callback)
    finally:
        # PDF 只是中间产物，用完即删（几百页的 PDF 有几十 MB）
        try:
            os.remove(pdf_path)
            shutil.rmtree(os.path.dirname(pdf_path), ignore_errors=True)
        except OSError:
            pass
