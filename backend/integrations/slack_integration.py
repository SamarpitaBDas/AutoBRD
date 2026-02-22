"""
slack_integration.py
─────────────────────
Slack integration with per-product message splitting.

When a Slack message discusses multiple products simultaneously, we:
  1. Split it into sentences
  2. Group sentences by which product they're most about
  3. Return one message dict PER PRODUCT containing only that product's sentences

This means downstream code (views.py) gets clean, product-scoped messages
instead of mixed content — each DataSource in the DB is about exactly one product.
"""

import os
from datetime import datetime, timedelta

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackIntegration:
    def __init__(self):
        self.token = os.getenv("SLACK_BOT_TOKEN")
        self.client = WebClient(token=self.token) if self.token else None
        self._extractor = None

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def fetch_messages(self, channel, days=30, limit=100, product_topic=None, all_products=None):
        """
        Fetch messages from a Slack channel.

        Args:
            channel      : Channel ID or name.
            days         : Days to look back.
            limit        : Max messages to fetch from Slack API.
            product_topic: Single product string — filter to this product only.
            all_products : List of product strings e.g. ['Product A', 'Product B'].
                           When set, each message is SPLIT by product and you get
                           back multiple dicts per original message (one per product
                           that has relevant content in that message).

        Returns:
            List of message dicts. When all_products is set, each dict includes
            'product_topic' showing which product it belongs to.
        """
        if not self.client:
            print("Slack client not initialised. Set SLACK_BOT_TOKEN.")
            return []

        raw_messages = []
        try:
            oldest = (datetime.now() - timedelta(days=days)).timestamp()
            result = self.client.conversations_history(
                channel=channel, oldest=str(oldest), limit=limit
            )
            for msg in result.get("messages", []):
                raw_messages.append(self._parse_message(msg, channel))
        except SlackApiError as e:
            print(f"Slack error: {e.response['error']}")

        return self._route_messages(raw_messages, product_topic, all_products)

    def fetch_thread(self, channel, thread_ts, product_topic=None, all_products=None):
        """Fetch thread messages with optional multi-product splitting."""
        if not self.client:
            return []

        raw_messages = []
        try:
            result = self.client.conversations_replies(channel=channel, ts=thread_ts)
            for msg in result.get("messages", []):
                raw_messages.append(self._parse_message(msg, channel))
        except SlackApiError as e:
            print(f"Slack error: {e.response['error']}")

        return self._route_messages(raw_messages, product_topic, all_products)

    def search_messages(self, query, count=100, product_topic=None, all_products=None):
        """Search messages across channels with optional multi-product splitting."""
        if not self.client:
            return []

        raw_messages = []
        try:
            result = self.client.search_messages(query=query, count=count)
            for match in result["messages"]["matches"]:
                raw_messages.append({
                    "ts": match["ts"],
                    "text": match.get("text", ""),
                    "user": match.get("user", ""),
                    "channel": match.get("channel", {}).get("id", ""),
                    "metadata": {
                        "permalink": match.get("permalink", ""),
                        "channel_name": match.get("channel", {}).get("name", ""),
                    },
                })
        except SlackApiError as e:
            print(f"Slack error: {e.response['error']}")

        return self._route_messages(raw_messages, product_topic, all_products)

    def get_channel_list(self):
        if not self.client:
            return []
        try:
            return self.client.conversations_list()["channels"]
        except SlackApiError as e:
            print(f"Slack error: {e.response['error']}")
            return []

    def get_user_info(self, user_id):
        if not self.client:
            return {}
        try:
            return self.client.users_info(user=user_id)["user"]
        except SlackApiError as e:
            print(f"Slack error: {e.response['error']}")
            return {}

    # ── ROUTING ───────────────────────────────────────────────────────────────

    def _route_messages(self, raw_messages, product_topic, all_products):
        """
        Dispatch raw messages through the right filter path:
          - all_products set  → split each message by product (multi-product mode)
          - product_topic set → keep only sentences about that one product
          - neither set       → return messages unchanged
        """
        if all_products:
            return self._split_by_all_products(raw_messages, all_products)
        elif product_topic:
            return [m for m in
                    (self._apply_single_product_filter(msg, product_topic) for msg in raw_messages)
                    if m is not None]
        else:
            return raw_messages

    # ── MULTI-PRODUCT SPLITTING ───────────────────────────────────────────────

    def _split_by_all_products(self, messages, all_products):
        """
        For each raw message, produce one output dict per product that has
        relevant content in that message.  A single Slack message discussing
        three products becomes three separate dicts, each containing only the
        sentences that belong to that product.
        """
        extractor = self._get_extractor()
        output = []

        for msg in messages:
            text = msg.get("text", "").strip()
            if not text:
                continue

            for product in all_products:
                focused = extractor.get_product_sentences(text, product, threshold=0.28)
                if not focused or len(focused.split()) < 4:
                    continue  # this message has nothing about this product

                product_msg = dict(msg)
                product_msg["text"] = focused
                product_msg["metadata"] = dict(msg.get("metadata", {}))
                product_msg["metadata"]["product_topic"] = product
                product_msg["metadata"]["original_text"] = text
                product_msg["metadata"]["multi_product_split"] = True
                product_msg["product_topic"] = product
                output.append(product_msg)

        return output

    # ── SINGLE-PRODUCT FILTER ─────────────────────────────────────────────────

    def _apply_single_product_filter(self, message, product_topic):
        """Keep only sentences about product_topic; drop message if nothing remains."""
        text = message.get("text", "").strip()
        if not text:
            return None

        extractor = self._get_extractor()
        focused = extractor.get_product_sentences(text, product_topic)

        if not focused or len(focused.split()) < 4:
            return None

        filtered = dict(message)
        filtered["text"] = focused
        filtered["metadata"] = dict(message.get("metadata", {}))
        filtered["metadata"]["product_topic"] = product_topic
        filtered["metadata"]["original_text"] = text
        filtered["metadata"]["product_relevance_filtered"] = True
        return filtered

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _parse_message(self, message, channel):
        return {
            "ts": message["ts"],
            "text": message.get("text", ""),
            "user": message.get("user", ""),
            "channel": channel,
            "metadata": {
                "type": message.get("type", ""),
                "subtype": message.get("subtype", ""),
                "reactions": message.get("reactions", []),
                "thread_ts": message.get("thread_ts", ""),
            },
        }

    def _get_extractor(self):
        if self._extractor is None:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from ml_models.requirement_extractor import RequirementExtractor
            self._extractor = RequirementExtractor()
        return self._extractor
