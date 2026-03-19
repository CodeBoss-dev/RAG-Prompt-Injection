"""Synthetic enterprise data generation package."""

from src.data_gen.base import DataSource
from src.data_gen.confluence import ConfluenceGenerator
from src.data_gen.email import EmailGenerator
from src.data_gen.injector import PayloadInjector
from src.data_gen.internal_docs import InternalDocsGenerator
from src.data_gen.slack import SlackGenerator

__all__ = [
    "DataSource",
    "ConfluenceGenerator",
    "EmailGenerator",
    "InternalDocsGenerator",
    "PayloadInjector",
    "SlackGenerator",
]
