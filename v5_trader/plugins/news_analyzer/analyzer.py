"""News sentiment analyzer for Korean equities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from textblob import TextBlob


@dataclass
class NewsHeadline:
    title: str
    url: str


@dataclass
class NewsSentiment:
    title: str
    sentiment: float
    url: str


class NewsAnalyzer:
    """Very lightweight sentiment scoring using TextBlob."""

    def analyze(self, headlines: List[NewsHeadline]) -> List[NewsSentiment]:
        sentiments: List[NewsSentiment] = []
        for headline in headlines:
            blob = TextBlob(headline.title)
            sentiments.append(
                NewsSentiment(title=headline.title, sentiment=float(blob.sentiment.polarity), url=headline.url)
            )
        return sentiments
