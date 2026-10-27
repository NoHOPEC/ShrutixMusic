import asyncio

from pyrogram import Client
from pyrogram import errors as _errors
from pyrogram.enums import ChatMemberStatus

import config

from ..logging import LOGGER

assistants = []
assistantids = []

START_TIMEOUT = 60


def _collect_session_errors():
    names = (
        "AuthKeyUnregistered",
        "AuthKeyInvalid",
        "AuthKeyDuplicated",
        "SessionRevoked",
        "SessionExpired",
        "UserDeactivated",
        "UserDeactivatedBan",
    )
    found = []
    for name in names:
        cls = getattr(_errors, name, None)
        if isinstance(cls, type):
            found.append(cls)
    try:
        from pyrogram.session.session import AuthKeyNotFound

        found.append(AuthKeyNotFound)
    except Exception:
        pass
    return tuple(found)


SESSION_ERRORS = _collect_session_errors()


def remove_assistant(number: int):
    number = int(number)
    if number in assistants:
        index = assistants.index(number)
        assistants.pop(index)
        if index < len(assistantids):
            assistantids.pop(index)


class Userbot(Client):
    def __init__(self):
        self.one = Client(
            name="ShrutiXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            name="ShrutiXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.three = Client(
            name="ShrutiXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.four = Client(
            name="ShrutiXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.five = Client(
            name="ShrutiXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )

    def _slots(self):
        return (
            (1, self.one, config.STRING1),
            (2, self.two, config.STRING2),
            (3, self.three, config.STRING3),
            (4, self.four, config.STRING4),
            (5, self.five, config.STRING5),
        )

    async def _safe_disconnect(self, client):
        try:
            if client.is_connected:
                await asyncio.wait_for(client.disconnect(), timeout=10)
        except Exception:
            pass

    async def _in_logger_group(self, client):
        from ShrutixMusic import nand

        try:
            member = await nand.get_chat_member(config.LOGGER_ID, client.me.id)
        except Exception:
            return False
        if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            return False
        return True

    async def _notify_not_in_logger(self, number, client):
        from ShrutixMusic import nand

        text = (
            f"⚠️ <b>Assistant {number} is not in the logger group.</b>\n\n"
            f"<b>Name :</b> {client.me.mention}\n"
            f"<b>ID :</b> <code>{client.me.id}</code>\n\n"
            "The assistant has started and will keep working normally. "
            "Add it to this group if you want it to send logs here."
        )
        try:
            await nand.send_message(config.LOGGER_ID, text)
        except Exception as e:
            LOGGER(__name__).warning(
                f"Could not send the assistant {number} logger notice: {type(e).__name__}: {e}"
            )

    async def _start_assistant(self, number, client):
        try:
            await asyncio.wait_for(client.start(), timeout=START_TIMEOUT)
        except asyncio.TimeoutError:
            LOGGER(__name__).error(
                f"Assistant {number} did not start within {START_TIMEOUT}s. "
                "The session string is probably invalid or expired. Skipping it."
            )
            await self._safe_disconnect(client)
            return False
        except Exception as e:
            LOGGER(__name__).error(
                f"Assistant {number} failed to start ({type(e).__name__}: {e}). "
                "Check its session string. Skipping it."
            )
            await self._safe_disconnect(client)
            return False

        try:
            me = client.me
            client.id = me.id
            client.name = me.mention
            client.username = me.username
        except Exception as e:
            LOGGER(__name__).error(
                f"Assistant {number} could not load its account info ({type(e).__name__}: {e}). Skipping it."
            )
            await self._safe_disconnect(client)
            return False

        LOGGER(__name__).info(
            f"Assistant {number} ID: {client.id}, Username: {client.username}"
        )

        try:
            await client.join_chat("ShrutiBots")
            await client.join_chat("ShrutiSupportChat")
            LOGGER(__name__).info(f"Assistant {number} joined support chats")
        except Exception as e:
            LOGGER(__name__).warning(
                f"Assistant {number} failed to join support chats: {type(e).__name__}: {e}"
            )

        in_logger = await self._in_logger_group(client)
        if in_logger:
            try:
                await client.send_message(
                    config.LOGGER_ID, f"✅ Assistant {number} Started Successfully"
                )
            except Exception as e:
                LOGGER(__name__).warning(
                    f"Assistant {number} could not send a message to the logger group: {type(e).__name__}: {e}"
                )
        else:
            LOGGER(__name__).warning(
                f"Assistant {number} is not in the logger group. It will still work."
            )
            await self._notify_not_in_logger(number, client)

        assistants.append(number)
        assistantids.append(client.id)
        LOGGER(__name__).info(f"Assistant {number} Started as {client.name}")
        return True

    async def start(self):
        LOGGER(__name__).info("Starting Assistants...")

        if not config.LOGGER_ID:
            LOGGER(__name__).error("LOGGER_ID is not set in config!")
            exit()

        for number, client, string in self._slots():
            if not string:
                continue
            try:
                await self._start_assistant(number, client)
            except Exception as e:
                LOGGER(__name__).error(
                    f"Unexpected error while starting Assistant {number}: {type(e).__name__}: {e}"
                )
                await self._safe_disconnect(client)
                remove_assistant(number)

        if not assistants:
            LOGGER(__name__).error("No assistant could be started.")
        else:
            LOGGER(__name__).info(f"Active assistants: {assistants}")

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        for number, client, string in self._slots():
            if not string:
                continue
            try:
                await client.stop()
            except Exception:
                pass
