"""Synthetic internal technical document generator."""

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
    "DevOps", "SRE", "Infrastructure", "Architecture",
]


class InternalDocsGenerator(DataSource):
    """Generates longer-form technical documents (specs, runbooks, RFCs, etc.)."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        self._templates = self._load_templates()

    @property
    def source_type(self) -> str:
        return "internal_docs"

    def generate(self, count: int) -> list[dict[str, Any]]:
        return [self._generate_one() for _ in range(count)]

    def _load_templates(self) -> dict:
        path = settings.data_seed_dir / "internal_docs.json"
        with open(path) as f:
            return json.load(f)

    def _pick_access_level(self) -> str:
        return random.choice(self._templates["access_levels"])

    def _pick_trust_score(self) -> float:
        lo, hi = self._templates["trust_score_range"]
        return round(random.uniform(lo, hi), 3)

    def _fill(self, text: str, author: str, department: str) -> str:
        environment = random.choice(["staging", "production", "canary", "dev"])
        replacements = {
            "{{owner_name}}": author,
            "{{author}}": author,
            "{{department}}": department,
            "{{team_name}}": department,
            "{{service_name}}": self._fake.bs().split()[0].title() + "Service",
            "{{version}}": f"{random.randint(1,3)}.{random.randint(0,9)}",
            "{{environment}}": environment,
            "{{date}}": self._fake.date_this_year().isoformat(),
            "{{updated_at}}": self._fake.date_this_year().isoformat(),
            "{{status}}": random.choice(["Approved", "In Review", "Draft", "Deprecated"]),
            "{{rfc_status}}": random.choice(["proposed", "accepted", "rejected", "implemented"]),
            "{{endpoint}}": f"https://api.acme.com/v{random.randint(1,3)}/{self._fake.slug()}",
            "{{config_key}}": random.choice(["LOG_LEVEL", "MAX_RETRIES", "TIMEOUT_MS", "CACHE_TTL"]),
            "{{config_value}}": random.choice(["info", "3", "5000", "300"]),
            "{{paragraph}}": self._fake.paragraph(nb_sentences=5),
            "{{technical_paragraph}}": self._fake.paragraph(nb_sentences=6),
            "{{step}}": self._fake.sentence(),
            "{{risk}}": self._fake.sentence(),
            "{{metric}}": f"P99 latency: {random.randint(50, 500)}ms",
            "{{employee_name}}": self._fake.name(),
            "{{salary}}": f"${random.randint(80, 250)}k",
            "{{ssn}}": f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        text = re.sub(r"\{\{[^}]+\}\}", lambda _: self._fake.sentence(), text)
        return text

    def _generate_one(self) -> dict[str, Any]:
        tpl = random.choice(self._templates["templates"])
        doc_type = tpl.get("doc_type", random.choice(self._templates["doc_types"]))
        author = self._fake.name()
        department = random.choice(_DEPARTMENTS)

        title = tpl["title_template"]
        title = re.sub(r"\{\{[^}]+\}\}", lambda _: self._fake.bs().title(), title)

        content_tpl = random.choice(tpl["content_templates"])
        content = self._fill(content_tpl, author, department)

        return {
            "id": f"doc-{uuid.uuid4().hex[:12]}",
            "title": title,
            "content": content,
            "source_type": self.source_type,
            "author": author,
            "department": department,
            "access_level": self._pick_access_level(),
            "trust_score": self._pick_trust_score(),
            "created_at": self._fake.iso8601(),
            "metadata": {
                "doc_type": doc_type,
                "version": f"v{random.randint(1, 5)}.{random.randint(0, 9)}",
                "review_status": random.choice(["approved", "in_review", "draft"]),
                "page_count": random.randint(2, 20),
                "tags": [doc_type.lower().replace(" ", "-"), department.lower()],
            },
        }
