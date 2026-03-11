# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from mongoose.core.processing import ProcessingTopic
from mongoose.forward.base import BaseFormatter, BaseForwarder
from mongoose.models.configuration import DiscordForwarderConfiguration

logger = logging.getLogger(__name__)

# Discord embed limits (see Discord documentation)
MAX_EMBED_TITLE = 256
MAX_EMBED_DESCRIPTION = 4096
MAX_EMBED_FIELDS = 25
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024
MAX_EMBEDS = 10


def _truncate(text: Optional[str], max_len: int) -> str:
    """Truncate text to max_len, adding an ellipsis if truncated."""
    if text is None:
        return ""
    s = str(text)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


class DiscordFormatter(BaseFormatter):
    """Formats network events into Discord webhook payloads with embed size enforcement.

    The formatter tries to create informative embeds while respecting Discord's size
    limits. When an object contains many fields, only the most important are used,
    and long values are truncated.
    """

    @staticmethod
    def format(data: Any) -> Dict[str, Any]:
        """Return a Discord webhook JSON payload for the given model instance.

        Args:
            data: The model instance (e.g., NetworkAlert).

        Returns:
            A JSON-serializable dict following Discord webhook payload format.
        """
        try:
            payload = BaseFormatter.to_dict(data)

            title = "🚨 " + _truncate(payload.get("signature") or payload.get("category") or "Alert", MAX_EMBED_TITLE)
            description = _truncate(
                f"**{payload.get('src_ip')}:{payload.get('src_port')} -> {payload.get('dst_ip')}:{payload.get('dst_port')}**",
                MAX_EMBED_DESCRIPTION,
            )

            fields: List[Dict[str, str]] = []

            geoip = data.enrichment.get("geoip", None)
            if geoip:
                fields.append(
                    {
                        "name": _truncate("Country", MAX_FIELD_NAME),
                        "value": _truncate(geoip.get("country", "unknown"), MAX_FIELD_VALUE),
                        "inline": True,
                    }
                )
                fields.append(
                    {
                        "name": _truncate("Org.", MAX_FIELD_NAME),
                        "value": _truncate(geoip.get("asnOrganization", "unknown"), MAX_FIELD_VALUE),
                        "inline": True,
                    }
                )

            # Prioritized keys for fields
            keys = ["protocol", "action", "severity", "time"]
            for key in keys:
                if key in payload and len(fields) < MAX_EMBED_FIELDS:
                    fields.append(
                        {
                            "name": _truncate(key, MAX_FIELD_NAME),
                            "value": _truncate(payload.get(key), MAX_FIELD_VALUE),
                            "inline": True,
                        }
                    )

            # If there's useful extra data, add up to the field limit
            extra_keys = [k for k in payload.keys() if k not in keys and len(fields) < MAX_EMBED_FIELDS]
            for key in extra_keys:
                if len(fields) >= MAX_EMBED_FIELDS:
                    break
                value = payload.get(key)
                if not value:
                    continue
                fields.append(
                    {
                        "name": _truncate(key, MAX_FIELD_NAME),
                        "value": _truncate(f"{value}", MAX_FIELD_VALUE),
                        "inline": False,
                    }
                )

            embed = {"title": title, "description": description, "fields": fields}

            # assemble final payload
            discord_payload: Dict[str, Any] = {"embeds": [embed]}

            # Final guard: ensure embed counts and sizes
            if len(discord_payload["embeds"]) > MAX_EMBEDS:
                discord_payload["embeds"] = discord_payload["embeds"][:MAX_EMBEDS]

            # JSON-serializable
            return json.loads(json.dumps(discord_payload, default=str))
        except Exception as e:
            logger.exception("Failed to format data for Discord")
            return {"error": "formatting_failed", "details": str(e)}


class DiscordForwarder(BaseForwarder):
    """Sends payloads to Discord webhooks using the DiscordForwarderConfiguration.

    This class follows the project's forwarder retry semantics but customizes the
    retry logic: HTTP 4xx responses are considered non-retryable, 5xx and network
    errors are retryable according to the configured retry_count/retry_delay.
    """

    def __init__(self, config: DiscordForwarderConfiguration):
        super().__init__(
            [
                ProcessingTopic.ENRICHED_NETWORK_ALERT.value,
            ]
        )
        self.config = config
        self._session = self._setup_session()
        self.formatter = DiscordFormatter()

    def _setup_session(self) -> requests.Session:
        session = requests.Session()
        session.verify = self.config.verify_ssl
        session.headers.update({"User-Agent": "Mongoose-Discord-Forwarder/1.0", "Content-Type": "application/json"})
        session.headers.update(self.config.headers)
        # Apply username/avatar as part of each payload rather than header
        return session

    def _build_payload(self, data: Any) -> Dict[str, Any]:
        payload = self.formatter.format(data)
        # merge in username/avatar/allowed_mentions
        if self.config.username:
            payload["username"] = self.config.username
        if self.config.avatar_url:
            payload["avatar_url"] = self.config.avatar_url
        # allowed_mentions controls who gets pinged; default safe value is {"parse": []}
        payload["allowed_mentions"] = self.config.allowed_mentions
        return payload

    def forward(self, data: Any):
        payload = self._build_payload(data)
        # Attempt with retries for retryable errors
        attempts = self.config.retry_count + 1
        for attempt in range(attempts):
            try:
                resp = self._session.post(str(self.config.url), json=payload, timeout=self.config.timeout)
                status = getattr(resp, "status_code", 0)
                # Treat 2xx as success (Discord returns 204 for webhooks)
                if 200 <= status < 300:
                    return
                # 4xx -> don't retry
                if 400 <= status < 500:
                    resp.raise_for_status()
                # 5xx -> raise to trigger retry
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                is_retryable = True
                resp = getattr(e, "response", None)
                if resp is not None and 400 <= resp.status_code < 500:
                    is_retryable = False
                if not is_retryable or attempt + 1 >= attempts:
                    logger.error(f"Failed to send to Discord (attempt {attempt + 1}/{attempts}): {e}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {e}; retrying in {self.config.retry_delay}s")
                import time

                time.sleep(self.config.retry_delay)
