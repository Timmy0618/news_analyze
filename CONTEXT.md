# Domain Glossary

Shared names for the concepts in this codebase. Use these terms in code,
tests, and architecture discussion so a name always means one thing.

## Byline

The reporter attribution of an article — a person's name, or `未提及` when the
piece is unsigned. Extracted purely from article markdown by
`news_scraper/byline.py::extract_byline(content) -> str`, with no network or
scraper instance required. Desk-only credits (`即時新聞／綜合報導`) count as
unsigned, not as a byline. Stored on `NewsArticle` as `記者` / `reporter`.
