---
name: wechat-article
description: 写微信公众号文章并写入草稿箱。用户说“写篇公众号文章/排版成公众号能发的样子/发到公众号草稿箱”时使用。只负责微信平台的渲染边界与投稿通信，文章的内容、结构、视觉风格由模型自行决定。
---

# 微信公众号文章

这个 skill 只管两件事：**写**和**投递**。怎么写不设模板、不套主题、不规定流程——按这篇内容本身需要的样子来。

## 1. 写作

没有预设版式。标题层级、段落节奏、留白、配色、配图、强调方式，都由你根据内容、读者和用途自己决定。同一主题写两篇，长得不一样是对的。

必须守住的只有两处，其余全部自由：

- [references/wechat-format.md](references/wechat-format.md) — 微信会删掉什么、图片怎么引用、正文片段长什么样。这是硬约束，写的时候就要遵守，不是最后再补。
- [references/typography.md](references/typography.md) — 手机上的可读性下限。是下限，不是风格。

写作要求：

- 不编造事实、数据、人物、头衔、日期、结论、机构背书。素材不够就问，或者不写那一句。
- 成品要能脱离这次对话独立成立。正文里不留提示词、设计说明、文件路径、工具输出、审批口吻。
- 正文里的每一部分都要对读者有用。花哨的装饰如果只是装饰，删掉。

## 2. 产出：一个 HTML 片段

正文是**片段**（`<section>…</section>` 或若干段落标签），不是带 `<html><head>` 的完整文档。

- 所有样式写在元素的 `style` 属性里。
- 不用 `<style>` 块、外链 CSS、外链字体、`<script>`、`<iframe>`、表单、事件属性。
- 宽度跟着栏目走，手机上不能横向滚动、不能被裁切、文字不能压在背景上看不清。
- 动画、SVG 之类的东西可以有，但不能承载关键信息——被清理后仍要读得通。

在项目目录里存一份 `article.html`，内容就是将要提交的那段正文原文。提交前用窄屏宽度看一眼；提交后从草稿箱读回来对一遍，以真实草稿在手机上的样子为准。

## 3. 投递：进草稿箱，不发布

只写草稿箱。不点发布、不群发、不自动重试写操作。

脚本的绝对路径是 `~/.claude/skills/wechat-article/scripts/wechat_article.py`。下面的命令都在**用户的项目目录**里执行，所以用绝对路径，不要写成相对当前目录的路径：

```bash
python "C:/Users/Administrator/.claude/skills/wechat-article/scripts/wechat_article.py" status
```

未配对时先配对（验证码只在终端里隐藏输入，不要贴进对话，也不要写进命令行参数）：

```bash
python "C:/Users/Administrator/.claude/skills/wechat-article/scripts/wechat_article.py" pair --server https://控制台地址
```

配对信息与旧版共用 `~/.codex/yunoe/client.json`；没有该文件时写入 `~/.claude/yunoe/client.json`。已有的配对直接可用，不必重新配对。

投递顺序：

1. **封面** → `image-upload --mode material 封面.png` → 取返回的 `media_id`，作为 `thumb_media_id`。封面是必填项。
2. **正文图** → `image-upload --mode article 图.png` → 取返回的 `https://mmbiz.qpic.cn/...` 地址直接写进 `<img src>`。本地路径、data URL、外部链接都不行。
3. **建草稿** → 写一个 JSON（`title` / `author` / `digest` / `content_file` / `thumb_media_id`；`content_file` 相对于 JSON 所在目录），然后 `draft-create --json 该文件`。
4. **回读核对** → `draft-get <id>` 或 `wechat-get <media_id>`，确认缩进、字号、字重、行高、图片都还在。被清掉的样式用内联 CSS 补回去，不要用空格字符硬凑。

## 4. 命令

全部命令见 [references/client.md](references/client.md)。下表省略了脚本路径前缀，实际调用时补上。常用：

| 用途 | 命令 |
| --- | --- |
| 检查连接 | `status` |
| 首次配对 | `pair --server URL` |
| 上传图片 | `image-upload --mode article\|material FILES...` |
| 建草稿 | `draft-create --json FILE` |
| 读回草稿 | `draft-get ID` / `wechat-get MEDIA_ID` |
| 改草稿 | `draft-update ID --json FILE` |
| 删草稿 | `draft-delete ID --confirm` |
