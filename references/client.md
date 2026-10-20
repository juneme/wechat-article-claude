# 客户端命令

脚本绝对路径：`~/.claude/skills/wechat-article/scripts/wechat_article.py`。在项目目录里执行时用绝对路径调用。所有命令都读同一份配对文件。

下文命令表中的 `wechat_article.py` 是简写，实际调用请展开成绝对路径。

## 配对

```text
pair --server URL
```

验证码只在终端隐藏输入，不要贴进对话，也不要作为命令行参数。配对文件位置：

- 若 `~/.codex/yunoe/client.json` 已存在则沿用它（与旧版共用，不必重新配对）；
- 否则写入 `~/.claude/yunoe/client.json`。

令牌不打印、不写日志、不进版本库。密码一旦修改，该用户的全部客户端令牌作废，需要重新配对。

## 命令总表

```text
status
pair --server URL
image-upload --mode article|material|both FILE [FILE ...]
draft-create --json FILE
draft-list [--limit 100] [--offset 0]
draft-get ID
draft-update ID --json FILE
draft-delete ID --confirm
wechat-list [--offset 0] [--count 20] [--no-content]
wechat-get MEDIA_ID
wechat-update MEDIA_ID --json FILE
wechat-delete MEDIA_ID --confirm
```

`--account-id ID` 放在子命令前，仅用于临时切到同名下的另一个公众号；不要从本地文件推断这个值。

## 上传模式

| mode | 用途 | 返回 |
| --- | --- | --- |
| `article` | 正文插图 | 微信托管 URL，直接写进 `<img src>` |
| `material` | 封面（永久素材） | `media_id`，填进 `thumb_media_id` |
| `both` | 两者都要 | 同时返回 |

## 草稿 JSON

```json
{
  "title": "标题",
  "author": "作者",
  "digest": "摘要",
  "content_file": "article.html",
  "content_source_url": "",
  "thumb_media_id": "封面 media_id",
  "need_open_comment": 0,
  "only_fans_can_comment": 0
}
```

`content_file` 相对于 JSON 所在目录；也可以直接写 `"content": "<section>…</section>"`。`request_id` 不给时自动生成；同一 `request_id` 内容相同不会重复创建，内容不同返回 409。

修改草稿时 JSON 只需放变化的字段，服务端会先读微信端最新内容再合并。

## 安全

- 写操作超时或 5xx 之后不要自动重试；先 `draft-get` / `wechat-get` 核对远端状态，并沿用同一个 `request_id`。
- 删除必须带 `--confirm`。
- 微信没有正文图片的删除接口，删掉本地记录也无法让已发出去的图片 URL 失效。
- 不发布、不群发。
