"""文件 I/O 工具：原子写、表格解析、错误中文化、脱敏、文件名消毒。"""

from __future__ import annotations

import io
import os
import re
import tempfile
from pathlib import Path

import pandas as pd

from itol_mcp.exceptions import WorkspaceError
from itol_mcp.utils.constants import BIDI_CHARS, CONTROL_CHARS_RE

# 树 ID 等外部值消毒白名单
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]+$")


def atomic_write_text(path: Path, content: str, force: bool = False) -> Path:
    """原子写文本文件（temp + rename），目录自动创建。

    ``force=False`` 且文件已存在时报错（防覆盖）。
    """
    path = path.expanduser().resolve()
    if path.exists() and not force:
        raise WorkspaceError(f"文件已存在：{path}，如需覆盖请设置 force=true")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".itol_tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def read_text_file(path: Path, max_bytes: int | None = None) -> str:
    """读取文本文件；超限抛 ``WorkspaceError``。"""
    if not path.is_file():
        raise WorkspaceError(f"文件不存在或不是常规文件：{path}")
    size = path.stat().st_size
    if max_bytes is not None and size > max_bytes:
        raise WorkspaceError(
            f"文件过大（{size} 字节 > 上限 {max_bytes} 字节），请改用工作区直连或拆分处理"
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceError(f"文件不是有效 UTF-8 文本：{path}（{exc}）") from exc


def parse_table_text(text: str, sep: str | None = None) -> pd.DataFrame:
    """解析 CSV/TSV 表格文本为 DataFrame。

    ``sep`` 为 None 时自动嗅探（Tab 优先，其次逗号），支持首行表头。
    """
    if not text.strip():
        raise WorkspaceError("表格内容为空")
    # 取数据行做分隔符嗅探（跳过开头注释行）
    sniff_lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not sniff_lines:
        raise WorkspaceError("表格内容为空（无有效数据行）")
    sample = sniff_lines[0]
    if sep is None:
        sep = "\t" if "\t" in sample else ","
    delimiter = {"\t": "\t", ",": ",", ";": ";"}.get(sep, sep)
    try:
        df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, comment="#")
    except Exception as exc:  # pandas 解析错误
        raise WorkspaceError(f"表格解析失败：{exc}") from exc
    if df.empty or df.columns is None or len(df.columns) < 1:
        raise WorkspaceError("表格没有有效列")
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed", na=False)]
    df = df.dropna(how="all")
    if df.empty:
        raise WorkspaceError("表格没有有效数据行")
    # 列去空白
    df.columns = [str(c).strip() for c in df.columns]
    return df


def format_number(value: object) -> str:
    """数值格式化：int 原样、float 去尾零、非数值字符串原样。"""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN
            return "0.0"
        text = f"{value:.10g}"
        return text
    text = str(value).strip()
    return text


def safe_filename_part(name: str) -> str:
    """将外部值（如 tree_id）消毒为安全文件名组件。

    仅允许 ``[A-Za-z0-9_.-]``，非法字符替换为 ``_``；拒绝空结果。
    """
    cleaned = re.sub(r"[^A-Za-z0-9_.\-]", "_", str(name))
    cleaned = cleaned.strip(".")
    if not cleaned:
        raise WorkspaceError(f"非法文件名：{name!r}")
    return cleaned


def redact(text: str, secrets: set[str] | None = None) -> str:
    """将给定文本中的疑似密钥替换为 ``***REDACTED***``。"""
    result = text
    result = result.replace(".itolapi.key", "***KEYFILE***")
    if secrets:
        for sec in secrets:
            if sec:
                result = result.replace(sec, "***REDACTED***")
    # 通用兜底：连续 8-128 位字母数字密钥形态
    result = re.sub(r"(?i)(api[_ ]?key|apikey)[=:\s]+[A-Za-z0-9]{8,}", r"\1=***REDACTED***", result)
    return result


def detect_control_chars(text: str) -> list[str]:
    """检测文本中的控制字符与双向 Unicode 溢出字符，返回问题字符列表。"""
    issues: list[str] = []
    for m in re.finditer(CONTROL_CHARS_RE, text):
        issues.append(f"控制字符 U+{ord(m.group()):04X}")
    for ch in BIDI_CHARS:
        if ch in text:
            issues.append(f"双向 Unicode 字符 U+{ord(ch):04X}")
    return issues


def translate_itol_api_error(text: str) -> str:
    """iTOL 批量接口错误原文 → 友好中文提示（基于附录 B 映射表）。"""
    upper = text.upper()
    if not text.strip():
        return "iTOL 服务器返回空响应：请检查模板文件格式或稍后重试"
    if "SUBSCRIPTION" in upper or "REGISTRATION" in upper:
        return "批量上传需要有效的 iTOL 标准版订阅，请检查账户订阅状态"
    if "UNAUTHORIZED" in upper or "INVALID API KEY" in upper or "APIKEY" in upper:
        return "iTOL API Key 无效或已轮换，请使用 itol_config_set_api_key 重新配置"
    if "EXTENSION" in upper or "FORMAT" in upper or "FILE" in upper:
        return "上传文件格式不合法，请检查树文件扩展名（.tree/.tree.txt/.jplace）与模板格式"
    if "NOT FOUND" in upper:
        return "iTOL：指定的对象不存在（tree_id 或项目名有误）"
    if "SIZE" in upper or "LARGE" in upper:
        return "上传文件过大，请精简树规模或模板数据集后重试"
    if "BUSY" in upper or "TIMEOUT" in upper:
        return "iTOL 服务器繁忙或超时，请稍后重试（建议间隔数秒）"
    return text.strip()[:500]
