# wechat-article-claude

微信公众号文章的 Claude Code Skill：**只管微信平台的渲染边界和草稿投递，文章怎么写交回给模型。**

这是 [juneme/wechat-article-designer](https://github.com/juneme/wechat-article-designer) 的精简适配版，配套服务端为 [juneme/wechat-console-server](https://github.com/juneme/wechat-console-server)。

## 为什么精简

原版是给 Codex 写的，`SKILL.md` 里有大量关于"不许用模板、不许套主题、不许给设计理由、不许固定工作流"的流程禁令。这些条款本质上是在替模型做设计决策，占用了本该用于写作的注意力。

精简版把文章的内容、结构、视觉风格完全交回模型，只保留两件无法自行推断的事：

1. 微信会删掉哪些 HTML/CSS、图片必须怎么引用；
2. 草稿投递的通信协议。

## 与原版的差异

| 项目 | 原版 | 本版 |
| --- | --- | --- |
| 配对 | `pair-ui` 本地 Tkinter 窗口（330 行，含 Canvas 品牌图）+ `pair` | 仅 `pair`，终端隐藏输入 |
| 临时图片 | `temp-upload` / `temp-list` | 移除，与发文无关 |
| 发布流水线 | `build_release.py`、2 个 GitHub Actions | 移除 |
| Codex 元数据 | `agents/openai.yaml` | 移除 |
| 设计条款 | 数百字流程禁令 | 移除，改为自由发挥 |
| 客户端体积 | 26.9 KB | 13.2 KB |
| 配对文件 | `~/.codex/yunoe/client.json` | 优先沿用该文件，不存在时写 `~/.claude/yunoe/client.json` |

**已有的原版配对可以直接用，不必重新配对。**

## 安装

把整个目录放进 Claude Code 的 skill 目录：

```bash
cp -r wechat-article-claude ~/.claude/skills/wechat-article
```

重启会话后通过 `/wechat-article` 调用，或直接说"写一篇公众号文章"。

## 结构

```
SKILL.md                     写作与投递的入口，不含版式规定
references/
  wechat-format.md           微信会删什么、图片怎么引用、正文片段格式
  typography.md              手机中文可读性下限（下限，不是风格）
  client.md                  命令总表与安全语义
scripts/
  wechat_article.py          配对 / 上传 / 草稿增删改查
```

## 用法

```bash
python ~/.claude/skills/wechat-article/scripts/wechat_article.py status
```

未配对时：

```bash
python ~/.claude/skills/wechat-article/scripts/wechat_article.py pair --server https://<控制台地址>
```

投递顺序：封面按 `--mode material` 上传取 `media_id` → 正文图按 `--mode article` 上传取 URL → `draft-create` → `draft-get` 回读核对。

## 边界

- 只写草稿箱，不发布、不群发。
- 验证码只在终端隐藏输入，不进对话也不进命令行参数。
- 客户端令牌不打印、不写日志、不进版本库。
- 写操作超时或 5xx 后不自动重试，先核对远端状态。

## License

MIT，见 [LICENSE](LICENSE)。原作品版权归 juneme。
