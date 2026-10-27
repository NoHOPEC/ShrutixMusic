import asyncio
import importlib
import logging
import re
import subprocess

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall, NodeJSNotRunning

import config
from ShrutixMusic import LOGGER, nand, userbot
from ShrutixMusic.core.call import Shruti
from ShrutixMusic.core.userbot import assistants
from ShrutixMusic.misc import sudo
from ShrutixMusic.plugins import ALL_MODULES
from ShrutixMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


class _EndedCallNoiseFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        if "SetVideoCallStatus" in message and "GROUPCALL_FORBIDDEN" in message:
            return False
        if "AuthKeyNotFound" in message:
            return False
        return True


logging.getLogger("asyncio").addFilter(_EndedCallNoiseFilter())


def check_node():
    try:
        out = subprocess.run(
            ["node", "-v"], capture_output=True, text=True, timeout=15
        ).stdout.strip()
    except Exception:
        LOGGER("ShrutixMusic").error(
            "Node.js is not installed. Install Node.js 20 and start the bot again."
        )
        exit()
    match = re.match(r"v?(\d+)", out)
    major = int(match.group(1)) if match else 0
    if major > 20 or major < 16:
        LOGGER("ShrutixMusic").warning(
            f"Node.js {out} detected. py-tgcalls 0.9.7 works reliably on Node.js 18 or 20, "
            "voice chat may fail with NodeJSNotRunning on other versions."
        )


async def init():
    check_node()
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await nand.start()
    for all_module in ALL_MODULES:
        importlib.import_module("ShrutixMusic.plugins" + all_module)
    LOGGER("ShrutixMusic.plugins").info("Successfully Imported Modules...")
    await userbot.start()
    if not assistants:
        LOGGER("ShrutixMusic").error(
            "No working assistant found. Check your session strings. Stopping Bot..."
        )
        exit()
    await Shruti.start()
    if not assistants:
        LOGGER("ShrutixMusic").error(
            "No assistant could start voice chat support. Stopping Bot..."
        )
        exit()
    try:
        await Shruti.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("ShrutixMusic").warning(
            "Videochat of your log group/channel is not running. Skipping the startup stream check."
        )
    except NodeJSNotRunning:
        LOGGER("ShrutixMusic").error(
            "Node.js is not running for py-tgcalls. Install Node.js 20 and restart the bot."
        )
    except Exception:
        pass
    await Shruti.decorators()
    LOGGER("ShrutixMusic").info(
    "\x53\x68\x72\x75\x74\x69\x78\x20\x4d\x75\x73\x69\x63\x20\x42\x6f\x74\x20\x53\x74\x61\x72\x74\x65\x64\x20\x53\x75\x63\x63\x65\x73\x73\x66\x75\x6c\x6c\x79\x2e\n\n\x44\x6f\x6e'\x74\x20\x66\x6f\x72\x67\x65\x74\x20\x74\x6f\x20\x76\x69\x73\x69\x74\x20\x40\x53\x68\x72\x75\x74\x69\x42\x6f\x74\x73"
)
    await idle()
    await nand.stop()
    await userbot.stop()
    LOGGER("ShrutixMusic").info("Stopping ShrutixMusic Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
