"""iTOL API 服务：批量上传/导出/删除/状态查询客户端（实现设计第 5.7 节 + 附录 B）。

要点：
- ZIP 打包上传（树文件命名 ``*.tree``，模板按名称排序决定数据集顺序）；
- 上传响应逐行解析（警告行 + ``SUCCESS: <tree_id>`` / ``ERR`` 前缀）；
- 导出响应内容嗅探校验（HTML 错误页 / 短文本错误 / 格式最小体积）；
- 429/5xx 指数退避重试（POST 重试前记录 WARNING：可能重复建树）；
- 仅 HTTPS，统一超时。
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import time
import zipfile
from pathlib import Path

import httpx

from itol_mcp.exceptions import DeleteError, ExportError, UploadError
from itol_mcp.utils.constants import (
    DELETE_URL,
    EXPORT_FORMATS,
    EXPORT_MIN_BYTES,
    EXPORT_URL,
    RETRYABLE_STATUS_CODES,
    UPLOAD_URL,
)
from itol_mcp.utils.io import safe_filename_part, translate_itol_api_error

logger = logging.getLogger("itol_mcp")

# 导出格式 → 文件扩展名
_FORMAT_EXT = {
    "pdf": "pdf",
    "svg": "svg",
    "png": "png",
    "tiff": "tiff",
    "eps": "eps",
    "newick": "newick",
    "nexus": "nexus",
    "phyloxml": "phyloxml",
}


class ITOLClient:
    """iTOL 批量接口 HTTP 客户端。"""

    EXPORT_FORMATS = EXPORT_FORMATS

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        self.api_key: str | None = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.client = httpx.Client(timeout=timeout)
        # 只允许对 iTOL 官方域名的请求（防密钥外泄）
        self._allowed_hosts = {"itol.embl.de"}

    # -- 网络层 ---------------------------------------------------------------

    def _post(
        self,
        url: str,
        data: dict | None = None,
        files: dict | None = None,
    ) -> httpx.Response:
        """带重试的 POST；429/5xx 指数退避；POST 重试前记录 WARNING。"""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                logger.warning(
                    "重试 POST %s（第 %d/%d 次）：iTOL 接口无幂等键，可能产生重复上传，请留意项目列表",
                    _short_url(url),
                    attempt,
                    self.max_retries,
                )
                time.sleep(self.backoff_factor * (2 ** (attempt - 1)))
            try:
                resp = self.client.post(url, data=data, files=files)
            except httpx.HTTPError as exc:
                last_exc = exc
                continue
            if resp.status_code not in RETRYABLE_STATUS_CODES:
                return resp
            last_exc = None  # 可重试状态码
        if last_exc is not None:
            raise UploadError(f"请求 iTOL 失败（重试 {self.max_retries} 次后）：{last_exc}")
        raise UploadError(f"iTOL 服务器返回可重试错误状态（重试 {self.max_retries} 次后仍失败）")

    # -- 上传 ---------------------------------------------------------------

    def upload(
        self,
        tree_file: Path,
        template_files: list[Path] | None = None,
        project_name: str | None = None,
        tree_name: str | None = None,
        tree_description: str | None = None,
        force: bool = False,
    ) -> tuple[str, list[str]]:
        """打包并上传，返回 ``(tree_id, warnings)``。

        ``tree_file`` 需为已校验的工作区内路径；ZIP 内树文件统一命名为
        ``<basename>.tree``，模板按文件名排序（决定数据集应用顺序）。
        """
        template_files = template_files or []
        if not self.api_key:
            raise UploadError(
                "上传需要有效的 iTOL API Key（标准版订阅）。"
                "请通过工具参数 api_key、环境变量 ITOL_API_KEY 或密钥文件提供"
            )
        if len(template_files) + 1 > 50:
            raise UploadError(f"单次上传文件数超过上限（50）：{len(template_files) + 1}")

        project_name = project_name or tree_file.stem
        tree_name = tree_name or tree_file.stem
        zip_buf = self._build_zip(tree_file, template_files)

        try:
            resp = self._post(
                UPLOAD_URL,
                data={
                    "APIkey": self.api_key,
                    "projectName": project_name,
                    "treeName": tree_name,
                    **({"treeDescription": tree_description} if tree_description else {}),
                    **({"force": "1"} if force else {}),
                },
                files={"zipFile": ("upload.zip", zip_buf, "application/zip")},
            )
        except UploadError:
            raise
        self._check_https(resp)

        text = resp.text or ""
        return self._parse_upload_response(text, project_name)

    def _build_zip(self, tree_file: Path, template_files: list[Path]) -> io.BytesIO:
        """构建上传 ZIP（BytesIO，免落盘）。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 树文件：命名必须 *.tree（.tree.txt/.nwk.txt 等尾缀归一化）
            zf.writestr(_tree_arcname(tree_file), tree_file.read_bytes())
            # 模板按名称排序写入（iTOL 依序应用）
            for tf in sorted(template_files):
                zf.writestr(os.path.basename(str(tf)), tf.read_bytes())
        buf.seek(0)
        return buf

    def _parse_upload_response(self, text: str, project_name: str) -> tuple[str, list[str]]:
        """解析上传响应：警告行 + 末尾 SUCCESS: <tree_id>。"""
        if not text.strip():
            raise UploadError(
                "iTOL 服务器返回空响应：请检查模板文件格式或稍后重试（若持续失败，请确认已购买标准版订阅）"
            )
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        warnings: list[str] = []
        tree_id: str | None = None
        for ln in lines:
            upper = ln.upper()
            if upper.startswith("SUCCESS"):
                parts = ln.split(":", 1)
                tree_id = parts[1].strip() if len(parts) > 1 else parts[0].split(None, 1)[-1]
            elif upper.startswith(("ERR", "ERROR", "INVALID", "NOT FOUND")):
                raise UploadError(translate_itol_api_error(ln))
            else:
                warnings.append(ln)
        if tree_id is None:
            raise UploadError(
                translate_itol_api_error("\n".join(lines))
                + f"\n响应中未找到 SUCCESS 标记（projectName={project_name}）"
            )
        return tree_id, warnings

    # -- 导出 ---------------------------------------------------------------

    def export(
        self,
        tree_id: str,
        fmt: str = "pdf",
        out_dir: Path | None = None,
        datasets_visible: str | None = None,
        dpi: int | None = None,
        width: int | None = None,
        height: int | None = None,
        display_mode: int | None = None,
        extra_params: dict | None = None,
        wait: int = 0,
    ) -> Path:
        """按 tree_id 导出，返回本地文件路径。"""
        if fmt not in EXPORT_FORMATS:
            raise ExportError(f"不支持的导出格式：{fmt}（可选 {'/'.join(EXPORT_FORMATS)}）")
        if wait and wait > 0:
            time.sleep(min(wait, 120))

        payload: dict[str, object] = {"tree": tree_id, "format": fmt}
        if datasets_visible is not None:
            payload["datasets_visible"] = datasets_visible
        if dpi is not None:
            payload["dpi"] = dpi
        if width is not None:
            payload["width"] = width
        if height is not None:
            payload["height"] = height
        if display_mode is not None:
            payload["display_mode"] = display_mode
        if extra_params:
            payload.update({str(k): v for k, v in extra_params.items()})

        resp = self._post(EXPORT_URL, data=payload)
        self._check_https(resp)
        content = resp.content
        if not content:
            raise ExportError("iTOL 导出返回空内容，可能树尚未渲染完成，请稍候重试")

        # 内容校验
        ctype = resp.headers.get("content-type", "").lower()
        if "text/html" in ctype:
            raise ExportError(f"iTOL 返回错误页（tree_id={tree_id}）：{_html_error_hint(content)}")
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        if 0 < len(text) < 100 and any(
            kw in text.lower() for kw in ("error", "not found", "invalid", "fail")
        ):
            raise ExportError(f"iTOL 导出失败：{text.strip()[:200]}")

        min_bytes = EXPORT_MIN_BYTES.get(fmt, 0)
        if len(content) < min_bytes:
            raise ExportError(
                f"导出内容过小（{len(content)}B < {min_bytes}B，格式 {fmt}），"
                "可能为错误页或树未就绪，请检查 tree_id 后重试"
            )

        ext = _FORMAT_EXT.get(fmt, fmt)
        out_dir = (out_dir or Path(tempfile.mkdtemp())).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_id = safe_filename_part(tree_id)
        out_path = out_dir / f"{safe_id}.{ext}"
        out_path.write_bytes(content)
        return out_path

    def upload_and_export(
        self,
        tree_file: Path,
        template_files: list[Path] | None = None,
        fmt: str = "pdf",
        out_dir: Path | None = None,
        wait: int = 10,
        project_name: str | None = None,
        tree_name: str | None = None,
        tree_description: str | None = None,
        datasets_visible: str | None = None,
        dpi: int | None = None,
        width: int | None = None,
        height: int | None = None,
        extra_params: dict | None = None,
    ) -> tuple[str, Path]:
        """一步「上传 → 等待 → 导出」，返回 ``(tree_id, file_path)``。"""
        tree_id, _warnings = self.upload(
            tree_file,
            template_files=template_files,
            project_name=project_name or tree_file.stem,
            tree_name=tree_name or tree_file.stem,
            tree_description=tree_description,
        )
        path = self.export(
            tree_id,
            fmt=fmt,
            out_dir=out_dir,
            datasets_visible=datasets_visible,
            dpi=dpi,
            width=width,
            height=height,
            extra_params=extra_params,
            wait=wait,
        )
        return tree_id, path

    # -- 删除 ---------------------------------------------------------------

    def _delete(self, payload: dict[str, str]) -> tuple[bool, str]:
        if not self.api_key:
            raise DeleteError("删除需要有效的 iTOL API Key（标准版订阅），请先配置密钥")
        resp = self._post(DELETE_URL, data={"APIkey": self.api_key, **payload})
        self._check_https(resp)
        text = resp.text or ""
        upper = text.upper()
        if any(kw in upper for kw in ("SUCCESS", "OK", "DONE")):
            return True, text.strip()
        if text.strip():
            raise DeleteError(translate_itol_api_error(text))
        raise DeleteError("iTOL 删除接口返回空响应")

    def delete_tree(self, tree_id: str) -> tuple[bool, str]:
        """删除单棵树（不可恢复）。"""
        return self._delete({"tree": tree_id})

    def delete_project(self, project_name: str) -> tuple[bool, str]:
        """删除整个项目（不可恢复）。"""
        return self._delete({"project": project_name})

    # -- 状态 ---------------------------------------------------------------

    def query_status(self, tree_id: str) -> dict:
        """以一次 SVG 导出探测树就绪状态（每次调用消耗一次导出配额）。"""
        with tempfile.TemporaryDirectory() as tmp:
            try:
                path = self.export(tree_id, fmt="svg", out_dir=Path(tmp), wait=0)
                ok = path.stat().st_size > 100
            except ExportError as exc:
                return {"status": "unknown", "detail": f"导出探测失败：{exc}", "ready": False}
        return {
            "status": "ready" if ok else "unknown",
            "detail": "树已就绪（SVG 导出探测成功）" if ok else "树状态未知（探测内容过小）",
            "ready": ok,
        }

    # -- 工具 ---------------------------------------------------------------

    def _check_https(self, resp: httpx.Response) -> None:
        """校验请求域名与协议（防密钥外泄到非 iTOL 域名）。"""
        final_url = str(resp.url)
        if not final_url.lower().startswith("https://"):
            raise UploadError("非 HTTPS 请求被拦截")
        host = final_url.split("/")[2].lower() if "//" in final_url else ""
        if host not in self._allowed_hosts:
            raise UploadError(f"请求被拦截：非 iTOL 官方域名（{final_url[:100]}）")

    def close(self) -> None:
        """关闭底层 Client。"""
        try:
            self.client.close()
        except Exception:  # pragma: no cover
            pass


def _short_url(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def _tree_arcname(path: Path) -> str:
    """ZIP 内树文件规范名：以 ``.tree`` 结尾（iTOL 批量上传要求）。

    - ``foo.tree.txt``/``foo.nwk.txt`` → 先去掉 ``.txt`` 尾缀；
    - 已以 ``.tree``/``.nwk``/``.nexus``/``.jplace`` 结尾则原样保留；
    - 其余名称追加 ``.tree``。
    """
    name = path.name
    lowered = name.lower()
    if lowered.endswith(".txt") and any(
        lowered.endswith(ext + ".txt") for ext in (".tree", ".nwk", ".nexus")
    ):
        name = name[: -len(".txt")]
    if not name.lower().endswith((".tree", ".nwk", ".nexus", ".jplace")):
        name += ".tree"
    return name


def _html_error_hint(content: bytes) -> str:
    """从 HTML 错误页中尽力提取可读提示。"""
    import re

    text = content.decode("utf-8", errors="replace")
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:200] or "HTTP 错误页"
