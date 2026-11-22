"""QQ message enhancements for AstrBot on the aiocqhttp (OneBot v11) platform.

Incoming messages: speech-to-text results get a "[语音]" tag and merged
forwards are expanded into text, so the model knows what it is reading.
Model replies: inline "/表情名", "[@QQ号]" and "[分段]" markers become QQ
faces, @ mentions and separately sent messages.
"""

import asyncio
import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import (
    At,
    Face,
    Forward,
    Plain,
    Record,
    Reply,
)
from astrbot.api.star import Context, Star, register

from .qq_faces import QQ_FACE_IDS

VOICE_TAG = "[语音] "

# The model writes "[分段]" where a new message should start.
SPLIT_PATTERN = re.compile(r"\s*\[分段\]\s*")
# Replies longer than this are sent whole. Long explanations should not be
# split, and AngelHeart turns 800+ character replies into an image, where a
# leftover marker would be visible.
MAX_SPLIT_REPLY_CHARS = 300

# Nested forwards are expanded this many levels deep; the whole expansion is
# cut at FORWARD_MAX_CHARS so a huge chat log cannot flood the context.
FORWARD_MAX_DEPTH = 2
FORWARD_MAX_CHARS = 3000
FORWARD_TIMEOUT_SECONDS = 10
FORWARD_SEGMENT_TEXT = {
    "image": "[图片]",
    "face": "[表情]",
    "mface": "[表情包]",
    "record": "[语音]",
    "video": "[视频]",
    "json": "[卡片消息]",
    "xml": "[卡片消息]",
    "poke": "[戳一戳]",
    "forward": "[合并转发]",
    "reply": "",
}

# "[分段]" splits the reply. "[@123456]" becomes an @ mention; only plain QQ
# numbers are accepted, so the model cannot @ everyone, and one trailing space
# is eaten because the aiocqhttp adapter already puts a space after every @.
# "/name" follows the MaiBot SnowLuma adapter rule: it is a face only when it
# is not glued to a letter, digit, "_", "/" or ":" before it (keeps URLs and
# "666/赞" as text) and no word character follows it ("/赞说得好" stays text).
# Longer face names are tried first so "/大哭" is not cut short by "/大".
MARKER_PATTERN = re.compile(
    r"(?P<split>\s*\[分段\]\s*)"
    r"|\[@(?P<qq>\d{5,12})\] ?"
    r"|(?<![A-Za-z0-9_/:])/(?P<face>"
    + "|".join(re.escape(name) for name in sorted(QQ_FACE_IDS, key=len, reverse=True))
    + r")(?!\w)"
)


@register(
    "astrbot_plugin_qq_message_plus",
    "happycola233",
    "QQ 消息增强：标记语音转写、展开合并转发，把模型回复里的小黄脸、@ 和分段标记转成真正的 QQ 消息",
    "2.0.0",
)
class QQMessagePlus(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=100)
    async def enrich_incoming(self, event: AstrMessageEvent):
        """Tag voice transcripts and expand merged forwards before other plugins.

        Runs after AstrBot's speech-to-text and before AngelHeart (priority
        -10), so the chat record and the model both see the result.
        self-learning collects messages at a higher priority and therefore
        keeps learning from the untouched message.

        Args:
            event: The incoming message event.
        """
        if event.get_platform_name() != "aiocqhttp":
            return
        chain = event.get_messages()
        raw = event.message_obj.raw_message
        segments = raw.get("message") if isinstance(raw, dict) else None
        added_text = ""

        # QQ voice messages carry nothing else, so after a successful
        # speech-to-text the only text in the chain is the transcript.
        had_voice = isinstance(segments, list) and any(
            isinstance(seg, dict) and seg.get("type") == "record" for seg in segments
        )
        if had_voice and not any(isinstance(comp, Record) for comp in chain):
            for index, comp in enumerate(chain):
                if isinstance(comp, Plain) and comp.text.strip():
                    if not comp.text.startswith(VOICE_TAG):
                        chain[index] = Plain(VOICE_TAG + comp.text)
                        event.message_str = VOICE_TAG + event.message_str
                        event.message_obj.message_str = (
                            VOICE_TAG + event.message_obj.message_str
                        )
                    break

        for index, comp in enumerate(chain):
            if not isinstance(comp, Forward) or not comp.id:
                continue
            lines = await self._expand_forward(event.bot, str(comp.id), 1, [0])
            text = "[合并转发]\n" + "\n".join(lines) + "\n[合并转发结束]"
            chain[index] = Plain(text)
            added_text += text

        if added_text:
            event.message_str += added_text
            event.message_obj.message_str += added_text

    async def _expand_forward(
        self, bot, forward_id: str, depth: int, used_chars: list[int]
    ) -> list[str]:
        """Fetch a merged forward through SnowLuma and render it as text lines.

        Args:
            bot: The aiocqhttp bot used to call the OneBot API.
            forward_id: The forward resource ID from the forward segment.
            depth: Nesting level of this forward, starting at 1.
            used_chars: One-element list holding the characters already
                produced across all levels, shared so the cap is global.

        Returns:
            One "nickname: content" line per message, indented for nested
            forwards, or a single line explaining why nothing was fetched.
        """
        try:
            data = await asyncio.wait_for(
                bot.call_action("get_forward_msg", id=forward_id),
                timeout=FORWARD_TIMEOUT_SECONDS,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to fetch merged forward {forward_id}: {e}")
            return ["（内容获取失败）"]

        lines = []
        for node in (data or {}).get("messages") or []:
            if used_chars[0] >= FORWARD_MAX_CHARS:
                lines.append("……（后面还有，太长已省略）")
                break
            sender = node.get("sender") or {}
            name = (
                sender.get("card")
                or sender.get("nickname")
                or str(node.get("user_id") or "未知")
            )
            message = node.get("message") or []
            if isinstance(message, str):
                message = [{"type": "text", "data": {"text": message}}]
            parts = []
            nested = []
            for seg in message:
                kind = seg.get("type")
                seg_data = seg.get("data") or {}
                if kind == "text":
                    parts.append(seg_data.get("text", ""))
                elif kind == "at":
                    parts.append(f"@{seg_data.get('name') or seg_data.get('qq', '')}")
                elif kind == "file":
                    parts.append(
                        f"[文件: {seg_data.get('name') or seg_data.get('file', '')}]"
                    )
                elif kind == "markdown":
                    parts.append(seg_data.get("content", ""))
                elif kind == "forward" and depth < FORWARD_MAX_DEPTH:
                    parts.append("[合并转发]")
                    nested = await self._expand_forward(
                        bot, str(seg_data.get("id", "")), depth + 1, used_chars
                    )
                else:
                    parts.append(FORWARD_SEGMENT_TEXT.get(kind, f"[{kind}]"))
            line = f"{name}: {''.join(parts).strip()}"
            used_chars[0] += len(line)
            lines.append(line)
            lines.extend(f"  {inner}" for inner in nested)
        return lines or ["（空）"]

    @filter.on_decorating_result(priority=300)
    async def drop_unusable_splits(self, event: AstrMessageEvent):
        """Turn "[分段]" into line breaks when the reply must stay whole.

        Runs before AngelHeart (priority 200) builds its long-reply image, so
        a marker never ends up inside the image or on another platform.

        Args:
            event: The event whose reply is about to be sent.
        """
        result = event.get_result()
        if result is None or not result.is_llm_result():
            return
        plains = [comp for comp in result.chain if isinstance(comp, Plain)]
        if not any(SPLIT_PATTERN.search(comp.text) for comp in plains):
            return
        reply_chars = sum(len(SPLIT_PATTERN.sub("", comp.text)) for comp in plains)
        if (
            event.get_platform_name() == "aiocqhttp"
            and reply_chars <= MAX_SPLIT_REPLY_CHARS
        ):
            return
        for comp in plains:
            comp.text = SPLIT_PATTERN.sub("\n", comp.text).strip("\n")

    @filter.on_decorating_result()
    async def convert_markers(self, event: AstrMessageEvent):
        """Turn reply markers into QQ faces, @ mentions and separate messages.

        Only model replies on the aiocqhttp platform are touched, so plugin
        command output keeps its literal text. "[@QQ号]" becomes an @ in
        group chats and is removed in private chats, where an @ has no
        meaning. Every part before the last "[分段]" is sent right away with a
        short typing pause; the last part stays in the result so AstrBot and
        other plugins finish sending it as usual.

        Args:
            event: The event whose reply is about to be sent.
        """
        if event.get_platform_name() != "aiocqhttp":
            return
        result = event.get_result()
        if result is None or not result.is_llm_result():
            return
        in_group = bool(event.get_group_id())

        segments = [[]]
        for comp in result.chain:
            if not isinstance(comp, Plain) or not MARKER_PATTERN.search(comp.text):
                segments[-1].append(comp)
                continue
            cursor = 0
            for match in MARKER_PATTERN.finditer(comp.text):
                if match.start() > cursor:
                    segments[-1].append(Plain(comp.text[cursor : match.start()]))
                if match.group("split") is not None:
                    segments.append([])
                elif match.group("face"):
                    segments[-1].append(Face(id=QQ_FACE_IDS[match.group("face")]))
                elif in_group:
                    segments[-1].append(At(qq=match.group("qq")))
                cursor = match.end()
            if cursor < len(comp.text):
                segments[-1].append(Plain(comp.text[cursor:]))

        # A part holding only a quote or an @ (for example "[#3][分段]...")
        # is carried into the next part instead of being sent on its own.
        parts = []
        carried = []
        for segment in segments:
            segment = carried + segment
            if any(
                not isinstance(comp, (Reply, At))
                and not (isinstance(comp, Plain) and not comp.text.strip())
                for comp in segment
            ):
                parts.append(segment)
                carried = []
            else:
                carried = segment
        if not parts:
            result.chain = carried
            return
        parts[-1].extend(carried)

        for index, part in enumerate(parts):
            if index:
                chars = sum(len(comp.text) for comp in part if isinstance(comp, Plain))
                await asyncio.sleep(min(3.0, 0.6 + 0.08 * chars))
            if index == len(parts) - 1:
                result.chain = part
                break
            try:
                await event.send(MessageChain(chain=part))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to send a split reply part: {e}")
