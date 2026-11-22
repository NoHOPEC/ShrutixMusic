import math
import random
import re

from pyrogram import enums, errors, types

from ShrutixMusic.misc import db
from ShrutixMusic.utils.database import get_lang, is_autoplay
from ShrutixMusic.utils.formatters import seconds_to_min, time_to_seconds
from strings import get_string

_TAG_RE = re.compile(r"<(/?)(b|a|code)(?:\s+href=([^>]+))?>", re.IGNORECASE)

_consumed = set()

_FORBIDDEN = (errors.ChatSendPhotosForbidden, errors.ChatSendMediaForbidden)


async def _lang(chat_id):
    return get_string(await get_lang(chat_id))


def _parse_inline(segment):
    parts = []
    stack = []
    pos = 0

    for m in _TAG_RE.finditer(segment):
        if m.start() > pos:
            parts.append(segment[pos : m.start()])
        pos = m.end()

        closing, tag, href = m.group(1), m.group(2).lower(), m.group(3)

        if not closing:
            stack.append((tag, href.strip("\"'") if href else None, len(parts)))
        elif stack and stack[-1][0] == tag:
            open_tag, url, start = stack.pop()
            inner = parts[start:]
            del parts[start:]
            inner = inner[0] if len(inner) == 1 else inner if inner else ""
            if open_tag == "b":
                parts.append(types.RichTextBold(text=inner))
            elif open_tag == "code":
                parts.append(types.RichTextCode(text=inner))
            else:
                parts.append(types.RichTextUrl(text=inner, url=url))

    if pos < len(segment):
        parts.append(segment[pos:])

    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else parts


def _balance_lines(caption_html):
    lines = []
    carry = False
    for line in caption_html.split("\n"):
        if not line:
            lines.append(line)
            continue
        if carry:
            line = "<b>" + line
        opened = len(re.findall(r"<b>", line, re.IGNORECASE))
        closed = len(re.findall(r"</b>", line, re.IGNORECASE))
        carry = opened > closed
        if carry:
            line += "</b>"
        lines.append(line)
    return lines


def _html_caption_to_blocks(caption_html):
    return [
        types.InputRichBlockParagraph(text=_parse_inline(line))
        for line in _balance_lines(caption_html)
    ]


def _progress_line(played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    percentage = (played_sec / duration_sec) * 100 if duration_sec else 0
    umm = math.floor(percentage)
    if 0 < umm <= 10:
        bar = "◉—————————"
    elif 10 < umm < 20:
        bar = "—◉————————"
    elif 20 <= umm < 30:
        bar = "——◉———————"
    elif 30 <= umm < 40:
        bar = "———◉——————"
    elif 40 <= umm < 50:
        bar = "————◉—————"
    elif 50 <= umm < 60:
        bar = "—————◉————"
    elif 60 <= umm < 70:
        bar = "——————◉———"
    elif 70 <= umm < 80:
        bar = "———————◉——"
    elif 80 <= umm < 95:
        bar = "————————◉—"
    else:
        bar = "—————————◉"
    return f"{played}  {bar}  {dur}"


_BUTTON_STYLES = [
    enums.ButtonStyle.DEFAULT,
    enums.ButtonStyle.PRIMARY,
    enums.ButtonStyle.SUCCESS,
    enums.ButtonStyle.DANGER,
]


def _random_styles():
    styles = list(_BUTTON_STYLES)
    styles.append(random.choice(_BUTTON_STYLES))
    styles.append(random.choice(_BUTTON_STYLES))
    random.shuffle(styles)
    return styles


def _progress_row(played, dur, style):
    return types.InputRichBlockButtons(
        buttons=[
            types.RichMessageButton(
                text=_progress_line(played, dur),
                style=style,
                callback_data="GetTimer",
            )
        ]
    )


def _queue_len(chat_id):
    tracks = db.get(chat_id)
    return max(len(tracks) - 1, 0) if tracks else 0


def _control_rows(_, chat_id, playing, styles, autoplay_on, end_style):
    replay_style, toggle_style, skip_style, queue_style = styles
    toggle = (
        types.RichMessageButton(
            text=_["RICH_BTN_PAUSE"],
            style=toggle_style,
            callback_data=f"ADMIN Pause|{chat_id}",
        )
        if playing
        else types.RichMessageButton(
            text=_["RICH_BTN_RESUME"],
            style=toggle_style,
            callback_data=f"ADMIN Resume|{chat_id}",
        )
    )
    return [
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text=_["RICH_BTN_REPLAY"],
                    style=replay_style,
                    callback_data=f"ADMIN Replay|{chat_id}",
                ),
                toggle,
                types.RichMessageButton(
                    text=_["RICH_BTN_SKIP"],
                    style=skip_style,
                    callback_data=f"ADMIN Skip|{chat_id}",
                ),
            ]
        ),
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text=_["RICH_BTN_QUEUE"].format(_queue_len(chat_id)),
                    style=queue_style,
                    callback_data=f"nowplaying_queue {chat_id}",
                ),
                types.RichMessageButton(
                    text=_["RICH_BTN_END_QUEUE"],
                    style=end_style,
                    callback_data=f"ADMIN Stop|{chat_id}",
                ),
            ]
        ),
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text=_["RICH_BTN_AUTOPLAY_ON"] if autoplay_on else _["RICH_BTN_AUTOPLAY_OFF"],
                    style=enums.ButtonStyle.SUCCESS if autoplay_on else enums.ButtonStyle.DEFAULT,
                    callback_data=f"nowplaying_autoplay {chat_id}",
                ),
            ]
        ),
    ]


def build_now_playing_blocks(
    _, photo, caption_html, chat_id, played=None, dur=None, playing=True, autoplay_on=False
):
    blocks = [types.InputRichBlockPhoto(photo=types.InputMediaPhoto(photo))]
    blocks += _html_caption_to_blocks(caption_html)
    styles = _random_styles()
    if played and dur:
        blocks.append(_progress_row(played, dur, styles[4]))
    blocks += _control_rows(_, chat_id, playing, styles[:4], autoplay_on, styles[5])
    return blocks


def _message_key(message):
    return (message.chat.id, message.id)


def _strip_photo(blocks):
    return [b for b in blocks if not isinstance(b, types.InputRichBlockPhoto)]


async def _edit_rich(message, blocks):
    try:
        return await message.edit_text(
            rich_message=types.InputRichMessage(blocks=blocks)
        )
    except _FORBIDDEN:
        plain = _strip_photo(blocks)
        if len(plain) == len(blocks):
            raise
        return await message.edit_text(
            rich_message=types.InputRichMessage(blocks=plain)
        )


async def _try_deliver(client, target_chat_id, blocks, replace):
    rich = types.InputRichMessage(blocks=blocks)
    if replace is not None:
        try:
            edited = await replace.edit_text(rich_message=rich)
        except _FORBIDDEN:
            raise
        except Exception:
            try:
                await replace.delete()
            except Exception:
                pass
        else:
            _consumed.add(_message_key(replace))
            return edited or replace
    return await client.send_rich_message(target_chat_id, rich_message=rich)


async def _deliver(client, target_chat_id, blocks, replace=None):
    try:
        return await _try_deliver(client, target_chat_id, blocks, replace)
    except _FORBIDDEN:
        plain = _strip_photo(blocks)
        if len(plain) == len(blocks):
            raise
        return await _try_deliver(client, target_chat_id, plain, replace)


def caption_blocks(caption_html):
    return _html_caption_to_blocks(caption_html)


async def edit_rich(message, blocks):
    return await _edit_rich(message, blocks)


async def deliver_rich(client, target_chat_id, blocks, replace=None):
    result = await _deliver(client, target_chat_id, blocks, replace)
    if replace is not None:
        _consumed.discard(_message_key(replace))
    return result


async def release_mystic(mystic):
    if mystic is None:
        return
    key = _message_key(mystic)
    if key in _consumed:
        _consumed.discard(key)
        return
    try:
        await mystic.delete()
    except Exception:
        pass


def _classic_now_playing_markup(_, chat_id, playing, autoplay_on, played=None, dur=None):
    rows = []
    if played and dur:
        rows.append(
            [
                types.InlineKeyboardButton(
                    _progress_line(played, dur), callback_data="GetTimer"
                )
            ]
        )
    rows.extend(
        [
            [
                types.InlineKeyboardButton(
                    _["RICH_BTN_REPLAY"], callback_data=f"ADMIN Replay|{chat_id}"
                ),
                types.InlineKeyboardButton(
                    _["RICH_BTN_PAUSE"] if playing else _["RICH_BTN_RESUME"],
                    callback_data=f"ADMIN {'Pause' if playing else 'Resume'}|{chat_id}",
                ),
                types.InlineKeyboardButton(
                    _["RICH_BTN_SKIP"], callback_data=f"ADMIN Skip|{chat_id}"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    _["RICH_BTN_QUEUE"].format(_queue_len(chat_id)),
                    callback_data=f"nowplaying_queue {chat_id}",
                ),
                types.InlineKeyboardButton(
                    _["RICH_BTN_END_QUEUE"], callback_data=f"ADMIN Stop|{chat_id}"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    _["RICH_BTN_AUTOPLAY_ON"] if autoplay_on else _["RICH_BTN_AUTOPLAY_OFF"],
                    callback_data=f"nowplaying_autoplay {chat_id}",
                )
            ],
        ]
    )
    return types.InlineKeyboardMarkup(rows)


async def _deliver_classic(
    client, target_chat_id, caption, reply_markup, photo=None, replace=None
):
    if replace is not None:
        try:
            if photo is not None:
                if getattr(replace, "photo", None):
                    edited = await replace.edit_caption(
                        caption=caption, reply_markup=reply_markup
                    )
                    _consumed.add(_message_key(replace))
                    return edited or replace
                await replace.delete()
            else:
                edited = await replace.edit_text(
                    text=caption, reply_markup=reply_markup
                )
                _consumed.add(_message_key(replace))
                return edited or replace
        except _FORBIDDEN:
            if photo is None:
                raise
        except Exception:
            try:
                await replace.delete()
            except Exception:
                pass

    if photo is not None:
        try:
            return await client.send_photo(
                target_chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
            )
        except _FORBIDDEN:
            pass
    return await client.send_message(
        target_chat_id,
        text=caption,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


async def send_now_playing_rich(
    client, chat_id, target_chat_id, photo, caption_html, replace=None
):
    _ = await _lang(chat_id)
    markup = _classic_now_playing_markup(
        _, chat_id, True, await is_autoplay(chat_id)
    )
    msg = await _deliver_classic(
        client, target_chat_id, caption_html, markup, photo=photo, replace=replace
    )
    if db.get(chat_id):
        db[chat_id][0]["np_photo"] = photo
        db[chat_id][0]["np_caption"] = caption_html
    return msg

def build_queue_blocks(_, caption_html, chat_id, qid):
    blocks = _html_caption_to_blocks(caption_html)
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text=_["RICH_BTN_PLAYNOW"],
                    style=enums.ButtonStyle.SUCCESS,
                    callback_data=f"ADMIN PlayNow|{chat_id}_{qid}",
                ),
            ]
        )
    )
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text=_["RICH_BTN_SKIP"],
                    style=enums.ButtonStyle.PRIMARY,
                    callback_data=f"ADMIN Skip|{chat_id}",
                ),
                types.RichMessageButton(
                    text=_["RICH_BTN_END"],
                    style=enums.ButtonStyle.DANGER,
                    callback_data=f"ADMIN Stop|{chat_id}",
                ),
            ]
        )
    )
    return blocks


async def send_queue_rich(
    client, chat_id, target_chat_id, caption_html, qid, replace=None
):
    _ = await _lang(chat_id)
    markup = types.InlineKeyboardMarkup(
        [
            [
                types.InlineKeyboardButton(
                    _["RICH_BTN_PLAYNOW"],
                    callback_data=f"ADMIN PlayNow|{chat_id}_{qid}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    _["RICH_BTN_SKIP"], callback_data=f"ADMIN Skip|{chat_id}"
                ),
                types.InlineKeyboardButton(
                    _["RICH_BTN_END"], callback_data=f"ADMIN Stop|{chat_id}"
                ),
            ],
        ]
    )
    return await _deliver_classic(
        client, target_chat_id, caption_html, markup, replace=replace
    )

async def _edit_now_playing(mystic, caption_html, markup):
    if getattr(mystic, "photo", None):
        return await mystic.edit_caption(caption=caption_html, reply_markup=markup)
    return await mystic.edit_text(text=caption_html, reply_markup=markup)


async def update_now_playing_progress(mystic, chat_id, played, dur, playing=True):
    info = db.get(chat_id)
    if not info:
        return None
    caption_html = info[0].get("np_caption")
    if not caption_html:
        return None
    _ = await _lang(chat_id)
    markup = _classic_now_playing_markup(
        _, chat_id, playing, await is_autoplay(chat_id), played, dur
    )
    return await _edit_now_playing(mystic, caption_html, markup)


async def set_now_playing_state(chat_id, playing):
    info = db.get(chat_id)
    if not info:
        return None
    mystic = info[0].get("mystic")
    caption_html = info[0].get("np_caption")
    if not mystic or not caption_html:
        return None
    played = seconds_to_min(info[0].get("played", 0)) or None
    dur = info[0].get("dur")
    _ = await _lang(chat_id)
    markup = _classic_now_playing_markup(
        _, chat_id, playing, await is_autoplay(chat_id), played, dur
    )
    try:
        return await _edit_now_playing(mystic, caption_html, markup)
    except Exception:
        return None
