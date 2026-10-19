"""Narrow adapter to the existing authenticated BOSS CLI browser bridge."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1] / "source" / "boss-cli-main"
logger = logging.getLogger(__name__)


class BossBrowser:
    def __init__(self, session):
        self.session = session

    @classmethod
    def connected(cls):
        if str(CLI_ROOT) not in sys.path:
            sys.path.insert(0, str(CLI_ROOT))
        from boss_cli.browser_session import resolve_browser_session

        session = resolve_browser_session()
        if session is None or not session.account_key:
            raise RuntimeError("BOSS Chrome 连接未就绪或账号标识未核实")
        if not session.rpc("/status").get("allow_writes"):
            raise RuntimeError("BOSS 连接器当前为只读；请按说明以 --allow-writes 重启连接服务")
        return cls(session)

    def cards(self):
        self.session.navigate("recommend")
        cards = self.session.call("cards")
        result = []
        for card in cards:
            cid, name, body = card.get("geek_id"), card.get("name"), card.get("text")
            if (isinstance(cid, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", cid)
                    and isinstance(name, str) and name and isinstance(body, str) and body.strip()):
                result.append({"candidate_id": cid, "name": name, "text": body,
                               "source": "recommend_card", "coverage": "partial",
                               "captured_at": datetime.now(timezone(timedelta(hours=8))).isoformat()})
        if str(CLI_ROOT) not in sys.path:
            sys.path.insert(0, str(CLI_ROOT))
        from boss_cli.exceptions import BossApiError
        from boss_cli.precontact_abstract import (
            matching_resume_message,
            project_readable_resume,
        )

        for item in result:
            cid = item["candidate_id"]
            try:
                self.session.navigate("chat")
                self.session.navigate("recommend")
                if sum(card.get("geek_id") == cid for card in self.session.call("cards")) != 1:
                    continue
                self.session.call("open_profile", {"geek_id": cid})
                snapshot = self.session.call("profile_snapshot")
                matched = matching_resume_message(snapshot, cid)
                if matched:
                    readable = project_readable_resume(matched)
                    item["text"] += "\n" + json.dumps(readable, ensure_ascii=False)
                    item["source"] = "recommend_card+matched_abstract"
            except (BossApiError, RuntimeError, ValueError, KeyError) as exc:
                # Card remains a partial source; never invent missing detail.
                logger.warning("candidate %s has only card evidence: %s", cid, type(exc).__name__)
                continue
        return result

    def full_resume(self, candidate_id: str) -> dict:
        self.session.navigate("chat")
        self.session.navigate("recommend")
        # A refreshed page must still contain this exact candidate before opening details.
        cards = self.session.call("cards")
        if sum(card.get("geek_id") == candidate_id for card in cards) != 1:
            return {"candidate_id": candidate_id, "coverage": "partial", "source": "candidate_missing"}
        self.session.call("open_profile", {"geek_id": candidate_id})
        snapshot = self.session.call("profile_snapshot")
        full = snapshot.get("full_resume") if isinstance(snapshot, dict) else None
        if (isinstance(full, dict) and full.get("candidate_id") == candidate_id
                and full.get("coverage") == "complete" and full.get("verified") is True
                and full.get("sections_complete") is True and isinstance(full.get("text"), str)
                and full["text"].strip()):
            return {"candidate_id": candidate_id, "coverage": "complete", "text": full["text"],
                    "source": full.get("source", "precontact_verified")}
        return {"candidate_id": candidate_id, "coverage": "partial", "source": "precontact_detail_unverified"}

    def _write_ready(self):
        status = self.session.rpc("/status")
        if not status.get("allow_writes"):
            raise RuntimeError("BOSS 连接器未启用写操作")
        if not status.get("connected"):
            raise RuntimeError("BOSS 扩展已断开")

    def greet(self, candidate_id: str) -> bool:
        self._write_ready()
        self.session.navigate("chat")
        self.session.navigate("recommend")
        result = self.session.call("greet", {"geek_id": candidate_id})
        return isinstance(result, dict) and result.get("status") == "observed"

    def _relation(self, candidate_id: str) -> dict:
        if str(CLI_ROOT) not in sys.path:
            sys.path.insert(0, str(CLI_ROOT))
        from boss_cli.client import BossClient

        with BossClient(self.session) as client:
            for page in range(1, 6):
                items = client.get_boss_friend_list(page=page).get("result", [])
                matches = [item for item in items if item.get("encryptFriendId") == candidate_id]
                if len(matches) == 1:
                    relation = matches[0]
                    friend_id = relation.get("friendId")
                    if type(friend_id) is int and friend_id > 0:
                        details = client.get_boss_friend_details([friend_id]).get("friendList", [])
                        consistent = [item for item in details if item.get("friendId") == friend_id]
                        if len(consistent) == 1:
                            return {**relation, **consistent[0]}
                    return relation
                if len(matches) > 1:
                    raise RuntimeError("候选人会话不唯一")
                if not items:
                    break
        raise RuntimeError("打招呼后未找到与候选人 ID 对应的会话")

    def _history(self, friend_id: int) -> list[dict]:
        from boss_cli.client import BossClient

        with BossClient(self.session) as client:
            return client.get_boss_chat_history(gid=friend_id, count=50).get("messages", [])

    @staticmethod
    def _sent_message(history: list[dict], content: str) -> bool:
        for item in history:
            body = item.get("body")
            message = body if isinstance(body, str) else body.get("text", body.get("showText", "")) if isinstance(body, dict) else ""
            if item.get("received") is False and message.strip() == content:
                return True
        return False

    def send_first(self, candidate_id: str, message: str) -> bool:
        self._write_ready()
        for attempt in range(3):
            try:
                relation = self._relation(candidate_id)
                break
            except RuntimeError as exc:
                if "未找到与候选人 ID 对应的会话" not in str(exc) or attempt == 2:
                    raise
                time.sleep(2)
        friend_id = relation.get("friendId")
        uid = relation.get("uid")
        encrypted = relation.get("encryptFriendId")
        source = relation.get("friendSource")
        if (type(friend_id) is not int or friend_id <= 0 or type(uid) is not int or uid <= 0
                or encrypted != candidate_id or type(source) is not int):
            raise RuntimeError("会话身份字段不足，未发送首条消息")
        self.session.navigate("chat")
        if self._sent_message(self._history(friend_id), message):
            raise RuntimeError("历史消息中已有相同内容，需人工核查")
        result = self.session.call("chat_send", {"uid": uid, "encrypt_uid": encrypted,
                                                  "friend_source": source, "message": message})
        if not isinstance(result, dict) or result.get("invoked") is not True:
            return False
        for _ in range(5):
            if self._sent_message(self._history(friend_id), message):
                return True
            time.sleep(1)
        return False
