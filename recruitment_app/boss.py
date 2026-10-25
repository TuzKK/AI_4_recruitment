"""Narrow adapter to the existing authenticated BOSS CLI browser bridge."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1] / "source" / "boss-cli-main"
logger = logging.getLogger(__name__)


def fresh_resume_message(snapshot, candidate_id, opened_at):
    """Use only the newest identity-matched event from this profile opening."""
    matches = []
    for frame in snapshot.get("frames", []):
        for message in (frame.get("resumeTap") or {}).get("messages", []):
            data = (message.get("data") or {}).get("abstractData")
            at = message.get("at", 0)
            if (message.get("type") == "IFRAME_DONE" and isinstance(data, dict)
                    and data.get("encryptGeekId") == candidate_id
                    and isinstance(at, (int, float)) and at >= opened_at):
                matches.append((at, data))
    if not matches:
        return None
    latest = max(at for at, _ in matches)
    data = [d for at, d in matches if at == latest]
    return data[0] if all(d == data[0] for d in data) else None


class GreetingNotSent(RuntimeError):
    """Failure proven to occur before a greeting click was dispatched."""


class CandidateUnavailable(GreetingNotSent):
    """The candidate disappeared before any write; other candidates may continue."""


class BossBrowser:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _connection():
        os.environ.setdefault('BOSS_BRIDGE_FILE', str(CLI_ROOT / '.runtime' / 'browser-bridge.json'))
        if str(CLI_ROOT) not in sys.path:
            sys.path.insert(0, str(CLI_ROOT))
        from boss_cli.browser_session import browser_connection
        return browser_connection()

    @classmethod
    def connection_status(cls):
        return cls._connection().rpc('/status', timeout=2)

    @classmethod
    def configure_connection(cls, limits):
        connection = cls._connection()
        status = connection.rpc('/status', timeout=2)
        if not status.get('connected') or status.get('rate_limit_version') != 1:
            raise RuntimeError('请启动新版连接服务，并重载、连接0.2.26或更新版本扩展后运行（统一限速尚未就绪）')
        connection.rpc('/rate-settings', limits, timeout=2)

    @classmethod
    def connected(cls):
        # The bridge launcher writes here; direct Python launches need the same defaults.
        os.environ.setdefault('BOSS_BRIDGE_FILE', str(CLI_ROOT / '.runtime' / 'browser-bridge.json'))
        os.environ.setdefault('BOSS_TRANSPORT', 'browser')
        if str(CLI_ROOT) not in sys.path:
            sys.path.insert(0, str(CLI_ROOT))
        from boss_cli.browser_session import resolve_browser_session

        session = resolve_browser_session()
        if session is None:
            raise RuntimeError("BOSS 浏览器会话未启用；请检查 BOSS_TRANSPORT 是否被设置为 cookie")
        if not session.account_key:
            raise RuntimeError("BOSS 页面已连接，但未识别招聘账号；请在招聘端页面刷新后重试")
        if not session.rpc("/status").get("allow_writes"):
            raise RuntimeError("BOSS 连接器当前为只读；请按说明以 --allow-writes 重启连接服务")
        return cls(session)

    def _loaded_cards(self):
        # Logged-in navigation can finish before the asynchronous list renders.
        for attempt in range(11):
            cards = self.session.call("cards")
            if not isinstance(cards, list):
                raise RuntimeError("BOSS 候选人列表返回格式异常")
            if cards:
                return cards
            if attempt < 10:
                time.sleep(1)
        raise RuntimeError("推荐页面未读取到候选人；请检查列表是否加载、职位筛选条件或页面验证后重试")

    def cards(self):
        return list(self.iter_cards(load_more=False))

    def iter_cards(self, *, load_more=True, scan_limit=200):
        """Process captured cards, then load more; each ID is yielded once per pass."""
        self.end_reason = None
        self.session.navigate("recommend")
        cards = self._loaded_cards()
        seen = set(getattr(self, 'skip_candidate_ids', ()))
        loaded_ids = set()
        scanned = 0
        idle = 0
        while True:
            page_ids = {c.get("geek_id") for c in cards if c.get("geek_id")}
            loading_progress = bool(page_ids - loaded_ids)
            loaded_ids.update(page_ids)
            fresh = [c for c in cards if c.get("geek_id") not in seen]
            for item in self._card_batch(fresh):
                cid = item["candidate_id"]
                if cid in seen:
                    continue
                seen.add(cid)
                scanned += 1
                idle = 0
                yield item
                if scanned >= scan_limit:
                    self.end_reason = "scan_limit"
                    return
            if not load_more:
                return
            if not fresh:
                # A resumed run may need to scroll past many already-screened
                # pages before reaching new candidates. Loading them is progress.
                idle = 0 if loading_progress else idle + 1
            if idle >= 3:
                self.end_reason = "no_more_candidates"
                return
            # Contact/fine screening may have moved to chat. Navigate only if
            # needed; never deliberately refresh the recommendation list.
            self.session.navigate("recommend")
            cards = self.session.call("cards", {"advance": True})
            if not isinstance(cards, list):
                raise RuntimeError("BOSS 候选人列表返回格式异常")
            time.sleep(1)

    def _card_batch(self, cards):
        result = []
        for card in cards:
            cid, name, body = card.get("geek_id"), card.get("name"), card.get("text")
            if (isinstance(cid, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", cid)
                    and isinstance(name, str) and name and isinstance(body, str) and body.strip()):
                result.append({"candidate_id": cid, "name": name, "text": body,
                               "source": "recommend_card", "coverage": "partial",
                               "captured_at": datetime.now(timezone(timedelta(hours=8))).isoformat()})
        if cards and not result:
            raise RuntimeError("已读取推荐卡片，但候选人标识、姓名或正文均未通过校验；请检查页面结构")
        if str(CLI_ROOT) not in sys.path:
            sys.path.insert(0, str(CLI_ROOT))
        from boss_cli.exceptions import BossApiError
        from boss_cli.precontact_abstract import (
            project_readable_resume,
        )

        for item in result:
            cid = item["candidate_id"]
            try:
                self.session.navigate("recommend")
                self.session.call("cards", {"close_profile": True})
                if sum(card.get("geek_id") == cid for card in self._loaded_cards()) != 1:
                    # The recommendation list can rotate after navigation. Keep
                    # the captured card for screening, but never open another
                    # candidate's profile as a substitute.
                    raise RuntimeError("推荐列表已变化，保留原卡片参与粗筛，不读取其他人的详情")
                opened_at = int(time.time() * 1000)
                self.session.call("open_profile", {"geek_id": cid})
                matched = None
                for attempt in range(6):
                    snapshot = self.session.call("profile_snapshot")
                    matched = fresh_resume_message(snapshot, cid, opened_at)
                    if matched:
                        break
                    if attempt < 5:
                        time.sleep(0.4)
                if matched:
                    readable = project_readable_resume(matched)
                    item["text"] += "\n" + json.dumps(readable, ensure_ascii=False)
                    item["source"] = "recommend_card+matched_abstract"
            except (BossApiError, RuntimeError, ValueError, KeyError) as exc:
                if getattr(exc, 'rate_limited', False):
                    raise
                # Card remains a partial source; never invent missing detail.
                logger.warning("candidate %s has only card evidence: %s", cid, type(exc).__name__)
            # Never leave a detail overlay in front of the greeting/next card.
            self.session.call("cards", {"close_profile": True})
            yield item

    def full_resume(self, candidate_id: str) -> dict:
        self.session.navigate("chat")
        self.session.navigate("recommend")
        # A refreshed page must still contain this exact candidate before opening details.
        cards = self._loaded_cards()
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

    def contacted_resume(self, candidate_id: str) -> dict:
        """Read the authenticated online profile bound to the contacted relation."""
        from boss_cli.client import BossClient
        from boss_cli.resume_export import render_resume

        partial = {"candidate_id": candidate_id, "coverage": "partial", "source": "postcontact_waiting"}
        self.session.navigate("chat")
        relation = self._relation(candidate_id)
        job_id = relation.get("encryptJobId")
        if (relation.get("encryptFriendId") != candidate_id or
                not isinstance(job_id, str) or not job_id):
            return partial
        with BossClient(self.session) as client:
            data = client.get_boss_view_geek(encrypt_geek_id=candidate_id,
                                            encrypt_job_id=job_id,
                                            security_id=relation.get("securityId") or "")
        detail = data.get("geekDetailInfo") if isinstance(data, dict) else None
        if (not isinstance(detail, dict) or not isinstance(detail.get("geekBaseInfo"), dict)
                or data.get("hiddenResume") not in (None, False, 0)):
            return partial
        for obj in (data, detail, detail["geekBaseInfo"]):
            for key in ("encryptGeekId", "encryptFriendId", "encryptUid"):
                if obj.get(key) and obj[key] != candidate_id:
                    return partial
            if any(obj.get(key) is True for key in ("isMasked", "isTruncated", "needExchange")):
                return partial
        project_key = "geekProjExpList" if "geekProjExpList" in detail else "geekProjectExpList"
        sections = ("geekWorkExpList", "geekEduExpList", project_key)
        if not all(isinstance(detail.get(key), list) for key in sections):
            return partial
        if not any(detail[key] for key in sections):
            return partial
        return {"candidate_id": candidate_id, "coverage": "complete",
                "text": render_resume({"geekDetailInfo": detail}, candidate_id, job_id),
                "source": "postcontact_online_profile"}

    def _write_ready(self):
        status = self.session.rpc("/status")
        if not status.get("allow_writes"):
            raise RuntimeError("BOSS 连接器未启用写操作")
        if not status.get("connected"):
            raise RuntimeError("BOSS 扩展已断开")

    def greet(self, candidate_id: str) -> bool:
        self.last_greeting_result = None
        try:
            self._write_ready()
            self.session.navigate("recommend")
            cards = self._loaded_cards()
            matches = sum(card.get("geek_id") == candidate_id for card in cards)
            if matches == 0:
                raise CandidateUnavailable("目标候选人已不在当前推荐列表，未点击打招呼")
            if matches != 1:
                raise RuntimeError("当前页面目标候选人不存在或不唯一")
        except CandidateUnavailable:
            raise
        except Exception as exc:
            raise GreetingNotSent(f"发送前检查失败，未点击打招呼：{exc}") from exc
        try:
            result = self.session.call("greet", {"geek_id": candidate_id})
        except Exception as exc:
            # Exact connector errors that are emitted strictly before button.click().
            if getattr(exc, 'not_dispatched', False):
                raise GreetingNotSent(str(exc)) from exc
            if getattr(exc, 'rate_limited', False):
                raise
            reason = str(exc).removesuffix('；若已执行写动作，请核实，不要直接重发')
            if reason in {"候选人卡片缺失或重复，未发送", "打招呼按钮不可用或不唯一，未发送",
                            "请先打开牛人推荐页面", "缺少候选人 ID"}:
                raise GreetingNotSent(reason) from exc
            result = {"status": "unknown", "candidate_id": candidate_id, "error": reason}
        if not isinstance(result, dict):
            result = {"status": "unknown", "candidate_id": candidate_id,
                      "error": "浏览器未返回执行结果，无法判定是否点击"}
        self.last_greeting_result = result
        if result.get("candidate_id") not in (None, candidate_id):
            raise RuntimeError("打招呼回执候选人身份不匹配，结果待核实")
        if (result.get("status") == "not_sent" and result.get("clicked") is False
                and any(c.get("label") == "继续沟通" for c in result.get("controls", []) if isinstance(c, dict))):
            raise CandidateUnavailable("该候选人已建立会话，跳过首次打招呼，不占用新名额")
        if result.get("status") in {"not_sent", "ready"}:
            raise GreetingNotSent(result.get("error") or "仅完成预检查，尚未点击打招呼")
        if result.get("status") == "observed":
            return True
        # Do not click again when the UI acknowledgement or transport response
        # is missing. An exact candidate-bound chat relation is independent proof.
        relation_error = None
        for attempt in range(3):
            try:
                relation = self._relation(candidate_id)
                if (relation.get("encryptFriendId") == candidate_id
                        and type(relation.get("friendId")) is int and relation["friendId"] > 0):
                    self.last_greeting_result = {**result, "status": "observed",
                                                 "verification": "chat_relation"}
                    return True
            except Exception as exc:
                relation_error = str(exc)[:180]
            if attempt < 2:
                time.sleep(1)
        reason = result.get("error") or "首次打招呼未得到明确回执"
        if relation_error:
            reason += f"；会话核查：{relation_error}"
        raise RuntimeError(reason)

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
                        consistent = [item for item in details
                                      if (item.get("friendId") == friend_id or item.get("uid") == friend_id)
                                      and item.get("encryptUid", candidate_id) == candidate_id
                                      and item.get("encryptFriendId", candidate_id) == candidate_id]
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
    def _sent_message(history: list[dict], content: str, recipient_uid: int, account_key: str) -> bool:
        for item in history:
            body = item.get("body")
            message = body if isinstance(body, str) else body.get("text", body.get("showText", "")) if isinstance(body, dict) else ""
            sender, recipient = item.get("from"), item.get("to")
            if not isinstance(sender, dict) or not isinstance(recipient, dict):
                continue
            sender_uid = sender.get("uid")
            if type(sender_uid) is not int or sender_uid <= 0 or recipient.get("uid") != recipient_uid:
                continue
            own_sender = any(hashlib.sha256(f"{key}:{sender_uid}".encode()).hexdigest() == account_key
                             for key in ("uid", "userId"))
            if own_sender and isinstance(message, str) and message.strip() == content:
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
        account_key = self.session.account_key
        if self._sent_message(self._history(friend_id), message, uid, account_key):
            raise RuntimeError("历史消息中已有相同内容，需人工核查")
        dispatch_error = None
        try:
            self.session.call("chat_send", {"uid": uid, "encrypt_uid": encrypted,
                                           "friend_source": source, "message": message})
        except Exception as exc:
            # A lost response can follow a successful send. Only re-read history.
            if getattr(exc, 'not_dispatched', False) or getattr(exc, 'rate_limited', False):
                raise
            dispatch_error = exc
        for _ in range(5):
            if self._sent_message(self._history(friend_id), message, uid, account_key):
                return True
            time.sleep(1)
        if dispatch_error:
            raise dispatch_error
        return False
