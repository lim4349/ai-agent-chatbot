"""Search source profiles and alias resolution."""

from __future__ import annotations

import re

from src.search.models import ContentTypeProfile, SourceProfile

PAPERS = ContentTypeProfile(
    id="papers",
    aliases=("논문", "paper", "papers", "daily papers", "research paper"),
    search_terms=("papers",),
)

NEWS = ContentTypeProfile(
    id="news",
    aliases=("뉴스", "news", "announcement", "발표"),
    search_terms=("news",),
)

BLOG = ContentTypeProfile(
    id="blog",
    aliases=("블로그", "blog", "post", "article", "글"),
    search_terms=("blog",),
)

MODELS = ContentTypeProfile(
    id="models",
    aliases=("모델", "model", "models"),
    search_terms=("models",),
)

DATASETS = ContentTypeProfile(
    id="datasets",
    aliases=("데이터셋", "dataset", "datasets"),
    search_terms=("datasets",),
)

DEFAULT_SOURCE_PROFILES: tuple[SourceProfile, ...] = (
    SourceProfile(
        id="huggingface",
        canonical_name="Hugging Face",
        aliases=("hf", "huggingface", "hugging face", "hf.co", "허깅페이스"),
        site="huggingface.co",
        content_types={
            "papers": ContentTypeProfile(
                id="papers",
                aliases=PAPERS.aliases,
                search_terms=("Hugging Face Daily Papers",),
                date_url_template="https://huggingface.co/papers/date/{date}",
            ),
            "models": MODELS,
            "datasets": DATASETS,
        },
    ),
    SourceProfile(
        id="arxiv",
        canonical_name="arXiv",
        aliases=("arxiv", "아카이브", "아카이브 논문"),
        site="arxiv.org",
        content_types={"papers": ContentTypeProfile("papers", PAPERS.aliases, ("arXiv",))},
    ),
    SourceProfile(
        id="openai",
        canonical_name="OpenAI",
        aliases=("openai", "오픈ai", "오픈에이아이"),
        site="openai.com",
        content_types={
            "blog": ContentTypeProfile("blog", BLOG.aliases, ("OpenAI blog",)),
            "news": ContentTypeProfile("news", NEWS.aliases, ("OpenAI news",)),
            "papers": ContentTypeProfile("papers", PAPERS.aliases, ("OpenAI research",)),
        },
    ),
    SourceProfile(
        id="nvidia",
        canonical_name="NVIDIA",
        aliases=("nvidia", "엔비디아"),
        site="nvidia.com",
        content_types={
            "blog": ContentTypeProfile("blog", BLOG.aliases, ("NVIDIA blog",)),
            "news": ContentTypeProfile("news", NEWS.aliases, ("NVIDIA news",)),
            "papers": ContentTypeProfile("papers", PAPERS.aliases, ("NVIDIA research",)),
        },
    ),
    SourceProfile(
        id="google_deepmind",
        canonical_name="Google DeepMind",
        aliases=("google deepmind", "deepmind", "구글 딥마인드", "딥마인드"),
        site="deepmind.google",
        content_types={
            "blog": ContentTypeProfile("blog", BLOG.aliases, ("Google DeepMind blog",)),
            "news": ContentTypeProfile("news", NEWS.aliases, ("Google DeepMind news",)),
            "papers": ContentTypeProfile("papers", PAPERS.aliases, ("Google DeepMind research",)),
        },
    ),
)

GLOBAL_CONTENT_TYPES: tuple[ContentTypeProfile, ...] = (PAPERS, NEWS, BLOG, MODELS, DATASETS)


class SourceResolver:
    """Resolve source aliases from free-form user queries."""

    def __init__(self, profiles: tuple[SourceProfile, ...] = DEFAULT_SOURCE_PROFILES) -> None:
        self.profiles = profiles

    def resolve(self, query: str) -> SourceProfile | None:
        """Return the first matching source profile."""
        lowered = query.lower()
        for profile in self.profiles:
            if any(alias_matches(lowered, alias) for alias in profile.aliases):
                return profile
        return None


class ContentIntentResolver:
    """Resolve requested content type from query and source profile."""

    def __init__(self, global_content_types: tuple[ContentTypeProfile, ...] = GLOBAL_CONTENT_TYPES):
        self.global_content_types = global_content_types

    def resolve(
        self,
        query: str,
        source: SourceProfile | None = None,
    ) -> ContentTypeProfile | None:
        """Return the requested content type profile if present."""
        lowered = query.lower()
        candidates = tuple(source.content_types.values()) if source else self.global_content_types
        for content_type in candidates:
            if any(alias_matches(lowered, alias) for alias in content_type.aliases):
                return content_type
        return None


def alias_matches(text: str, alias: str) -> bool:
    """Return whether an alias matches, allowing Korean particles after ASCII aliases."""
    normalized_alias = alias.lower()
    if re.fullmatch(r"[a-z0-9.]+", normalized_alias):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])", text))
    return normalized_alias in text
