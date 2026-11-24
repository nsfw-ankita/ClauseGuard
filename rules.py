"""Rule-based checklist and scoring for rent agreements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class RuleCheck:
    key: str
    label_en: str
    label_hi: str
    present: bool
    evidence: str = ""


@dataclass(frozen=True)
class RuleDef:
    key: str
    label_en: str
    label_hi: str
    patterns: tuple[str, ...]


RULE_DEFS: tuple[RuleDef, ...] = (
    RuleDef(
        "security_deposit",
        "Security deposit amount",
        "सुरक्षा जमा राशि",
        (
            r"security\s+deposit",
            r"deposit\s+of\s+(rs\.?|inr|₹)?\s*\d",
            r"advance\s+deposit",
            r"सुरक्षा\s*जमा",
            r"जमानत\s*राशि",
            r"डिपॉजिट",
        ),
    ),
    RuleDef(
        "deposit_refund",
        "Deposit refund timeline",
        "जमा वापसी की समय सीमा",
        (
            r"refund.{0,60}(deposit|amount)",
            r"deposit.{0,60}refund",
            r"within\s+\d+\s*(day|days|week|weeks|month|months).{0,40}refund",
            r"वापस.{0,30}(जमा|राशि|डिपॉजिट)",
            r"जमा.{0,30}वापस",
            r"रिफंड",
        ),
    ),
    RuleDef(
        "notice_period",
        "Notice period",
        "नोटिस अवधि",
        (
            r"notice\s+period",
            r"\d+\s*(day|days|month|months).{0,20}notice",
            r"notice\s+of\s+\d+",
            r"नोटिस\s*अवधि",
            r"\d+\s*(दिन|महीन).{0,15}नोटिस",
            r"नोटिस\s*देना",
        ),
    ),
    RuleDef(
        "lock_in",
        "Lock-in period",
        "लॉक-इन अवधि",
        (
            r"lock[-\s]?in",
            r"minimum\s+(period|tenure|term)",
            r"लॉक[-\s]?इन",
            r"न्यूनतम\s*अवधि",
            r"बंधी\s*अवधि",
        ),
    ),
    RuleDef(
        "rent_increase",
        "Rent increase cap",
        "किराया बढ़ोतरी सीमा",
        (
            r"rent.{0,40}(increase|increment|hike|escalat)",
            r"(increase|increment|hike|escalat).{0,40}rent",
            r"\d+\s*%.{0,30}(increase|increment|rent)",
            r"किराय.{0,30}(बढ़|वृद्धि)",
            r"बढ़ोतरी.{0,30}किराय",
        ),
    ),
    RuleDef(
        "maintenance",
        "Maintenance responsibility",
        "रखरखाव जिम्मेदारी",
        (
            r"maintenance",
            r"repair",
            r"upkeep",
            r"रखरखाव",
            r"मरम्मत",
            r"मेंटेनेंस",
        ),
    ),
    RuleDef(
        "eviction",
        "Eviction terms",
        "बेदखली की शर्तें",
        (
            r"evict",
            r"vacate",
            r"termination\s+of\s+(agreement|tenancy|lease)",
            r"terminate.{0,30}(agreement|lease|tenancy)",
            r"बेदखली",
            r"खाली\s*कर",
            r"समाप्त.{0,20}(अनुबंध|समझौता)",
        ),
    ),
    RuleDef(
        "police_verification",
        "Police verification",
        "पुलिस सत्यापन",
        (
            r"police\s+verification",
            r"tenant\s+verification",
            r"पुलिस\s*सत्यापन",
            r"किरायेदार\s*सत्यापन",
        ),
    ),
    RuleDef(
        "utilities",
        "Electricity/water bill responsibility",
        "बिजली/पानी बिल जिम्मेदारी",
        (
            r"electricity",
            r"water\s+bill",
            r"utility|utilities",
            r"बिजली",
            r"पानी\s*बिल",
            r"उपयोगिता\s*बिल",
        ),
    ),
    RuleDef(
        "inspection",
        "Property inspection notice",
        "संपत्ति निरीक्षण सूचना",
        (
            r"inspect",
            r"visit.{0,30}(property|premises)",
            r"entry.{0,30}(property|premises)",
            r"निरीक्षण",
            r"मुआयना",
            r"प्रवेश.{0,20}(संपत्ति|मकान)",
        ),
    ),
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def check_rules(text: str) -> list[RuleCheck]:
    normalized = _normalize(text)
    results: list[RuleCheck] = []
    for rule in RULE_DEFS:
        evidence = ""
        present = False
        for pattern in rule.patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                present = True
                start = max(0, match.start() - 25)
                end = min(len(normalized), match.end() + 45)
                evidence = normalized[start:end].strip()
                break
        results.append(
            RuleCheck(
                key=rule.key,
                label_en=rule.label_en,
                label_hi=rule.label_hi,
                present=present,
                evidence=evidence,
            )
        )
    return results


def merge_missing_clauses(
    ai_missing: list[str], rule_checks: list[RuleCheck], language: str
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        key = re.sub(r"\s+", " ", item.lower()).strip()
        if not key or key in seen:
            return
        seen.add(key)
        merged.append(item.strip())

    for item in ai_missing:
        add(item)

    for rule in rule_checks:
        if rule.present:
            continue
        label = rule.label_hi if language == "Hindi" else rule.label_en
        # Avoid duplicates when AI already mentioned similar concept.
        label_key = re.sub(r"\s+", " ", label.lower()).strip()
        if any(label_key in s or s in label_key for s in seen):
            continue
        # Also check English label keywords against AI items for cross-language dedupe.
        en_tokens = [t for t in re.findall(r"[a-z]+", rule.label_en.lower()) if len(t) > 3]
        if en_tokens and any(sum(1 for t in en_tokens if t in s) >= 2 for s in seen):
            continue
        add(label)

    return merged


def calculate_score(analysis: Any, rule_checks: list[RuleCheck]) -> dict:
    score = 10.0
    for clause in getattr(analysis, "clauses", []):
        color = getattr(clause, "color", None)
        if color == "red":
            score -= 1.0
        elif color == "yellow":
            score -= 0.4
    for rule in rule_checks:
        if not rule.present:
            score -= 0.5
    score = max(0.0, round(score, 1))
    if score >= 8.0:
        label_en, label_hi, color = "Looks safe", "सुरक्षित लग रहा है", "green"
    elif score >= 5.0:
        label_en, label_hi, color = "Be careful", "सावधान रहें", "yellow"
    else:
        label_en, label_hi, color = "Risky", "जोखिम भरा", "red"
    return {
        "score": score,
        "label_en": label_en,
        "label_hi": label_hi,
        "color": color,
    }
