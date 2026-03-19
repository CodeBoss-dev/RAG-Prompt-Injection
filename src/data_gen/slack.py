"""Synthetic Slack message generator."""

from __future__ import annotations

import json
import random
import re
import uuid
from typing import Any

from faker import Faker

from config.settings import settings
from src.data_gen.base import DataSource

_DEPARTMENTS = [
    "Engineering", "Platform", "Security", "Data Science",
    "DevOps", "Product", "SRE", "Infrastructure", "QA", "ML",
]


class SlackGenerator(DataSource):
    """Generates realistic Slack messages — short, casual, with channel metadata."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        self._templates = self._load_templates()

    @property
    def source_type(self) -> str:
        return "slack"

    def generate(self, count: int) -> list[dict[str, Any]]:
        return [self._generate_one() for _ in range(count)]

    def _load_templates(self) -> dict:
        path = settings.data_seed_dir / "slack_messages.json"
        with open(path) as f:
            return json.load(f)

    def _pick_access_level(self) -> str:
        return random.choice(self._templates["access_levels"])

    def _pick_trust_score(self) -> float:
        lo, hi = self._templates["trust_score_range"]
        return round(random.uniform(lo, hi), 3)

    def _fill(self, text: str, author: str) -> str:
        replacements = {
            "{{author}}": author,
            "{{user_name}}": self._fake.first_name(),
            "{{tool_name}}": random.choice(["Terraform", "Kubernetes", "Vault", "Datadog", "PagerDuty"]),
            "{{service_name}}": self._fake.bs().split()[0].title() + "Service",
            "{{environment}}": random.choice(["prod", "staging", "dev", "canary"]),
            "{{pr_number}}": str(random.randint(1000, 9999)),
            "{{issue_number}}": f"JIRA-{random.randint(1000, 9999)}",
            "{{meeting_type}}": random.choice(["standup", "sprint retro", "arch review", "1-on-1"]),
            "{{date}}": self._fake.date_this_month().isoformat(),
            "{{time}}": self._fake.time(),
            "{{message}}": self._fake.sentence(),
            "{{update}}": self._fake.sentence(),
            "{{topic}}": self._fake.bs(),
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        text = re.sub(r"\{\{[^}]+\}\}", lambda _: self._fake.word(), text)
        return text

    def _generate_one(self) -> dict[str, Any]:
        channel = random.choice(self._templates["channels"])
        author = self._fake.name()
        department = random.choice(_DEPARTMENTS)

        tpl_group = random.choice(self._templates["templates"])
        msg_tpl = random.choice(tpl_group["message_templates"])
        content = self._fill(msg_tpl, author)

        # Optionally add a thread reply (30% chance)
        if random.random() < 0.3:
            reply_author = self._fake.first_name()
            reply = random.choice([
                f"  > {reply_author}: +1, same here",
                f"  > {reply_author}: thanks, that fixed it!",
                f"  > {reply_author}: {self._fake.sentence()}",
                f"  > {reply_author}: linking the ticket — JIRA-{random.randint(1000, 9999)}",
            ])
            content = f"{content}\n{reply}"

        title_line = content.split("\n")[0][:80]

        return {
            "id": f"slack-{uuid.uuid4().hex[:12]}",
            "title": title_line,
            "content": content,
            "source_type": self.source_type,
            "author": author,
            "department": department,
            "access_level": self._pick_access_level(),
            "trust_score": self._pick_trust_score(),
            "created_at": self._fake.iso8601(),
            "metadata": {
                "channel": f"#{channel}",
                "thread_ts": f"{random.randint(1_700_000_000, 1_710_000_000)}.{random.randint(100000, 999999)}",
                "reactions": random.randint(0, 12),
                "reply_count": random.randint(0, 25),
            },
        }
