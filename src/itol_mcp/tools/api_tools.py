"""组 E：iTOL API 工具（工具 25–30，见《04 §4.6》）。

上传/删除需要「标准版订阅 + API Key」（三通道：api_key 参数 > 环境变量 > 密钥文件）；
导出与状态探测不需要订阅，密钥可选。所有请求仅 HTTPS 且有超时/重试。
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from itol_mcp.exceptions import UsageError
from itol_mcp.tools.common import MCPServerLike, Runtime, execute, resolve_tree_text
from itol_mcp.utils.constants import DISPLAY_MODES
from itol_mcp.utils.io import safe_filename_part
from itol_mcp.utils.result import ToolResult

ITOL_WEB = "https://itol.embl.de"
_WAIT_LIMIT = 120


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册 iTOL API 工具。"""

    @server.tool(
        name="itol_upload",
        description=(
            "将树与一个或多个注释模板打包为 ZIP 上传至 iTOL（batch_uploader），返回 tree_id 与访问链接。"
            "tree/tree_file 必填其一；templates（模板文本列表）与 template_files（工作区模板路径列表）可同时提供。"
            "需要标准版订阅 + API Key（api_key 参数 / 环境变量 ITOL_API_KEY / 密钥文件）。"
            "上传后建议间隔数秒再导出（服务端渲染）。两次调用间请至少间隔数秒，避免限流。"
        ),
    )
    def itol_upload(
        tree: str | None = None,
        tree_file: str | None = None,
        templates: list[str] | None = None,
        template_files: list[str] | None = None,
        tree_name: str | None = None,
        tree_description: str | None = None,
        project_name: str | None = None,
        datasets_visible: str | None = None,
        force: bool = False,
        api_key: str | None = None,
    ) -> dict:
        """上传树与模板至 iTOL。"""
        return execute(
            runtime.logger,
            "itol_upload",
            lambda: _upload_impl(
                runtime,
                tree,
                tree_file,
                templates,
                template_files,
                tree_name,
                tree_description,
                project_name,
                datasets_visible,
                force,
                api_key,
            ),
        )

    @server.tool(
        name="itol_export",
        description=(
            "按 tree_id 从 iTOL 导出（batch_downloader），支持 8 种格式：pdf/svg/png/tiff/eps/newick/nexus/phyloxml。"
            "导出不需要订阅；datasets_visible 为逗号分隔的数据集索引（0 起）；dpi 为位图分辨率；"
            "display_mode 可选 1 矩形/2 环形/3 无根；extra_params 可透传任意批量导出参数（见资源 itol://help/batch-api）。"
            "文件默认写入工作区 exports/<tree_id>.<ext>。wait 为导出前等待秒数（≤120）。"
        ),
    )
    def itol_export(
        tree_id: str = "",
        format: str = "pdf",
        datasets_visible: str | None = None,
        dpi: int | None = None,
        width: int | None = None,
        height: int | None = None,
        display_mode: int | None = None,
        extra_params: dict | None = None,
        output: str | None = None,
        wait: int = 0,
        api_key: str | None = None,
    ) -> dict:
        """按 tree_id 导出为指定格式。"""
        return execute(
            runtime.logger,
            "itol_export",
            lambda: _export_impl(
                runtime,
                tree_id,
                format,
                datasets_visible,
                dpi,
                width,
                height,
                display_mode,
                extra_params,
                output,
                wait,
                api_key,
            ),
        )

    @server.tool(
        name="itol_upload_and_export",
        description=(
            "一步完成「上传 → 等待渲染 → 导出」，返回 tree_id、访问链接与本地文件。"
            "参数合并自 itol_upload 与 itol_export；wait 默认 10 秒；api_key 必填（上传需要订阅）。"
            "推荐用于快速出图场景（如 300dpi PDF）。两次调用间请至少间隔数秒。"
        ),
    )
    def itol_upload_and_export(
        tree: str | None = None,
        tree_file: str | None = None,
        templates: list[str] | None = None,
        template_files: list[str] | None = None,
        format: str = "pdf",
        wait: int = 10,
        output: str | None = None,
        datasets_visible: str | None = None,
        dpi: int | None = None,
        width: int | None = None,
        height: int | None = None,
        display_mode: int | None = None,
        extra_params: dict | None = None,
        project_name: str | None = None,
        tree_name: str | None = None,
        tree_description: str | None = None,
        force: bool = False,
        api_key: str | None = None,
    ) -> dict:
        """一步上传并导出。"""
        return execute(
            runtime.logger,
            "itol_upload_and_export",
            lambda: _upload_export_impl(
                runtime,
                tree,
                tree_file,
                templates,
                template_files,
                format,
                wait,
                output,
                datasets_visible,
                dpi,
                width,
                height,
                display_mode,
                extra_params,
                project_name,
                tree_name,
                tree_description,
                force,
                api_key,
            ),
        )

    @server.tool(
        name="itol_delete_tree",
        description=(
            "删除一棵 iTOL 树（batch_delete）。注意：删除不可恢复！"
            "需要标准版订阅 + API Key。返回服务器回执（脱敏）。"
        ),
    )
    def itol_delete_tree(tree_id: str = "", api_key: str | None = None) -> dict:
        """删除单棵树（不可恢复）。"""
        return execute(
            runtime.logger,
            "itol_delete_tree",
            lambda: _delete_tree_impl(runtime, tree_id, api_key),
        )

    @server.tool(
        name="itol_delete_project",
        description=(
            "删除整个 iTOL 项目（该项目下全部树）。注意：删除不可恢复！"
            "project_name 大小写敏感。需要标准版订阅 + API Key。"
        ),
    )
    def itol_delete_project(project_name: str = "", api_key: str | None = None) -> dict:
        """删除整个项目（不可恢复）。"""
        return execute(
            runtime.logger,
            "itol_delete_project",
            lambda: _delete_project_impl(runtime, project_name, api_key),
        )

    @server.tool(
        name="itol_query_status",
        description=(
            "探测树是否已就绪（以一次 SVG 导出探测）。注意：每次调用消耗一次导出配额。"
            "返回 status: ready/unknown 与说明。"
        ),
    )
    def itol_query_status(tree_id: str = "", api_key: str | None = None) -> dict:
        """探测树渲染就绪状态。"""
        return execute(
            runtime.logger,
            "itol_query_status",
            lambda: _query_status_impl(runtime, tree_id, api_key),
        )


# ---------------------------------------------------------------------------
# 实现
# ---------------------------------------------------------------------------


def _require_tree_id(tree_id: str) -> str:
    tree_id = (tree_id or "").strip()
    if not tree_id:
        raise UsageError("参数 tree_id 必填（iTOL 数字树 ID）")
    return tree_id


def _prepare_upload_files(
    runtime: Runtime, tree_text: str, templates: list[str] | None, template_files: list[str] | None
) -> tuple[Path, list[Path]]:
    """将内联树/模板落盘为临时文件，返回 (tree_path, template_paths)。"""
    fd, tree_tmp = tempfile.mkstemp(prefix="itol_tree_", suffix=".tree.txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(tree_text)

    tpl_paths: list[Path] = []
    try:
        if template_files:
            for tf in template_files:
                real = runtime.workspace.resolve(tf)
                if not real.is_file():
                    raise UsageError(f"模板文件不存在：{tf}")
                tpl_paths.append(real)
        if templates:
            for idx, tpl in enumerate(templates, start=1):
                _fd, tmp = tempfile.mkstemp(prefix=f"itol_tpl_{idx:02d}_", suffix=".txt")
                with os.fdopen(_fd, "w", encoding="utf-8") as fh:
                    fh.write(tpl)
                tpl_paths.append(Path(tmp))
    except Exception:
        _cleanup([Path(tree_tmp), *tpl_paths])
        raise
    return Path(tree_tmp), tpl_paths


def _cleanup(paths: list[Path]) -> None:
    for p in paths:
        try:
            os.unlink(p)
        except OSError:
            pass


def _target_output(runtime: Runtime, output: str | None, tree_id: str, fmt: str) -> Path:
    """确定导出目标路径（默认 exports/<tree_id>.<ext>）。"""
    if output:
        return runtime.workspace.path_for(output)
    export_dir = runtime.config.effective_export_dir(runtime.workspace.root)
    safe_id = safe_filename_part(tree_id)
    return export_dir / f"{safe_id}.{fmt}"


def _move_to(path: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))
    return target


def _upload_impl(
    runtime: Runtime,
    tree: str | None,
    tree_file: str | None,
    templates: list[str] | None,
    template_files: list[str] | None,
    tree_name: str | None,
    tree_description: str | None,
    project_name: str | None,
    datasets_visible: str | None,
    force: bool,
    api_key: str | None,
) -> ToolResult:
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file)
    if not tree_text:
        raise UsageError("上传需要提供树（tree 或 tree_file）")
    client, _source = runtime.client(api_key)
    tree_tmp, tpl_paths = _prepare_upload_files(runtime, tree_text, templates, template_files)
    warnings: list[str] = []
    try:
        if len(tpl_paths) + 1 > runtime.config.max_upload_files:
            raise UsageError(
                f"单次上传文件数超过上限（{runtime.config.max_upload_files}）：{len(tpl_paths) + 1}"
            )
        if project_name is None:
            project_name = tree_name or Path(tree_file).stem if tree_file else "itol-mcp-upload"
        tree_id, server_warnings = client.upload(
            tree_tmp,
            template_files=tpl_paths,
            project_name=str(project_name) if project_name else None,
            tree_name=tree_name,
            tree_description=tree_description,
            force=force,
        )
        warnings.extend(server_warnings)
        if datasets_visible:
            warnings.append("datasets_visible 为导出阶段参数，上传时忽略（导出工具中生效）")
        webpage = f"{ITOL_WEB}/tree/{tree_id}"
        data = {"tree_id": tree_id, "webpage": webpage, "project_name": project_name}
        msg = f"上传成功：tree_id={tree_id}，访问 {webpage}（建议间隔数秒再导出）"
        return ToolResult.ok(msg, data, warnings=warnings)
    finally:
        client.close()
        _cleanup([tree_tmp, *tpl_paths])


def _export_impl(
    runtime: Runtime,
    tree_id: str,
    fmt: str,
    datasets_visible: str | None,
    dpi: int | None,
    width: int | None,
    height: int | None,
    display_mode: int | None,
    extra_params: dict | None,
    output: str | None,
    wait: int,
    api_key: str | None,
) -> ToolResult:
    tree_id = _require_tree_id(tree_id)
    if display_mode is not None and display_mode not in DISPLAY_MODES:
        raise UsageError(
            f"display_mode 可选：{', '.join(f'{k}={v}' for k, v in DISPLAY_MODES.items())}"
        )
    if dpi is not None and not (10 <= dpi <= 2400):
        raise UsageError("dpi 需在 10–2400 之间")

    client, _source = runtime.client(api_key, required=False)
    try:
        export_dir = runtime.config.effective_export_dir(runtime.workspace.root)
        path = client.export(
            tree_id,
            fmt=fmt,
            out_dir=export_dir,
            datasets_visible=datasets_visible,
            dpi=dpi,
            width=width,
            height=height,
            display_mode=display_mode,
            extra_params=extra_params,
            wait=max(0, min(wait, _WAIT_LIMIT)),
        )
        target = _target_output(runtime, output, tree_id, fmt)
        if str(target) != str(path):
            path = _move_to(path, target)
        size = path.stat().st_size if path.is_file() else None
        data = {
            "tree_id": tree_id,
            "format": fmt,
            "file": str(path),
            "bytes": size,
        }
        files = [{"path": str(path), "kind": "image", "bytes": size}]
        return ToolResult.ok(f"导出成功：{fmt} → {path}（{size} 字节）", data, files=files)
    finally:
        client.close()


def _upload_export_impl(
    runtime: Runtime,
    tree: str | None,
    tree_file: str | None,
    templates: list[str] | None,
    template_files: list[str] | None,
    fmt: str,
    wait: int,
    output: str | None,
    datasets_visible: str | None,
    dpi: int | None,
    width: int | None,
    height: int | None,
    display_mode: int | None,
    extra_params: dict | None,
    project_name: str | None,
    tree_name: str | None,
    tree_description: str | None,
    force: bool,
    api_key: str | None,
) -> ToolResult:
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file)
    if not tree_text:
        raise UsageError("上传需要提供树（tree 或 tree_file）")
    if display_mode is not None and display_mode not in DISPLAY_MODES:
        raise UsageError(
            f"display_mode 可选：{', '.join(f'{k}={v}' for k, v in DISPLAY_MODES.items())}"
        )
    client, _source = runtime.client(api_key, required=True)
    tree_tmp, tpl_paths = _prepare_upload_files(runtime, tree_text, templates, template_files)
    try:
        if len(tpl_paths) + 1 > runtime.config.max_upload_files:
            raise UsageError(
                f"单次上传文件数超过上限（{runtime.config.max_upload_files}）：{len(tpl_paths) + 1}"
            )
        project = project_name or (
            tree_name or (Path(tree_file).stem if tree_file else "itol-mcp-upload")
        )
        tree_id, path = client.upload_and_export(
            tree_tmp,
            template_files=tpl_paths,
            fmt=fmt,
            out_dir=runtime.config.effective_export_dir(runtime.workspace.root),
            wait=max(0, min(wait, _WAIT_LIMIT)),
            project_name=project,
            tree_name=tree_name,
            tree_description=tree_description,
            datasets_visible=datasets_visible,
            dpi=dpi,
            width=width,
            height=height,
            extra_params=extra_params,
        )
        target = _target_output(runtime, output, tree_id, fmt)
        if output and str(target) != str(path):
            path = _move_to(path, target)
        size = path.stat().st_size
        webpage = f"{ITOL_WEB}/tree/{tree_id}"
        data = {"tree_id": tree_id, "webpage": webpage, "file": str(path), "bytes": size}
        files = [{"path": str(path), "kind": "image", "bytes": size}]
        return ToolResult.ok(f"上传并导出成功：tree_id={tree_id}，文件 {path}", data, files=files)
    finally:
        client.close()
        _cleanup([tree_tmp, *tpl_paths])


def _delete_tree_impl(runtime: Runtime, tree_id: str, api_key: str | None) -> ToolResult:
    tree_id = _require_tree_id(tree_id)
    client, _source = runtime.client(api_key, required=True)
    try:
        ok, message = client.delete_tree(tree_id)
        data = {"tree_id": tree_id, "deleted": ok, "server_message": message}
        msg = f"树 {tree_id} 已删除（不可恢复）" if ok else f"删除失败：{message}"
        return ToolResult.ok(msg, data)
    finally:
        client.close()


def _delete_project_impl(runtime: Runtime, project_name: str, api_key: str | None) -> ToolResult:
    project_name = (project_name or "").strip()
    if not project_name:
        raise UsageError("参数 project_name 必填（大小写敏感）")
    client, _source = runtime.client(api_key, required=True)
    try:
        ok, message = client.delete_project(project_name)
        data = {"project_name": project_name, "deleted": ok, "server_message": message}
        msg = f"项目 {project_name} 已删除（不可恢复）" if ok else f"删除失败：{message}"
        return ToolResult.ok(msg, data)
    finally:
        client.close()


def _query_status_impl(runtime: Runtime, tree_id: str, api_key: str | None) -> ToolResult:
    tree_id = _require_tree_id(tree_id)
    client, _source = runtime.client(api_key, required=False)
    try:
        status = client.query_status(tree_id)
        data = {"tree_id": tree_id, "status": status["status"], "detail": status["detail"]}
        msg = f"树 {tree_id} 状态：{status['status']}（{status['detail']}）"
        return ToolResult.ok(msg, data)
    finally:
        client.close()
