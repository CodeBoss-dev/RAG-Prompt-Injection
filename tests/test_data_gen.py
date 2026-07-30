"""Tests for synthetic enterprise data generation.

The generators depend on seed JSON template files whose structure may evolve.
To keep tests fast and independent of filesystem state, we mock
``_load_templates`` on each generator to supply a minimal template dict that
matches the structure the generator code expects.
"""

from __future__ import annotations

from unittest.mock import patch

from src.data_gen.injector import PayloadInjector, INJECTION_METHODS


# ---------------------------------------------------------------------------
# Required fields that every generated document must contain
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "id", "title", "content", "source_type", "author",
    "department", "access_level", "trust_score", "created_at", "metadata",
}


# ---------------------------------------------------------------------------
# Minimal template dicts that match the structure each generator expects
# ---------------------------------------------------------------------------

_CONFLUENCE_TPL = {
    "departments": ["Engineering", "Product"],
    "topics": ["Onboarding", "Architecture"],
    "access_levels": ["public", "internal", "confidential"],
    "trust_score_range": [0.7, 0.95],
    "templates": [
        {
            "title_template": "{{department}} {{topic}}",
            "content_templates": [
                "Overview: {{overview}}\nDetails: {{details}}\nStep: {{step_description}}"
            ],
        }
    ],
}

_SLACK_TPL = {
    "channels": ["general", "engineering"],
    "access_levels": ["public", "internal"],
    "trust_score_range": [0.4, 0.7],
    "templates": [
        {
            "message_templates": [
                "Hey {{user_name}}, can you check {{service_name}} in {{environment}}?"
            ]
        }
    ],
}

_EMAIL_TPL = {
    "access_levels": ["internal", "confidential"],
    "trust_score_range": [0.6, 0.85],
    "templates": [
        {
            "subject_template": "{{department}} update",
            "body_templates": [
                "Dear {{recipient_name}},\n\n{{paragraph}}\n\nBest,\n{{sender_name}}"
            ],
        }
    ],
}

_INTERNAL_DOCS_TPL = {
    "doc_types": ["RFC", "Runbook"],
    "access_levels": ["internal", "confidential", "restricted"],
    "trust_score_range": [0.8, 0.98],
    "templates": [
        {
            "doc_type": "RFC",
            "title_template": "RFC: {{service_name}}",
            "content_templates": [
                "Author: {{author}}\nDepartment: {{department}}\n\n{{technical_paragraph}}"
            ],
        }
    ],
}


def _make_generator(cls, tpl, seed=42):
    """Instantiate a generator with mocked template loading."""
    with patch.object(cls, "_load_templates", return_value=tpl):
        return cls(seed=seed)


# ---------------------------------------------------------------------------
# Confluence
# ---------------------------------------------------------------------------

class TestConfluenceGenerator:
    def test_produces_correct_structure(self):
        from src.data_gen.confluence import ConfluenceGenerator

        gen = _make_generator(ConfluenceGenerator, _CONFLUENCE_TPL, seed=1)
        docs = gen.generate(5)

        assert len(docs) == 5
        for doc in docs:
            missing = REQUIRED_FIELDS - set(doc.keys())
            assert not missing, f"Missing fields: {missing}"
            assert doc["source_type"] == "confluence"
            assert isinstance(doc["content"], str) and len(doc["content"]) > 0
            assert isinstance(doc["trust_score"], float)
            assert 0.0 <= doc["trust_score"] <= 1.0


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

class TestSlackGenerator:
    def test_metadata(self):
        from src.data_gen.slack import SlackGenerator

        gen = _make_generator(SlackGenerator, _SLACK_TPL, seed=2)
        docs = gen.generate(3)

        for doc in docs:
            missing = REQUIRED_FIELDS - set(doc.keys())
            assert not missing, f"Missing fields: {missing}"
            assert doc["source_type"] == "slack"
            assert 0.0 <= doc["trust_score"] <= 1.0


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

class TestEmailGenerator:
    def test_metadata(self):
        from src.data_gen.email import EmailGenerator

        gen = _make_generator(EmailGenerator, _EMAIL_TPL, seed=3)
        docs = gen.generate(3)

        for doc in docs:
            missing = REQUIRED_FIELDS - set(doc.keys())
            assert not missing, f"Missing fields: {missing}"
            assert doc["source_type"] == "email"


# ---------------------------------------------------------------------------
# Internal Docs
# ---------------------------------------------------------------------------

class TestInternalDocsGenerator:
    def test_metadata(self):
        from src.data_gen.internal_docs import InternalDocsGenerator

        gen = _make_generator(InternalDocsGenerator, _INTERNAL_DOCS_TPL, seed=4)
        docs = gen.generate(3)

        for doc in docs:
            missing = REQUIRED_FIELDS - set(doc.keys())
            assert not missing, f"Missing fields: {missing}"
            assert doc["source_type"] == "internal_docs"


# ---------------------------------------------------------------------------
# Cross-generator uniqueness
# ---------------------------------------------------------------------------

class TestAllGeneratorsUniqueIds:
    def test_unique_ids(self):
        """Generate docs from all generators and verify no duplicate IDs."""
        from src.data_gen.confluence import ConfluenceGenerator
        from src.data_gen.slack import SlackGenerator
        from src.data_gen.email import EmailGenerator
        from src.data_gen.internal_docs import InternalDocsGenerator

        generators = [
            (ConfluenceGenerator, _CONFLUENCE_TPL, 10),
            (SlackGenerator, _SLACK_TPL, 11),
            (EmailGenerator, _EMAIL_TPL, 12),
            (InternalDocsGenerator, _INTERNAL_DOCS_TPL, 13),
        ]

        all_ids: list[str] = []
        for cls, tpl, seed in generators:
            gen = _make_generator(cls, tpl, seed=seed)
            docs = gen.generate(10)
            all_ids.extend(d["id"] for d in docs)

        assert len(all_ids) == len(set(all_ids)), "Duplicate IDs found across generators"


# ---------------------------------------------------------------------------
# Payload Injector
# ---------------------------------------------------------------------------

def _make_clean_corpus(n: int = 40) -> list[dict]:
    """Build a small mixed corpus for injection tests using mocked generators."""
    from src.data_gen.confluence import ConfluenceGenerator
    from src.data_gen.slack import SlackGenerator
    from src.data_gen.email import EmailGenerator
    from src.data_gen.internal_docs import InternalDocsGenerator

    docs: list[dict] = []
    for cls, tpl, count, seed in [
        (ConfluenceGenerator, _CONFLUENCE_TPL, n // 4, 100),
        (SlackGenerator, _SLACK_TPL, n // 4, 101),
        (EmailGenerator, _EMAIL_TPL, n // 4, 102),
        (InternalDocsGenerator, _INTERNAL_DOCS_TPL, n // 4, 103),
    ]:
        gen = _make_generator(cls, tpl, seed=seed)
        docs.extend(gen.generate(count))
    return docs


class TestPayloadInjector:
    def test_injects_correct_count(self):
        corpus = _make_clean_corpus(40)
        injector = PayloadInjector(num_poisoned_per_type=5, seed=42)
        modified, manifest = injector.inject(corpus)

        # The total number of docs stays the same (in-place replacement)
        assert len(modified) == len(corpus)

        # Manifest should have entries for every injection performed
        assert len(manifest) > 0
        from collections import Counter
        type_counts = Counter(m["attack_type"] for m in manifest)
        for attack_type, count in type_counts.items():
            assert count <= 5, f"{attack_type} injected {count} > 5"

    def test_manifest_structure(self):
        corpus = _make_clean_corpus(40)
        injector = PayloadInjector(num_poisoned_per_type=3, seed=42)
        _, manifest = injector.inject(corpus)

        required_manifest_fields = {
            "doc_id", "attack_type", "variant_id", "variant_name",
            "injection_method", "original_source_type", "success_patterns",
        }
        for entry in manifest:
            missing = required_manifest_fields - set(entry.keys())
            assert not missing, f"Manifest entry missing fields: {missing}"
            assert entry["injection_method"] in INJECTION_METHODS

    def test_no_double_poisoning(self):
        corpus = _make_clean_corpus(40)
        injector = PayloadInjector(num_poisoned_per_type=5, seed=42)
        _, manifest = injector.inject(corpus)

        doc_ids = [m["doc_id"] for m in manifest]
        assert len(doc_ids) == len(set(doc_ids)), "Same doc poisoned more than once"

    def test_injection_methods(self):
        """Verify append, middle, and html_comment produce distinct results."""
        original = "Line one\nLine two\nLine three\nLine four"
        payload = "INJECTED PAYLOAD"

        results: dict[str, str] = {}
        for method in INJECTION_METHODS:
            results[method] = PayloadInjector._inject_payload(original, payload, method)

        # All three methods should produce different output
        assert len(set(results.values())) == 3, (
            "Expected 3 distinct injection results, got fewer"
        )

        # append: payload appears at the end
        assert results["append"].endswith(payload)

        # html_comment: payload is wrapped in <!-- ... -->
        assert "<!--" in results["html_comment"]
        assert "-->" in results["html_comment"]

        # middle: payload appears between the first and last lines
        assert payload in results["middle"]
        assert not results["middle"].startswith(payload)
        assert not results["middle"].rstrip().endswith(payload)
