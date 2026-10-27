import inspect

from pyrogram import Client
from pyrogram.types import Message

try:
    from pyrogram.types import LinkPreviewOptions
except ImportError:
    LinkPreviewOptions = None


def _accepts(func, name):
    try:
        return name in inspect.signature(func).parameters
    except (TypeError, ValueError):
        return True


def _wrap(owner, attr):
    original = getattr(owner, attr, None)
    if original is None:
        return
    if getattr(original, "_preview_patched", False):
        return
    if _accepts(original, "disable_web_page_preview"):
        return
    if not _accepts(original, "link_preview_options"):
        return

    def wrapper(*args, **kwargs):
        if "disable_web_page_preview" in kwargs:
            disabled = kwargs.pop("disable_web_page_preview")
            if disabled and kwargs.get("link_preview_options") is None:
                kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
        return original(*args, **kwargs)

    wrapper._preview_patched = True
    wrapper.__name__ = getattr(original, "__name__", attr)
    wrapper.__doc__ = getattr(original, "__doc__", None)
    setattr(owner, attr, wrapper)


def patch_link_preview():
    if LinkPreviewOptions is None:
        return
    for attr in ("reply", "reply_text", "edit", "edit_text"):
        _wrap(Message, attr)
    for attr in ("send_message", "edit_message_text"):
        _wrap(Client, attr)


patch_link_preview()
