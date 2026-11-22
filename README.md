# QQ 小黄脸行内转换

AstrBot 插件。把模型回复里的两种标记转换成 QQ 消息段：

| 模型写 | 发出去 |
| --- | --- |
| `在呢/汪汪` | 「在呢」+ 汪汪小黄脸 |
| `[@123456] 你看看` | @ QQ 号 123456 +「你看看」 |

小黄脸的规则沿用 MaiBot SnowLuma 适配器：

- 表情前面紧挨英文字母、数字、`_`、`/`、`:` 时不转换（如 `666/赞`、网址）。
- 表情后面紧跟文字时不转换（如 `/赞说得好`），要先接一个标点。

@ 的规则：

- 只接受纯数字 QQ 号，不能 @ 全体成员。
- 群聊里转换成 @；私聊里 @ 没有意义，标记会被直接去掉。

只处理 aiocqhttp 平台上模型生成的回复，插件指令的输出不受影响。没有配置项。要让模型用上这些标记，需要在人格提示词里写明用法。

## 安装

在 AstrBot WebUI「插件」页用仓库地址安装：

```text
https://github.com/happycola233/astrbot_plugin_qq_face_inline
```

或者把整个文件夹放到 AstrBot 的 `data/plugins/` 下，再重启 AstrBot。

## 注意

不要同时开启 AstrBot 的「分段回复」：开启后每个消息段会单独发送，表情和 @ 会和文字拆成几条消息。

## 数据来源与许可证

表情名到 ID 的对照表 `qq_faces.py` 由 [Koishi QFace](https://github.com/koishijs/QFace) 的 [`_index.json`](https://koishi.js.org/QFace/assets/qq_emoji/_index.json) 生成，只收经典小黄脸和超级表情（骰子、接龙、Unicode emoji 需要特殊处理，没有收录）。QFace 使用 MIT 许可证，见 `LICENSE-QFace`。

本插件使用 MIT 许可证，见 `LICENSE`。
