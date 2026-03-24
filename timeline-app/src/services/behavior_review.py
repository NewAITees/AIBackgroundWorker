"""行動改善レビューと Big Five 推定の共通ロジック。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Iterable

from ..config import BehaviorConfig
from ..models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType

BIG_FIVE_TRAITS = [
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
]

TRAIT_LABELS = {
    "openness": "開放性",
    "conscientiousness": "誠実性",
    "extraversion": "外向性",
    "agreeableness": "協調性",
    "neuroticism": "神経症傾向",
}

IMPROVEMENT_HINTS = {
    "openness": "新しいやり方を1つ試す、違う視点のメモを1行残す",
    "conscientiousness": "着手条件を1つ具体化する、次の15分タスクに分解する",
    "extraversion": "短い相談や共有を1回入れる、声に出して整理する",
    "agreeableness": "相手視点の確認を1回入れる、感謝や配慮を言語化する",
    "neuroticism": "不安の原因を1つ書き出す、休憩や切替の条件を先に決める",
}

TRAIT_DIRECTION_LABELS = {
    "up": "上げたい",
    "down": "下げたい",
    "keep": "維持したい",
}

TRAIT_KEYWORDS: dict[str, dict[str, float]] = {
    "openness": {
        "試": 0.35,
        "新": 0.25,
        "学": 0.2,
        "読": 0.1,
        "設計": 0.1,
        "アイデア": 0.35,
        "改善": 0.15,
    },
    "conscientiousness": {
        "完了": 0.35,
        "進": 0.2,
        "TODO": 0.25,
        "整理": 0.2,
        "計画": 0.2,
        "提出": 0.2,
        "レビュー": 0.1,
    },
    "extraversion": {
        "会話": 0.3,
        "相談": 0.35,
        "打合": 0.3,
        "共有": 0.25,
        "連絡": 0.25,
        "電話": 0.35,
    },
    "agreeableness": {
        "手伝": 0.3,
        "感謝": 0.35,
        "配慮": 0.25,
        "調整": 0.2,
        "サポート": 0.3,
        "返信": 0.15,
    },
    "neuroticism": {
        "不安": 0.45,
        "焦": 0.35,
        "疲": 0.25,
        "つら": 0.3,
        "心配": 0.35,
        "ミス": 0.2,
        "遅れ": 0.15,
    },
}

PERSPECTIVE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "今日の前進": ("完了", "進", "終", "提出", "整理", "でき"),
    "詰まりやすかった点": ("不安", "焦", "止", "詰", "遅れ", "疲"),
    "明日に回すもの": ("明日", "次", "続き", "残", "未完", "TODO"),
    "エネルギーの使い方": ("疲", "休", "集中", "眠", "体調"),
    "対人コミュニケーション": ("会話", "相談", "共有", "返信", "感謝"),
    "集中と段取り": ("計画", "整理", "TODO", "優先", "着手"),
}


@dataclass
class DailyReviewBundle:
    review_entry: Entry | None
    action_entry: Entry | None
    tagged_entries: list[Entry]


@dataclass
class WeeklyReviewBundle:
    review_entry: Entry | None


def target_behavior_entries(entries: Iterable[Entry]) -> list[Entry]:
    return [
        entry
        for entry in entries
        if entry.type in {EntryType.diary, EntryType.event, EntryType.todo_done}
        and is_user_related_entry(entry)
    ]


def is_user_related_entry(entry: Entry) -> bool:
    return entry.source == EntrySource.user


def estimate_entry_traits(entry: Entry) -> tuple[dict[str, float], list[str]]:
    text = " ".join(
        part for part in [entry.title or "", entry.summary or "", entry.content] if part
    ).lower()
    scores = {trait: 0.0 for trait in BIG_FIVE_TRAITS}
    evidence: list[str] = []
    for trait, mapping in TRAIT_KEYWORDS.items():
        for keyword, weight in mapping.items():
            if keyword.lower() in text:
                scores[trait] += weight
                evidence.append(f"{TRAIT_LABELS[trait]}: {keyword}")
    scores["neuroticism"] = max(min(scores["neuroticism"], 1.0), 0.0)
    for trait in ("openness", "conscientiousness", "extraversion", "agreeableness"):
        scores[trait] = max(min(scores[trait], 1.0), 0.0)
    compact = {trait: round(value, 2) for trait, value in scores.items() if value > 0}
    return compact, evidence[:5]


def tag_entries_with_traits(entries: Iterable[Entry]) -> list[Entry]:
    tagged: list[Entry] = []
    for entry in target_behavior_entries(entries):
        traits, evidence = estimate_entry_traits(entry)
        if not traits and not evidence:
            continue
        tagged.append(
            entry.model_copy(
                update={
                    "meta": entry.meta.model_copy(
                        update={
                            "traits": traits,
                            "trait_evidence": evidence,
                        }
                    )
                }
            )
        )
    return tagged


def build_daily_review_bundle(
    workspace_path: str,
    target_date: date,
    entries: Iterable[Entry],
    behavior_config: BehaviorConfig,
) -> DailyReviewBundle:
    relevant_entries = sorted(target_behavior_entries(entries), key=lambda entry: entry.timestamp)
    if not relevant_entries or not behavior_config.review_enabled:
        tagged_entries = (
            tag_entries_with_traits(relevant_entries) if behavior_config.big_five_enabled else []
        )
        return DailyReviewBundle(
            review_entry=None, action_entry=None, tagged_entries=tagged_entries
        )

    tagged_entries = (
        tag_entries_with_traits(relevant_entries) if behavior_config.big_five_enabled else []
    )
    trait_totals = aggregate_trait_scores(tagged_entries)
    review_entry = Entry(
        id=f"daily-review-{target_date.isoformat()}",
        type=EntryType.memo,
        title="日次レビュー",
        summary=f"{target_date.isoformat()} の振り返り",
        content=render_daily_review(
            target_date,
            relevant_entries,
            behavior_config.review_perspectives,
            trait_totals,
            behavior_config.big_five_enabled,
        ),
        timestamp=datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        + timedelta(hours=23, minutes=40),
        status=EntryStatus.active,
        source=EntrySource.ai,
        workspace_path=workspace_path,
        meta=EntryMeta(
            review_kind="daily_review",
            review_scope="behavior",
            review_date=target_date.isoformat(),
        ),
    )
    action_entry = Entry(
        id=f"daily-action-{target_date.isoformat()}",
        type=EntryType.todo,
        title="明日の改善アクション",
        summary=pick_daily_action_summary(behavior_config, trait_totals),
        content=render_daily_action(behavior_config, trait_totals),
        timestamp=datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        + timedelta(hours=8, minutes=30),
        status=EntryStatus.active,
        source=EntrySource.ai,
        workspace_path=workspace_path,
        meta=EntryMeta(
            review_kind="improvement_action",
            review_scope="behavior",
            review_date=target_date.isoformat(),
            traits={trait: score for trait, score in trait_totals.items() if score > 0},
        ),
    )
    return DailyReviewBundle(
        review_entry=review_entry, action_entry=action_entry, tagged_entries=tagged_entries
    )


def aggregate_trait_scores(entries: Iterable[Entry]) -> dict[str, float]:
    totals = defaultdict(float)
    for entry in entries:
        for trait, score in (entry.meta.traits or {}).items():
            totals[trait] += float(score)
    return {trait: round(totals.get(trait, 0.0), 2) for trait in BIG_FIVE_TRAITS}


def render_daily_review(
    target_date: date,
    entries: list[Entry],
    perspectives: list[str],
    trait_totals: dict[str, float],
    include_big_five: bool,
) -> str:
    lines = [f"# {target_date.isoformat()} のレビュー", ""]
    lines.append("## 今日の記録")
    for entry in entries[:6]:
        body = (entry.summary or entry.content).strip().replace("\n", " ")
        lines.append(f"- {entry.title or entry.type.value}: {body[:90]}")
    lines.append("")
    lines.append("## 観点別メモ")
    for perspective in perspectives or ["今日の前進", "詰まりやすかった点", "明日に回すもの"]:
        lines.append(f"- {perspective}: {summarize_perspective(perspective, entries)}")
    if include_big_five:
        lines.append("")
        lines.append("## Big Five 視点")
        if any(value > 0 for value in trait_totals.values()):
            for trait in BIG_FIVE_TRAITS:
                value = trait_totals.get(trait, 0.0)
                if value <= 0:
                    continue
                lines.append(f"- {TRAIT_LABELS[trait]}: {describe_trait_signal(trait, value)}")
        else:
            lines.append("- 今日は Big Five 推定に使える明確な行動シグナルが少なめでした。")
    return "\n".join(lines).strip()


def summarize_perspective(perspective: str, entries: list[Entry]) -> str:
    keywords = PERSPECTIVE_KEYWORDS.get(perspective, ())
    matched = []
    for entry in entries:
        text = " ".join(
            part for part in [entry.title or "", entry.summary or "", entry.content] if part
        )
        if any(keyword in text for keyword in keywords):
            matched.append(entry.title or entry.type.value)
    if matched:
        unique = " / ".join(dict.fromkeys(matched).keys())
        return f"{unique} に関連する動きが見えました。"
    if perspective == "今日の前進":
        return "完了や前進を明示した記録をもう少し残すと振り返りやすくなります。"
    if perspective == "詰まりやすかった点":
        return "詰まりの記録が少ないので、止まった理由を一言残すと改善につながります。"
    return "次に回したいことを一文で切り出しておくと明日が軽くなります。"


def describe_trait_signal(trait: str, value: float) -> str:
    if trait == "neuroticism":
        return "不安や負荷のサインがやや強めでした。" if value >= 0.5 else "軽いストレス反応が見えました。"
    if value >= 0.7:
        return "かなり出ていました。"
    if value >= 0.35:
        return "ほどよく出ていました。"
    return "小さく見えました。"


def pick_daily_action_summary(
    behavior_config: BehaviorConfig, trait_totals: dict[str, float]
) -> str:
    target_trait = select_focus_trait(behavior_config, trait_totals)
    label = TRAIT_LABELS[target_trait]
    direction = behavior_config.big_five_trait_targets.get(target_trait, "keep")
    return f"{label} を{TRAIT_DIRECTION_LABELS.get(direction, '整えたい')}行動を1つ入れる"


def render_daily_action(behavior_config: BehaviorConfig, trait_totals: dict[str, float]) -> str:
    target_trait = select_focus_trait(behavior_config, trait_totals)
    direction = behavior_config.big_five_trait_targets.get(target_trait, "keep")
    lines = [
        f"{TRAIT_LABELS[target_trait]} を {TRAIT_DIRECTION_LABELS.get(direction, '整えたい')} 設定なので、明日は次のどれかを1つ入れてください。",
        "",
        f"- {IMPROVEMENT_HINTS[target_trait]}",
    ]
    if behavior_config.big_five_enabled:
        lines.append(f"- これは Big Five の {TRAIT_LABELS[target_trait]} 改善候補として提案しています。")
    return "\n".join(lines)


def select_focus_trait(behavior_config: BehaviorConfig, trait_totals: dict[str, float]) -> str:
    configured = [
        trait for trait in behavior_config.big_five_focus_traits if trait in BIG_FIVE_TRAITS
    ]
    if configured:
        return min(
            configured, key=lambda trait: focus_trait_sort_key(trait, behavior_config, trait_totals)
        )
    return min(
        BIG_FIVE_TRAITS,
        key=lambda trait: focus_trait_sort_key(trait, behavior_config, trait_totals),
    )


def focus_trait_sort_key(
    trait: str, behavior_config: BehaviorConfig, trait_totals: dict[str, float]
) -> float:
    direction = behavior_config.big_five_trait_targets.get(trait, "keep")
    score = trait_totals.get(trait, 0.0)
    if direction == "up":
        return score
    if direction == "down":
        return -score
    return 999 + abs(score - 0.5)


def build_weekly_review_bundle(
    workspace_path: str,
    entries: Iterable[Entry],
    anchor_date: date,
    behavior_config: BehaviorConfig,
) -> WeeklyReviewBundle:
    payload = build_weekly_review_payload(entries, anchor_date, behavior_config)
    if not behavior_config.review_enabled:
        return WeeklyReviewBundle(review_entry=None)
    content_lines = [
        f"# {payload['week_start']} - {payload['week_end']} の週次レビュー",
        "",
        payload["overview"],
        "",
        "## 観点別メモ",
    ]
    for item in payload["perspective_notes"]:
        content_lines.append(f"- {item['title']}: {item['body']}")
    if behavior_config.big_five_enabled:
        content_lines.append("")
        content_lines.append("## Big Five")
        for item in payload["big_five"]["trait_notes"]:
            content_lines.append(f"- {item['label']}: {item['body']}")
    review_entry = Entry(
        id=f"weekly-review-{payload['week_start']}",
        type=EntryType.memo,
        title="週次レビュー",
        summary=f"{payload['week_start']} - {payload['week_end']} の振り返り",
        content="\n".join(content_lines),
        timestamp=datetime.combine(anchor_date, datetime.min.time(), tzinfo=UTC)
        + timedelta(
            hours=behavior_config.weekly_review_hour, minutes=behavior_config.weekly_review_minute
        ),
        status=EntryStatus.active,
        source=EntrySource.ai,
        workspace_path=workspace_path,
        meta=EntryMeta(
            review_kind="weekly_review",
            review_scope="behavior",
            review_week_start=payload["week_start"],
            review_date=payload["week_end"],
        ),
    )
    return WeeklyReviewBundle(review_entry=review_entry)


def build_weekly_review_payload(
    entries: Iterable[Entry],
    anchor_date: date,
    behavior_config: BehaviorConfig,
) -> dict:
    week_end = anchor_date
    week_start = anchor_date - timedelta(days=6)
    relevant = [
        entry
        for entry in target_behavior_entries(entries)
        if week_start <= entry.timestamp.astimezone().date() <= week_end
    ]
    tagged_entries = tag_entries_with_traits(relevant) if behavior_config.big_five_enabled else []
    trait_totals = aggregate_trait_scores(tagged_entries)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "review_enabled": behavior_config.review_enabled,
        "big_five_enabled": behavior_config.big_five_enabled,
        "daily_review_time": f"{behavior_config.daily_review_hour:02d}:{behavior_config.daily_review_minute:02d}",
        "weekly_review_schedule": {
            "weekday": behavior_config.weekly_review_weekday,
            "time": f"{behavior_config.weekly_review_hour:02d}:{behavior_config.weekly_review_minute:02d}",
        },
        "review_perspectives": behavior_config.review_perspectives,
        "big_five_perspectives": behavior_config.big_five_perspectives,
        "overview": render_weekly_overview(relevant, behavior_config.review_perspectives),
        "perspective_notes": [
            {"title": perspective, "body": summarize_perspective(perspective, relevant)}
            for perspective in (behavior_config.review_perspectives or [])
        ],
        "big_five": {
            "focus_traits": behavior_config.big_five_focus_traits,
            "trait_targets": behavior_config.big_five_trait_targets,
            "trait_scores": trait_totals,
            "trait_notes": [
                {
                    "trait": trait,
                    "label": TRAIT_LABELS[trait],
                    "score": trait_totals.get(trait, 0.0),
                    "body": render_trait_review(
                        trait, trait_totals.get(trait, 0.0), behavior_config.big_five_perspectives
                    ),
                    "improvement_hint": IMPROVEMENT_HINTS[trait],
                    "target_direction": behavior_config.big_five_trait_targets.get(trait, "keep"),
                }
                for trait in BIG_FIVE_TRAITS
            ],
        },
        "entries": [
            {
                "id": entry.id,
                "title": entry.title or entry.type.value,
                "type": entry.type.value,
                "timestamp": entry.timestamp.isoformat(),
                "summary": entry.summary or entry.content,
            }
            for entry in sorted(relevant, key=lambda item: item.timestamp, reverse=True)[:20]
        ],
    }


def render_weekly_overview(entries: list[Entry], perspectives: list[str]) -> str:
    if not entries:
        return "今週のレビュー対象エントリはまだありません。"
    done_count = sum(1 for entry in entries if entry.type == EntryType.todo_done)
    diary_count = sum(1 for entry in entries if entry.type == EntryType.diary)
    event_count = sum(1 for entry in entries if entry.type == EntryType.event)
    focus_text = " / ".join(perspectives[:3]) if perspectives else "通常レビュー"
    return (
        f"今週は {done_count} 件の完了、{diary_count} 件の日記、{event_count} 件の出来事がありました。"
        f" 設定中の観点は {focus_text} です。"
    )


def render_trait_review(trait: str, score: float, perspectives: list[str]) -> str:
    if score <= 0:
        return f"{TRAIT_LABELS[trait]} を示す行動は今週あまり記録されていません。{IMPROVEMENT_HINTS[trait]}"
    perspective_text = " / ".join(perspectives[:2]) if perspectives else "Big Five 視点"
    if trait == "neuroticism":
        return f"{perspective_text} では負荷サインが見えています。{IMPROVEMENT_HINTS[trait]}"
    return f"{perspective_text} では {TRAIT_LABELS[trait]} の行動シグナルが出ています。{IMPROVEMENT_HINTS[trait]}"
