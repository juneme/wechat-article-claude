"""微信公众号草稿客户端（精简版）。

只做一件事：通过云浪控制台把正文、图片、草稿送进微信，并读回来核对。
不发布、不群发、不自动重试写操作。
"""

from __future__ import annotations

import argparse
import getpass
import json
import mimetypes
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

WRITE_METHODS = {"POST", "PUT", "DELETE"}
LEGACY_CONFIG = Path.home() / ".codex" / "yunoe" / "client.json"
CONFIG_PATH = Path.home() / ".claude" / "yunoe" / "client.json"
IMAGE_HOSTS = {"mmbiz.qpic.cn", "mmecoa.qpic.cn"}

_IMG_TAG = re.compile(r"<img\b(?:[^>'\"]|'[^']*'|\"[^\"]*\")*>", re.IGNORECASE)
_SRC_ATTR = re.compile(
    r"(?P<prefix>\bsrc\s*=\s*)"
    r"(?:(?P<quote>['\"])(?P<quoted>.*?)(?P=quote)|(?P<bare>[^\s>]+))",
    re.IGNORECASE,
)


class ClientError(RuntimeError):
    pass


# ---------- 基础设施 ----------

def _dump(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _server_url(value: str) -> str:
    result = value.strip().rstrip("/")
    parsed = urlparse(result)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ClientError("服务器地址必须以 http:// 或 https:// 开头")
    return result


def _canonical_image(source: str) -> str:
    parsed = urlsplit(source.strip())
    if (parsed.hostname or "").lower() not in IMAGE_HOSTS:
        return source.strip()
    return urlunsplit(("https", "mmbiz.qpic.cn", parsed.path, parsed.query, parsed.fragment))


def _canonical_content(content: str) -> str:
    """把正文里微信图床的 http:// 地址统一成 https://mmbiz.qpic.cn。"""

    def fix_tag(tag: re.Match[str]) -> str:
        def fix_src(src: re.Match[str]) -> str:
            quote = src.group("quote") or ""
            raw = src.group("quoted") or src.group("bare") or ""
            return f"{src.group('prefix')}{quote}{_canonical_image(raw)}{quote}"

        return _SRC_ATTR.sub(fix_src, tag.group(0), count=1)

    return _IMG_TAG.sub(fix_tag, content)


def _config_path() -> Path:
    return LEGACY_CONFIG if LEGACY_CONFIG.exists() else CONFIG_PATH


def _load_config() -> dict:
    path = _config_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ClientError("尚未配对，请先运行：pair --server <控制台地址>") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ClientError(f"本地配对文件不可读：{path}（{exc}）") from exc
    if not config.get("console_url") or not config.get("client_token"):
        raise ClientError("本地配对文件不完整，请重新运行 pair")
    return config


def _save_config(config: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    temp.replace(path)


def _request(method, url, *, token=None, account_id=None, body=None, content_type=None):
    headers = {"Accept": "application/json", "User-Agent": "wechat-article/1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if account_id is not None:
        headers["X-Wechat-Account-ID"] = str(account_id)
    if content_type:
        headers["Content-Type"] = content_type
    retry_note = "；写操作未自动重试，请先核对远端状态" if method in WRITE_METHODS else ""
    try:
        with urlopen(Request(url, data=body, headers=headers, method=method), timeout=90) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = payload.get("detail") or payload
        except Exception:
            detail = exc.reason
        raise ClientError(f"HTTP {exc.code}: {detail}{retry_note}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ClientError(f"无法连接服务器：{exc}{retry_note}") from exc


def _api(args, method, path, *, payload=None, body=None, content_type=None):
    config = _load_config()
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        content_type = "application/json"
    return _request(
        method,
        f"{config['console_url']}{path}",
        token=config["client_token"],
        account_id=getattr(args, "account_id", None),
        body=body,
        content_type=content_type,
    )


def _multipart(files: list[Path], mode: str) -> tuple[bytes, str]:
    boundary = f"wechat-{uuid.uuid4().hex}"
    chunks = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="mode"\r\n\r\n',
        mode.encode(),
        b"\r\n",
    ]
    for path in files:
        if not path.is_file():
            raise ClientError(f"文件不存在：{path}")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks += [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="images"; filename="{path.name.replace(chr(34), "")}"\r\n'.encode("utf-8"),
            f"Content-Type: {ctype}\r\n\r\n".encode(),
            path.read_bytes(),
            b"\r\n",
        ]
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _payload(path_value: str) -> dict:
    path = Path(path_value).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ClientError(f"JSON 文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ClientError(f"JSON 格式错误：{exc}") from exc
    if not isinstance(payload, dict):
        raise ClientError("JSON 顶层必须是对象")
    if "content_file" in payload:
        content_path = (path.parent / str(payload.pop("content_file"))).resolve()
        try:
            payload["content"] = content_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ClientError(f"正文文件不存在：{content_path}") from exc
    if isinstance(payload.get("content"), str):
        payload["content"] = _canonical_content(payload["content"])
    return payload


# ---------- 命令 ----------

def cmd_pair(args) -> None:
    console_url = _server_url(args.server)
    code = getpass.getpass("请输入控制台 1 分钟验证码（输入不回显）：").strip()
    if not code:
        raise ClientError("验证码不能为空")
    result = _request(
        "POST",
        f"{console_url}/api/v1/pairing/exchange",
        body=json.dumps({"code": code}).encode("utf-8"),
        content_type="application/json",
    )
    if not isinstance(result, dict) or not result.get("client_token"):
        raise ClientError("服务器未返回客户端令牌")
    saved = _server_url(str(result.get("console_url") or console_url))
    _save_config({
        "console_url": saved,
        "client_token": result["client_token"],
        "paired_at": datetime.now(UTC).isoformat(timespec="seconds"),
    })
    print(f"配对成功：{saved}")


def cmd_status(args) -> None:
    config = _load_config()
    context = _api(args, "GET", "/api/v1/account")
    if not isinstance(context, dict) or not isinstance(context.get("account"), dict):
        raise ClientError("服务器未返回当前公众号上下文")
    _dump({
        "paired": True,
        "console_url": config["console_url"],
        "active_account_id": context.get("active_account_id"),
        "account": context["account"],
    })


def cmd_upload(args) -> None:
    files = [Path(v).expanduser().resolve() for v in args.files]
    body, ctype = _multipart(files, args.mode)
    _dump(_api(args, "POST", "/api/v1/wechat-images", body=body, content_type=ctype))


def cmd_draft_create(args) -> None:
    payload = _payload(args.json)
    payload.setdefault(
        "request_id",
        f"article-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}",
    )
    _dump(_api(args, "POST", "/api/v1/wechat-drafts", payload=payload))


def cmd_draft_list(args) -> None:
    query = urlencode({"limit": args.limit, "offset": args.offset})
    _dump(_api(args, "GET", f"/api/v1/wechat-drafts?{query}"))


def cmd_draft_get(args) -> None:
    _dump(_api(args, "GET", f"/api/v1/wechat-drafts/{args.id}"))


def cmd_draft_update(args) -> None:
    _dump(_api(args, "PUT", f"/api/v1/wechat-drafts/{args.id}", payload=_payload(args.json)))


def cmd_draft_delete(args) -> None:
    if not args.confirm:
        raise ClientError("删除草稿必须显式提供 --confirm")
    _dump(_api(args, "DELETE", f"/api/v1/wechat-drafts/{args.id}"))


def cmd_wechat_list(args) -> None:
    query = urlencode({
        "offset": args.offset,
        "count": args.count,
        "no_content": str(args.no_content).lower(),
    })
    _dump(_api(args, "GET", f"/api/v1/wechat-drafts/wechat-box?{query}"))


def cmd_wechat_get(args) -> None:
    _dump(_api(args, "GET", f"/api/v1/wechat-drafts/wechat-box/{args.media_id}"))


def cmd_wechat_update(args) -> None:
    _dump(_api(
        args, "PUT",
        f"/api/v1/wechat-drafts/wechat-box/{args.media_id}",
        payload=_payload(args.json),
    ))


def cmd_wechat_delete(args) -> None:
    if not args.confirm:
        raise ClientError("删除微信草稿必须显式提供 --confirm")
    _dump(_api(args, "DELETE", f"/api/v1/wechat-drafts/wechat-box/{args.media_id}"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wechat_article.py",
        description="微信公众号草稿客户端：写草稿，不发布。",
    )
    parser.add_argument("--account-id", type=int, help="临时切到同用户名下的另一个公众号")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pair", help="用一次性验证码建立配对")
    p.add_argument("--server", required=True, help="控制台根地址")
    p.set_defaults(handler=cmd_pair)

    sub.add_parser("status", help="检查配对与当前公众号").set_defaults(handler=cmd_status)

    p = sub.add_parser("image-upload", help="上传图片")
    p.add_argument("--mode", required=True, choices=("article", "material", "both"),
                   help="article=正文图（返回 URL），material=封面素材（返回 media_id）")
    p.add_argument("files", nargs="+")
    p.set_defaults(handler=cmd_upload)

    p = sub.add_parser("draft-create", help="按 JSON 创建草稿")
    p.add_argument("--json", required=True)
    p.set_defaults(handler=cmd_draft_create)

    p = sub.add_parser("draft-list", help="列出本地草稿记录")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(handler=cmd_draft_list)

    p = sub.add_parser("draft-get", help="读回本地草稿记录")
    p.add_argument("id", type=int)
    p.set_defaults(handler=cmd_draft_get)

    p = sub.add_parser("draft-update", help="修改草稿")
    p.add_argument("id", type=int)
    p.add_argument("--json", required=True)
    p.set_defaults(handler=cmd_draft_update)

    p = sub.add_parser("draft-delete", help="删除草稿")
    p.add_argument("id", type=int)
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(handler=cmd_draft_delete)

    p = sub.add_parser("wechat-list", help="列出真实微信草稿箱")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--no-content", action="store_true")
    p.set_defaults(handler=cmd_wechat_list)

    p = sub.add_parser("wechat-get", help="按 media_id 读回真实草稿")
    p.add_argument("media_id")
    p.set_defaults(handler=cmd_wechat_get)

    p = sub.add_parser("wechat-update", help="按 media_id 修改真实草稿")
    p.add_argument("media_id")
    p.add_argument("--json", required=True)
    p.set_defaults(handler=cmd_wechat_update)

    p = sub.add_parser("wechat-delete", help="按 media_id 删除真实草稿")
    p.add_argument("media_id")
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(handler=cmd_wechat_delete)

    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        args = build_parser().parse_args()
        args.handler(args)
        return 0
    except ClientError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
