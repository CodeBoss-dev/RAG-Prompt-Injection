"""Synthetic internal email generator."""

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
    "DevOps", "Product", "SRE", "HR", "Finance", "Legal",
]


class EmailGenerator(DataSource):
    """Generates realistic internal corporate emails."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        self._templates = self._load_templates()

    @property
    def source_type(self) -> str:
        return "email"

    def generate(self, count: int) -> list[dict[str, Any]]:
        return [self._generate_one() for _ in range(count)]

    def _load_templates(self) -> dict:
        path = settings.data_seed_dir / "emails.json"
        with open(path) as f:
            return json.load(f)

    def _pick_access_level(self) -> str:
        return random.choice(self._templates["access_levels"])

    def _pick_trust_score(self) -> float:
        lo, hi = self._templates["trust_score_range"]
        return round(random.uniform(lo, hi), 3)

    def _fill(self, text: str, sender: str, recipient: str, department: str) -> str:
        quarter = random.choice(["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2024"])
        replacements = {
            "{{sender_name}}": sender,
            "{{recipient_name}}": recipient,
            "{{department}}": department,
            "{{team_name}}": department,
            "{{quarter}}": quarter,
            "{{meeting_topic}}": self._fake.bs(),
            "{{meeting_type}}": random.choice(["all-hands", "sprint review", "1-on-1", "QBR"]),
            "{{date}}": self._fake.date_this_year().isoformat(),
            "{{time}}": self._fake.time(),
            "{{project_name}}": self._fake.bs().title(),
            "{{feature_name}}": self._fake.bs().title(),
            "{{service_name}}": self._fake.bs().split()[0].title() + "Service",
            "{{policy_name}}": self._fake.bs().title() + " Policy",
            "{{deadline}}": self._fake.date_between("+1d", "+30d").isoformat(),
            "{{action_item}}": self._fake.sentence(),
            "{{owner}}": self._fake.first_name(),
            "{{metric}}": f"{random.uniform(95.0, 99.99):.2f}%",
            "{{budget_amount}}": f"${random.randint(10, 500)}k",
            "{{paragraph}}": self._fake.paragraph(nb_sentences=4),
            "{{sentence}}": self._fake.sentence(),
            "{{update}}": self._fake.paragraph(nb_sentences=3),
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        text = re.sub(r"\{\{[^}]+\}\}", lambda _: self._fake.sentence(), text)
        return text

    def _generate_one(self) -> dict[str, Any]:
        tpl = random.choice(self._templates["templates"])
        sender = self._fake.name()
        recipient = self._fake.name()
        department = random.choice(_DEPARTMENTS)

        subject = tpl["subject_template"]
        subject = re.sub(r"\{\{[^}]+\}\}", lambda _: self._fake.bs().title(), subject)

        body_tpl = random.choice(tpl["body_templates"])
        body = self._fill(body_tpl, sender, recipient, department)

        return {
            "id": f"email-{uuid.uuid4().hex[:12]}",
            "title": subject,
            "content": f"Subject: {subject}\n\n{body}",
            "source_type": self.source_type,
            "author": sender,
            "department": department,
            "access_level": self._pick_access_level(),
            "trust_score": self._pick_trust_score(),
            "created_at": self._fake.iso8601(),
            "metadata": {
                "from": f"{sender.lower().replace(' ', '.')}@acme.com",
                "to": [f"{recipient.lower().replace(' ', '.')}@acme.com"],
                "cc": (
                    [f"{self._fake.name().lower().replace(' ', '.')}@acme.com"]
                    if random.random() < 0.4
                    else []
                ),
                "has_attachment": random.random() < 0.2,
                "thread_id": f"thread-{uuid.uuid4().hex[:8]}",
            },
        }
