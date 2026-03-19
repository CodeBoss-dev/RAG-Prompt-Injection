"""Payload injector — plants attack payloads into clean documents."""

from __future__ import annotations

import random
import uuid
from pathlib import Path
from typing import Any

import yaml

from config.settings import settings


# Supported injection strategies
INJECTION_METHODS = ("append", "middle", "html_comment")


class PayloadInjector:
    """Loads attack definitions from YAML and injects payloads into documents.

    The injector selects a subset of clean documents, embeds an attack payload
    into each, and produces a manifest that records exactly which documents
    were poisoned — critical for downstream evaluation metrics.

    Parameters
    ----------
    attacks_dir : Path | None
        Directory containing attack YAML files.  Defaults to
        ``settings.data_attacks_dir``.
    num_poisoned_per_type : int | None
        How many docs to poison for each attack type.  Defaults to
        ``settings.num_poisoned_per_type``.
    seed : int
        Random seed for reproducibility.
    """

    def __init__(
        self,
        attacks_dir: Path | None = None,
        num_poisoned_per_type: int | None = None,
        seed: int = 42,
    ) -> None:
        self._attacks_dir = attacks_dir or settings.data_attacks_dir
        self._num_per_type = num_poisoned_per_type or settings.num_poisoned_per_type
        self._seed = seed
        random.seed(seed)
        self._attack_defs = self._load_attack_definitions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inject(
        self, docs: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Inject attack payloads into a subset of *docs*.

        Returns
        -------
        (modified_docs, manifest)
            *modified_docs* is the full corpus with poisoned entries replaced
            in-place.  *manifest* is a list of dicts recording each injection
            (doc_id, attack_type, variant_id, injection_method, original_source_type).
        """
        manifest: list[dict[str, Any]] = []
        modified = list(docs)  # shallow copy — we'll replace entries

        for attack_def in self._attack_defs:
            attack_type = attack_def["attack_type"]
            variants = attack_def["variants"]

            # Pick eligible docs (match any of the variant target_sources)
            all_target_sources: set[str] = set()
            for v in variants:
                all_target_sources.update(v.get("target_sources", []))

            eligible_indices = [
                i
                for i, d in enumerate(modified)
                if d["source_type"] in all_target_sources
                and not any(m["doc_id"] == d["id"] for m in manifest)
            ]

            if not eligible_indices:
                continue

            # Select docs to poison
            n = min(self._num_per_type, len(eligible_indices))
            chosen_indices = random.sample(eligible_indices, n)

            for idx in chosen_indices:
                doc = dict(modified[idx])  # copy the doc dict
                variant = random.choice(variants)
                method = random.choice(INJECTION_METHODS)

                doc["content"] = self._inject_payload(
                    doc["content"], variant["payload"], method
                )
                doc["id"] = f"{doc['id']}-poisoned"

                modified[idx] = doc
                manifest.append({
                    "doc_id": doc["id"],
                    "attack_type": attack_type,
                    "variant_id": variant["id"],
                    "variant_name": variant["name"],
                    "injection_method": method,
                    "original_source_type": doc["source_type"],
                    "success_patterns": variant.get("success_patterns", []),
                })

        return modified, manifest

    @property
    def attack_types(self) -> list[str]:
        """Return loaded attack type names."""
        return [a["attack_type"] for a in self._attack_defs]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_attack_definitions(self) -> list[dict]:
        defs: list[dict] = []
        attacks_path = Path(self._attacks_dir)
        for yaml_file in sorted(attacks_path.glob("*.yaml")):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and "variants" in data:
                defs.append(data)
        return defs

    @staticmethod
    def _inject_payload(content: str, payload: str, method: str) -> str:
        """Embed *payload* into *content* using the specified method."""
        payload = payload.strip()

        if method == "append":
            return f"{content}\n\n{payload}"

        if method == "html_comment":
            wrapped = f"<!-- {payload} -->"
            return f"{content}\n\n{wrapped}"

        if method == "middle":
            lines = content.split("\n")
            mid = len(lines) // 2
            lines.insert(mid, f"\n{payload}\n")
            return "\n".join(lines)

        # Fallback — append
        return f"{content}\n\n{payload}"
