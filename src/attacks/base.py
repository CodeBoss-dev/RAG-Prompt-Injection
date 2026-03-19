"""Abstract base class for attack scenarios."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from config.settings import settings


class Attack(ABC):
    """Base class for attack scenarios.

    Each attack loads its variant definitions from the corresponding YAML
    file in ``data/attacks/`` and uses the ground-truth manifest produced
    by the data generation step to know which documents were poisoned.

    Subclasses must implement :pyattr:`attack_type`, :pymeth:`setup`,
    :pymeth:`execute`, and :pymeth:`detect_success`.
    """

    @property
    @abstractmethod
    def attack_type(self) -> str:
        """Identifier matching the YAML ``attack_type`` field."""
        ...

    @abstractmethod
    def setup(self, pipeline: Any, manifest: list[dict]) -> None:
        """Prepare the attack (e.g., select target queries, load variants).

        Parameters
        ----------
        pipeline:
            A configured :class:`RAGPipeline` instance.
        manifest:
            The ground-truth manifest (list of poisoned-doc records).
        """
        ...

    @abstractmethod
    def execute(
        self,
        pipeline: Any,
        user_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run the attack, returning a list of result dicts.

        Each result dict contains:
        - ``query`` (str): The query that was executed.
        - ``response`` (str): The LLM-generated response.
        - ``success`` (bool): Whether the attack succeeded.
        - ``details`` (dict): Additional info (matched patterns, variant, etc.).

        Parameters
        ----------
        pipeline:
            A configured :class:`RAGPipeline` instance.
        user_context:
            Optional user context dict passed to the pipeline.
        """
        ...

    @abstractmethod
    def detect_success(self, response: str, variant: dict) -> bool:
        """Check if the attack succeeded based on the response text.

        Parameters
        ----------
        response:
            The LLM-generated response string.
        variant:
            The attack variant dict (from YAML), which includes
            ``success_patterns``.

        Returns
        -------
        bool
            True if the attack succeeded.
        """
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def load_variants(self) -> list[dict]:
        """Load variant definitions from the YAML file for this attack type.

        Returns
        -------
        list[dict]
            List of variant dicts, each with ``id``, ``name``, ``payload``,
            ``target_sources``, and ``success_patterns``.
        """
        yaml_path = Path(settings.data_attacks_dir) / f"{self.attack_type}.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Attack definition not found: {yaml_path}"
            )
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        return data.get("variants", [])

    def filter_manifest(self, manifest: list[dict]) -> list[dict]:
        """Return only manifest entries matching this attack type."""
        return [
            entry for entry in manifest
            if entry.get("attack_type") == self.attack_type
        ]

    @staticmethod
    def check_patterns(response: str, patterns: list[str]) -> list[str]:
        """Check which success patterns match in the response.

        Parameters
        ----------
        response:
            The LLM response text.
        patterns:
            List of regex pattern strings.

        Returns
        -------
        list[str]
            The subset of patterns that matched.
        """
        matched: list[str] = []
        for pattern in patterns:
            try:
                if re.search(pattern, response, re.IGNORECASE):
                    matched.append(pattern)
            except re.error:
                # Fall back to literal match if regex is invalid
                if pattern.lower() in response.lower():
                    matched.append(pattern)
        return matched

    @staticmethod
    def load_manifest(manifest_path: Path | str | None = None) -> list[dict]:
        """Load the ground-truth manifest from disk.

        Parameters
        ----------
        manifest_path:
            Path to ``manifest.json``.  Defaults to
            ``settings.data_output_dir / "manifest.json"``.
        """
        if manifest_path is None:
            manifest_path = Path(settings.data_output_dir) / "manifest.json"
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found at {manifest_path}. "
                "Run `python scripts/generate_data.py` first."
            )
        with open(manifest_path) as f:
            return json.load(f)
