# QQ 小黄脸行内转换

把模型回复里的「/表情名」转换成 QQ 小黄脸（OneBot `face` 段），例如「在呢/汪汪」会发出「在呢」加一个汪汪表情。规则沿用 MaiBot SnowLuma 适配器：

- 表情前面紧挨英文字母、数字、`_`、`/`、`:` 时不转换（如 `666/赞`、网址）。
- 表情后面紧跟文字时不转换（如 `/赞说得好`），要先接一个标点。
- 只处理 aiocqhttp 平台上模型生成的回复，插件指令的输出不受影响。

表情名到 ID 的对照表 `qq_faces.py` 由 [Koishi QFace](https://github.com/koishijs/QFace) 的 [`_index.json`](https://koishi.js.org/QFace/assets/qq_emoji/_index.json) 生成，只收经典小黄脸和超级表情（骰子、接龙、Unicode emoji 需要特殊处理，没有收录）。QFace 使用 MIT 许可证，见 `LICENSE-QFace`。

## 许可证

MIT，见 `LICENSE`。

## 安装

把整个文件夹放到 AstrBot 的 `data/plugins/` 下（Docker 部署即宿主机的 `/opt/astrbot/data/plugins/`），然后在 WebUI「插件」页重载插件。

## 注意

不要同时开启 AstrBot 的「分段回复」：开启后每个消息段会单独发送，表情会和文字拆成两条消息。
