"""Pipeline Orchestrator – connects all 5 modules into a single automated flow.

Flow: Position Analysis → RPA Browser → Search & Greet → Resume Analysis → Contact Follow-up
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from analyzer.position_analyzer import analyze_position
from communicator.chat_manager import analyze_reply, generate_followup
from communicator.contact_followup import generate_contact_request, process_contact_reply
from communicator.matcher import pre_match_candidate
from communicator.resume_collector import collect_resume
from database.db import SessionLocal
from database.models import (
    Candidate,
    ChatMessage,
    ContactInfo,
    Position,
    RecruitTask,
    Resume,
)
from pipeline.events import *
from pipeline.events import PipelineEvent
from pipeline.task_manager import TaskControl
from resume_analysis.extractor import extract_resume_info
from resume_analysis.parser import parse_resume
from resume_analysis.scorer import generate_report, score_resume
from resume_analysis.storage import save_resume_to_db
from rpa.chrome_connection import browser_mode
from database.models import BossAccount
from utils.config import get_config, get_qualified_threshold

logger = logging.getLogger(__name__)

# Type alias for the event callback
EventCallback = Callable[[PipelineEvent], Coroutine[Any, Any, None]]


class RecruitPipeline:
    """Orchestrates the full recruitment automation pipeline."""

    def __init__(
        self,
        task_id: int,
        control: TaskControl,
        emit: EventCallback,
    ) -> None:
        self.task_id = task_id
        self.control = control
        self.emit = emit
        self.app_engine = None
        self.actions = None
        self.browser_mode = browser_mode(get_config())
        self.progress = {
            "searched": 0,
            "pre_matched": 0,
            "greeted": 0,
            "replied": 0,
            "resume_received": 0,
            "scored": 0,
            "qualified": 0,
            "contact_obtained": 0,
        }

    async def run(self) -> None:
        """Execute the full pipeline."""
        db = SessionLocal()
        try:
            task = db.get(RecruitTask, self.task_id)
            if not task:
                raise ValueError(f"Task {self.task_id} not found")

            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()

            position = db.get(Position, task.position_id)
            if not position:
                raise ValueError(f"Position {task.position_id} not found")

            config = json.loads(task.config_json) if task.config_json else {}
            if self.browser_mode:
                from rpa.browser_engine import BrowserEngine
                from rpa import page_actions
                account = db.get(BossAccount, config.get('account_id'))
                if not account or not account.cdp_url or not account.target_id:
                    raise RuntimeError('请先在设置中接入 BOSS 账号，并为任务选择账号')
                if account.connection_type == 'extension':
                    from rpa.extension_bridge import ExtensionEngine
                    from rpa import extension_actions
                    self.app_engine = ExtensionEngine(account.cdp_url, account.target_id)
                    self.actions = extension_actions
                else:
                    self.app_engine = BrowserEngine(account.cdp_url, account.target_id)
                    self.actions = page_actions
            else:
                from rpa.mac_app_engine import MacAppEngine
                from rpa import mac_ax_actions
                self.app_engine = MacAppEngine()
                self.actions = mac_ax_actions
            daily_limit = config.get("greeting_daily_limit", 80)
            threshold = config.get("qualified_threshold", get_qualified_threshold())

            await self.emit(PipelineEvent(TASK_STARTED, f"任务启动: {position.title}"))

            # ── Step 1: Position Analysis ──
            await self.emit(PipelineEvent(STEP1_START, "正在分析职位..."))

            jd_data = json.loads(position.jd_json) if position.jd_json != "{}" else None
            if not jd_data:
                analysis = await asyncio.to_thread(analyze_position, position.title, position.description)
                position.jd_json = json.dumps(analysis.jd.model_dump(), ensure_ascii=False)
                position.keywords_json = json.dumps(
                    {**analysis.keywords.model_dump(), "filters": analysis.filters.model_dump()},
                    ensure_ascii=False,
                )
                position.scorecard_json = json.dumps(analysis.scorecard.model_dump(), ensure_ascii=False)
                db.commit()
                jd_data = analysis.jd.model_dump()

            # Build enriched JD text: JD + keywords + scorecard criteria
            jd_enriched = dict(jd_data) if jd_data else {}
            keywords_data = json.loads(position.keywords_json) if position.keywords_json else {}
            scorecard_data = json.loads(position.scorecard_json) if position.scorecard_json else {}
            jd_enriched["primary_keywords"] = keywords_data.get("primary_keywords", [])
            jd_enriched["skill_keywords"] = keywords_data.get("skill_keywords", [])
            jd_enriched["must_have_skills"] = keywords_data.get("filters", {}).get("must_have_skills", [])
            jd_enriched["scorecard"] = scorecard_data
            jd_summary = json.dumps(jd_enriched, ensure_ascii=False, indent=2)
            scorecard_text = position.scorecard_json

            await self.emit(PipelineEvent(STEP1_DONE, "职位分析完成"))

            # ── Step 2: Launch BOSS app ──
            await self._check_control()
            await self.emit(PipelineEvent(STEP2_START, "正在连接所选 BOSS 账号..."))

            device = await self.app_engine.launch()

            await self.emit(PipelineEvent(STEP2_DONE, "BOSS 账号已连接"))

            # ── Login check — wait for user to log in if needed ──
            await self._check_control()

            # Wire notify callback so login prompt reaches the frontend
            self.actions.set_notify_callback(
                lambda event, msg: self.emit(PipelineEvent(WARNING, msg))
            )

            # ── Step 3: Scan recommend page → AI score → greet qualified ──
            await self._check_control()
            await self.emit(PipelineEvent(STEP3_SEARCHING, "正在打开推荐牛人页面..."))

            greeting_count = 0
            qualified_threshold = config.get("qualified_threshold", threshold)

            # Navigate to recommend (handles login if needed, only navigates ONCE)
            await self.actions.ensure_logged_in(device)

            # ── Batch scan + reverse-order greet ──
            # Strategy: scan ONCE (~77s) → sort cards by greet index DESC →
            # process from highest index (bottom of page) to lowest →
            # indices don't shift when bottom cards are greeted.
            # Only rescan after all cards in current batch are done + scrolled.
            processed_geek_ids: set[str] = set()
            scroll_attempts = 0
            max_scroll_attempts = 10  # Safety limit

            while (self.progress["pre_matched"] < 70 and greeting_count < daily_limit
                   and scroll_attempts < max_scroll_attempts):
                if self.control.should_stop:
                    break
                await self._check_control()

                # ── ONE scan for this batch ──
                await self.emit(PipelineEvent(
                    STEP3_SEARCHING, "正在扫描推荐牛人列表 (~1分钟)...",
                ))
                cards = await self.actions.get_candidate_cards(device, force_refresh=True)

                if not cards:
                    scroll_attempts += 1
                    await self.actions.scroll_to_load_more(device)
                    await asyncio.sleep(3)
                    continue

                # Sort by greet_btn_index DESCENDING → process bottom cards first
                cards.sort(key=lambda c: c.get("greet_btn_index", 0), reverse=True)

                self.progress["searched"] += len(cards)
                await self.emit(PipelineEvent(
                    STEP3_SEARCHING,
                    f"扫描完成: {len(cards)} 张卡（从下往上处理，索引不乱）",
                ))

                # ── Process ALL cards in this batch ──
                for card_idx, card in enumerate(cards):
                    if self.control.should_stop:
                        break
                    await self._check_control()

                    geek_id = card.get("geek_id", "")
                    name = card.get("name", "未知")

                    if geek_id in processed_geek_ids:
                        continue
                    processed_geek_ids.add(geek_id)

                    if self.progress["pre_matched"] >= 70 or greeting_count >= daily_limit:
                        break

                    # ── AI 初筛 ──
                    profile_text = json.dumps(card, ensure_ascii=False)
                    await self.emit(PipelineEvent(
                        STEP3_SEARCHING,
                        f"初筛: {name}... ({card_idx + 1}/{len(cards)})",
                    ))

                    match_result = await asyncio.to_thread(pre_match_candidate, jd_summary, profile_text)
                    await self._check_control()
                    score = match_result.get("score", 0)
                    self.progress["pre_matched"] += 1

                    # Save
                    candidate = Candidate(
                        task_id=self.task_id,
                        position_id=position.id,
                        name=name,
                        boss_id=geek_id,
                        boss_profile_json=profile_text,
                        pre_match_score=score,
                        status="found",
                    )
                    db.add(candidate)
                    db.commit()
                    db.refresh(candidate)

                    await self.emit(PipelineEvent(
                        STEP3_CANDIDATE_FOUND,
                        f"{name} — {score}分",
                        {"candidate_id": candidate.id, "score": score},
                    ))

                    # ── 硬性筛选：城市 + 车企经验 ──
                    skip_reason = None

                    # 检查1: 期望城市必须是合肥（检查期望城市字段+全卡片文本）
                    expect_city = card.get("expect_city", "")
                    search_text = card.get("_search_text", "")
                    combined = f"{expect_city} {search_text}"
                    if not self.browser_mode and "合肥" not in combined:
                        skip_reason = f"城市不符({expect_city})"

                    # 检查2: 必须有车企/汽车行业经验
                    if not self.browser_mode and not skip_reason and not _has_auto_experience(card):
                        skip_reason = "无车企经验"

                    if skip_reason:
                        candidate.status = "rejected"
                        db.commit()
                        await self._emit_progress()
                        await self.emit(PipelineEvent(
                            STEP3_CANDIDATE_FOUND,
                            f"{name} — {score}分 — ❌ {skip_reason}",
                            {"candidate_id": candidate.id, "score": score},
                        ))
                        await self.actions.random_delay(0.5, 1.5)
                        continue

                    if score < qualified_threshold:
                        candidate.status = "rejected"
                        db.commit()
                        await self._emit_progress()
                        await self.actions.random_delay(0.5, 1.5)
                        continue

                    # ── 打招呼 ──
                    await self.emit(PipelineEvent(
                        WARNING, f"{name} 通过({score}分)，打招呼...",
                    ))

                    await self._check_control()
                    greet_idx = card.get("greet_btn_index")
                    success = await self.actions.click_greet_button(
                        device, geek_id, greet_btn_index=greet_idx,
                    )
                    if success:
                        await asyncio.sleep(1.5)
                        dismissed = await self.actions.dismiss_greet_dialog(device)
                        await asyncio.sleep(1.5)

                        greeting_count += 1
                        candidate.status = "greeted"
                        db.add(ChatMessage(
                            candidate_id=candidate.id,
                            direction="sent",
                            content="打招呼 (系统自动)",
                            message_type="greeting",
                        ))
                        db.commit()
                        self.progress["greeted"] += 1

                        await self.emit(PipelineEvent(
                            STEP3_GREETING_SENT,
                            f"已打招呼: {name} ({greeting_count}/{daily_limit})",
                            {"candidate_id": candidate.id, "greeting_count": greeting_count},
                        ))

                    # 批次暂停（防检测）
                    throttle = get_config().get("throttle", {})
                    batch_size = throttle.get("batch_pause_count", 5)
                    if greeting_count > 0 and greeting_count % batch_size == 0:
                        pause_min = throttle.get("batch_pause_min", 45)
                        pause_max = throttle.get("batch_pause_max", 120)
                        await self.emit(PipelineEvent(
                            WARNING, f"批次暂停 {pause_min}-{pause_max}秒（防检测）...",
                        ))
                        await self.actions.random_delay(pause_min, pause_max)

                    await self._emit_progress()
                    await self.actions.random_delay(2, 5)

                # ── Batch done → scroll for next round ──
                await self.actions.scroll_to_load_more(device)
                scroll_attempts += 1
                await asyncio.sleep(3)

            # ── Step 3b: Check replies & collect resumes ──
            await self._check_control()
            if self.browser_mode:
                await self.emit(PipelineEvent(WARNING, '浏览器模式已完成推荐卡片筛选与打招呼；聊天回复、附件收集尚未实现'))
            elif not self.control.should_stop:
                await self.emit(PipelineEvent(STEP3_SEARCHING, "检查消息回复..."))
                await self._check_replies(db, device, position, jd_summary, scorecard_text, threshold)

            # ── Complete ──
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.progress_json = json.dumps(self.progress)
            db.commit()

            await self.emit(PipelineEvent(TASK_COMPLETED, "招聘任务完成", self.progress))

        except asyncio.CancelledError:
            task = db.get(RecruitTask, self.task_id)
            if task:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                task.error_message = '用户已停止任务'
                task.progress_json = json.dumps(self.progress)
                db.commit()
            raise
        except Exception as exc:
            logger.exception("Pipeline failed for task %d", self.task_id)
            try:
                task = db.get(RecruitTask, self.task_id)
                if task:
                    task.status = "failed"
                    task.error_message = str(exc)
                    db.commit()
            except Exception:
                pass
            await self.emit(PipelineEvent(TASK_FAILED, f"任务失败: {exc}"))
        finally:
            try:
                if self.app_engine:
                    await self.app_engine.close()
            finally:
                db.close()

    async def _check_replies(
        self,
        db: Session,
        device: Any,
        position: Position,
        jd_summary: str,
        scorecard_text: str,
        threshold: float,
    ) -> None:
        """Check for candidate replies, collect resumes, score and follow up."""
        await self.actions.navigate_to_chat(device)
        conversations = await self.actions.get_unread_messages(device)

        for conv in conversations:
            if self.control.should_stop:
                break
            await self._check_control()

            # Process each unread conversation
            try:
                # Click on the conversation by name
                conv_name = conv.get("name", "")
                if conv_name:
                    from rpa.mac_ax_utils import click_by_text
                    click_by_text(conv_name)
                    await self.actions.random_delay(1, 2)

                # Check for resume attachment
                resume_path = await collect_resume(
                    device,
                    conv.get("name", "unknown"),
                    position.title,
                )

                if resume_path:
                    self.progress["resume_received"] += 1

                    # Find the candidate in DB
                    candidate = (
                        db.query(Candidate)
                        .filter(
                            Candidate.task_id == self.task_id,
                            Candidate.name == conv.get("name", ""),
                        )
                        .first()
                    )

                    if candidate:
                        candidate.status = "resume_received"
                        db.commit()

                        await self.emit(PipelineEvent(
                            STEP3_RESUME_RECEIVED,
                            f"收到简历: {candidate.name}",
                            {"candidate_id": candidate.id},
                        ))

                        # ── Step 4: Score the resume ──
                        await self.emit(PipelineEvent(
                            STEP4_SCORING,
                            f"正在评分: {candidate.name}",
                        ))

                        raw_text = parse_resume(resume_path)
                        extracted = extract_resume_info(raw_text)
                        score = score_resume(extracted, jd_summary, scorecard_text)
                        report = generate_report(extracted, score)

                        save_resume_to_db(
                            db=db,
                            candidate_id=candidate.id,
                            file_path=resume_path,
                            file_type=resume_path.split(".")[-1],
                            raw_text=raw_text,
                            extracted_json=extracted.model_dump(),
                            score_json=score.model_dump(),
                            weighted_total=score.weighted_total,
                            is_qualified=score.is_qualified,
                            analysis_report=report,
                        )

                        candidate.status = "scored"
                        self.progress["scored"] += 1
                        db.commit()

                        await self.emit(PipelineEvent(
                            STEP4_SCORED,
                            f"评分完成: {candidate.name} ({score.weighted_total:.1f}分)",
                            {
                                "candidate_id": candidate.id,
                                "score": score.weighted_total,
                                "qualified": score.is_qualified,
                            },
                        ))

                        # ── Step 5: Contact follow-up if qualified ──
                        if score.is_qualified:
                            candidate.status = "qualified"
                            self.progress["qualified"] += 1
                            db.commit()

                            await self.emit(PipelineEvent(
                                STEP5_CONTACT_REQUEST,
                                f"正在索要联系方式: {candidate.name}",
                            ))

                            chat_history = "\n".join(
                                f"{'我' if m.direction == 'sent' else candidate.name}: {m.content}"
                                for m in candidate.messages
                            )

                            contact_msg = generate_contact_request(
                                jd_summary=jd_summary,
                                candidate_profile=candidate.boss_profile_json,
                                chat_history=chat_history,
                                attempt=1,
                            )

                            sent = await self.actions.send_chat_message(device, contact_msg)
                            if sent:
                                db.add(ChatMessage(
                                    candidate_id=candidate.id,
                                    direction="sent",
                                    content=contact_msg,
                                    message_type="contact_request",
                                ))
                                db.commit()

                await self._emit_progress()
                await self.actions.random_delay(2, 5)

            except Exception as e:
                logger.error("Error processing conversation: %s", e)
                continue

    async def _check_control(self) -> None:
        """Check if the task is paused or should stop."""
        await self.control.wait_if_paused()
        if self.control.should_stop:
            raise asyncio.CancelledError("Task stopped by user")

    async def _emit_progress(self) -> None:
        """Emit a progress update event."""
        await self.emit(PipelineEvent(
            PROGRESS_UPDATE,
            "进度更新",
            self.progress.copy(),
        ))


# ── 硬性筛选工具函数 ─────────────────────────────────────────────────

def _has_auto_experience(card: dict) -> bool:
    """判断候选人是否有车企/汽车行业经验。

    检查维度：
    1. 工作经历中是否有汽车相关公司（车企/Tier1供应商）
    2. 技能标签是否包含汽车行业关键词
    3. 个人自述是否提及汽车相关内容
    """
    AUTO_KEYWORDS = [
        "汽车", "整车", "新能源", "主机厂", "车企",
        "江淮", "奇瑞", "比亚迪", "蔚来", "理想", "小鹏", "吉利", "长安",
        "长城", "大众", "丰田", "本田", "通用", "上汽", "一汽", "东风",
        "博世", "大陆", "采埃孚", "德尔福", "舍弗勒", "宁德时代",
        "CANoe", "CANalyzer", "TSMaster", "CAN总线",
        "车载", "ADAS", "底盘", "动力总成", "变速箱",
        "内外饰", "车身", "NVH", "耐久", "碰撞",
        "HIL", "SIL", "MIL", "V模型", "ASPICE", "ISO 26262",
        "标定", "台架", "道路试验", "测试验证",
        "车辆工程", "发动机", "变速器", "悬架", "制动", "转向",
        "车联网", "智能驾驶", "自动驾驶", "三电", "BMS",
        "冲压", "焊装", "涂装", "总装",
    ]

    # 检查工作经历
    work_exp = card.get("work_experience", [])
    work_text = " ".join(work_exp) if work_exp else ""

    # 检查技能标签
    tags = card.get("tags", [])
    tag_text = " ".join(tags) if tags else ""

    # 检查个人自述
    advantages = card.get("advantages", "")

    # 检查期望职位
    expect_pos = card.get("expect_position", "")

    # 全部合并搜索
    full_text = f"{work_text} {tag_text} {advantages} {expect_pos}"

    for kw in AUTO_KEYWORDS:
        if kw.lower() in full_text.lower():
            return True

    return False
