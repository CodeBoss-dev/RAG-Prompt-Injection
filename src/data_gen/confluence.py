"""Synthetic Confluence wiki page generator."""

from __future__ import annotations

import json
import random
import uuid
from typing import Any

from faker import Faker

from config.settings import settings
from src.data_gen.base import DataSource


class ConfluenceGenerator(DataSource):
    """Generates realistic Confluence wiki pages from seed templates."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        self._templates = self._load_templates()

    @property
    def source_type(self) -> str:
        return "confluence"

    def generate(self, count: int) -> list[dict[str, Any]]:
        return [self._generate_one() for _ in range(count)]

    def _load_templates(self) -> dict:
        path = settings.data_seed_dir / "confluence_pages.json"
        with open(path) as f:
            return json.load(f)

    def _pick_access_level(self) -> str:
        return random.choice(self._templates["access_levels"])

    def _pick_trust_score(self) -> float:
        lo, hi = self._templates["trust_score_range"]
        return round(random.uniform(lo, hi), 3)

    def _fill(self, text: str, department: str, author: str) -> str:
        replacements = {
            "{{department}}": department,
            "{{author}}": author,
            "{{team_name}}": department,
            "{{service_name}}": self._fake.bs().split()[0].title() + "Service",
            "{{tool_name}}": random.choice(["Terraform", "Kubernetes", "Docker", "Vault", "Prometheus"]),
            "{{version}}": f"{random.randint(1,3)}.{random.randint(0,9)}",
            "{{owner_name}}": author,
            "{{date}}": self._fake.date_this_year().isoformat(),
            "{{step_description}}": self._fake.sentence(),
            "{{overview}}": self._fake.paragraph(nb_sentences=4),
            "{{details}}": self._fake.paragraph(nb_sentences=5),
            "{{guideline}}": self._fake.sentence(),
            "{{policy_text}}": self._fake.paragraph(nb_sentences=3),
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        # Replace any remaining {{...}} with a faker sentence fragment
        import re
        text = re.sub(r"\{\{[^}]+\}\}", lambda _: self._fake.sentence(), text)
        return text

    def _generate_one(self) -> dict[str, Any]:
        department = random.choice(self._templates["departments"])
        topic = random.choice(self._templates["topics"])
        author = self._fake.name()
        tpl = random.choice(self._templates["templates"])
        title = tpl["title_template"].replace("{{topic}}", topic).replace("{{department}}", department)
        content_tpl = random.choice(tpl["content_templates"])
        content = self._fill(content_tpl, department, author)

        return {
            "id": f"conf-{uuid.uuid4().hex[:12]}",
            "title": title,
            "content": f"# {title}\n\n{content}",
            "source_type": self.source_type,
            "author": author,
            "department": department,
            "access_level": self._pick_access_level(),
            "trust_score": self._pick_trust_score(),
            "created_at": self._fake.iso8601(),
            "metadata": {
                "space": f"{department.lower().replace(' ', '-')}-space",
                "url": f"https://acme.atlassian.net/wiki/spaces/{department[:3].upper()}/pages/{random.randint(100000, 999999)}",
                "labels": [topic.lower().replace(" ", "-"), department.lower()],
                "version": random.randint(1, 15),
            },
        }
