"""日志工具：ISO8601 时间戳、滚动文件、密钥脱敏过滤器。"""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

# 密钥形态正则：api_key 参数值、环境变量赋值等
_REDACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([A-Za-z0-9]{6,})"),
    re.compile(r"(?i)('api_key'\s*:\s*')([^']+)(')"),
    re.compile(r"(?i)(\"api_key\"\s*:\s*\")([^\"]+)(\")"),
    re.compile(r"(?i)key=([A-Za-z0-9]{6,128})"),
]


class RedactingFilter(logging.Filter):
    """将日志消息中的疑似密钥替换为 ``***REDACTED***``。"""

    def __init__(self, secrets: set[str] | None = None) -> None:
        super().__init__()
        self.secrets = secrets or set()

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = msg
        for secret in self.secrets:
            if secret:
                redacted = redacted.replace(secret, "***REDACTED***")
        for pattern in _REDACT_PATTERNS:
            redacted = pattern.sub(lambda m: m.group(1) + "***REDACTED***", redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


_logger: logging.Logger | None = None


def setup_logging(
    log_dir: Path, level: str = "INFO", secrets: set[str] | None = None
) -> logging.Logger:
    """初始化包级日志器（滚动文件 10MB x 3 + 控制台）。

    幂等：重复调用仅追加过滤器的密钥集合。
    """
    global _logger
    if _logger is not None:
        if secrets:
            for flt in _logger.filters:
                if isinstance(flt, RedactingFilter):
                    flt.secrets.update(secrets)
        return _logger

    log_dir = log_dir.expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "itol-mcp.log"

    logger = logging.getLogger("itol_mcp")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    logger.addFilter(RedactingFilter(secrets))

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(formatter)
    fh.addFilter(RedactingFilter(secrets))
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    sh.addFilter(RedactingFilter(secrets))
    logger.addHandler(sh)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """获取已初始化的日志器；未初始化时返回带默认过滤器的根日志器。"""
    if _logger is not None:
        return _logger
    logger = logging.getLogger("itol_mcp")
    if not logger.filters:
        logger.addFilter(RedactingFilter())
    return logger
