from dataclasses import asdict
from enum import Enum
import os
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Union

from agno.tools import Toolkit
from openilink import Client, TypingStatus, UploadMediaType

from openfox.tools.config import ConfigTools
from openfox.utils.const import OPENFOX_HOME_PATH


BUF_FILE = Path(OPENFOX_HOME_PATH / "channels" / "wxclaw" / "sync_buf.dat")
TOKEN_FILE = Path(OPENFOX_HOME_PATH / "channels" / "wxclaw" / "bot_token.dat")


class WxClawTools(Toolkit):
    """WeChat iLink toolkit based on openilink SDK only."""

    def __init__(self, **kwargs: Any):
        self.config_tools = ConfigTools()
        BUF_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

        tools = [
            self.send_text,
            self.upload_file,
        ]
        super().__init__(
            name="wxclaw",
            tools=tools,
            instructions=['If user_id contains "im.wechat", use WxClawTools'],
            add_instructions=True,
            **kwargs,
        )

    @staticmethod
    def load_file(path: Path) -> str:
        try:
            return path.read_text().strip()
        except FileNotFoundError:
            return ""

    def _refresh(self) -> None:
        self.token = self.load_file(TOKEN_FILE)
        self.client = Client(token=self.token)

    @staticmethod
    def _format_text(text: str, italics: bool) -> str:
        if italics:
            return "\n".join([f"_{line}_" for line in text.split("\n")])
        return text

    def send_text(
        self,
        user_id: str,
        context_token: str,
        text: str,
        italics: bool = False,
    ) -> Dict[str, Any]:
        """Send plain text to a user through the openilink (WeChat iLink) client.

        Refreshes the SDK client from disk token before sending. Long payloads are
        split so each API call stays within typical channel limits (same idea as
        the WhatsApp helper in this codebase).

        Args:
            user_id: Target user identifier for the conversation.
            context_token: Session/context token from the inbound message (required
                to correlate the outbound text with the right chat).
            text: Full message body; may be arbitrarily long (see batching below).
            italics: When True, each line is wrapped with underscores so the client
                can render italics (line-based, split on newlines).

        Returns:
            If ``len(text) <= 4096``: ``{"client_id": "<id>"}`` from a single send.
            Otherwise: ``{"client_ids": [...], "count": N}`` — one client id per
            chunk; chunks are 4000 chars with a ``[i/N]`` prefix so the user sees
            ordering across parts.

        Note:
            Batching uses 4000-character segments when over 4096 total characters
            so each part plus the index prefix stays under common size limits.
        """
        self._refresh()

        def _send_one(message: str) -> str:
            return self.client.send_text(user_id, message, context_token)

        config = self.client.get_config(user_id, context_token)
        self.client.send_typing(user_id, config.typing_ticket)

        # Same batching style as WhatsApp helper: single send if <=4096 chars;
        # else split into 4000-char slices and prefix each with [i/N].
        if len(text) <= 4096:
            client_id = _send_one(self._format_text(text, italics=italics))
            return {"client_id": client_id}

        message_batches = [text[i : i + 4000] for i in range(0, len(text), 4000)]
        client_ids: list[str] = []
        for i, batch in enumerate(message_batches, 1):
            batch_message = f"[{i}/{len(message_batches)}] {batch}"
            client_ids.append(_send_one(self._format_text(batch_message, italics=italics)))

        self.client.send_typing(user_id, config.typing_ticket, TypingStatus.CANCEL)
        return {"client_ids": client_ids, "count": len(client_ids)}

    def upload_file(
        self,
        file_path: str,
        user_id: str,
        context_token: str,
        media_type: Union[int, UploadMediaType] = UploadMediaType.FILE,
    ) -> Dict[str, Any]:
        """Upload local file via openilink ``Client.upload_file`` and send to the user.

        SDK flow: read bytes → AES encrypt → CDN upload → ``send_image`` / ``send_video`` /
        ``send_file_attachment`` with ``context_token``. See openilink ``Client.upload_file``.
        """
        self._refresh()
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        media_enum = (
            media_type if isinstance(media_type, UploadMediaType) else UploadMediaType(media_type)
        )
        if media_enum == UploadMediaType.VOICE:
            raise ValueError(
                "media_type=VOICE is not supported for upload+send: openilink Client has no "
                "send_voice helper; use FILE or IMAGE as appropriate."
            )
        
        sdk_media = UploadMediaType(media_enum.value)
        plaintext = path.read_bytes()
        uploaded = self.client.upload_file(plaintext, user_id, sdk_media)
        file_name = path.name
        config = self.client.get_config(user_id, context_token)
        self.client.send_typing(user_id, config.typing_ticket)

        if media_enum == UploadMediaType.IMAGE:
            client_id = self.client.send_image(user_id, context_token, uploaded)
        elif media_enum == UploadMediaType.VIDEO:
            client_id = self.client.send_video(user_id, context_token, uploaded)
        else:
            client_id = self.client.send_file_attachment(
                user_id, context_token, file_name, uploaded
            )
        self.client.send_typing(user_id, config.typing_ticket, TypingStatus.CANCEL)
        
        return {
            "client_id": client_id,
            "upload_result": asdict(uploaded),
            "file_name": file_name,
            "media_type": media_enum.value,
        }
