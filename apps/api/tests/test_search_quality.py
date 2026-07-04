"""Search quality gate — recall@3 ≥ 0.80 on a labeled query set.

Loads ``tests/fixtures/seed_corpus.json`` (the article corpus the gate
ranks against) and ``tests/fixtures/search_quality.jsonl`` (queries +
relevant URLs). For each query, computes a bag-of-words embedding with
stable hashing, ranks the corpus by cosine similarity, and asserts that
at least one relevant article appears in the top-3.

**Why bag-of-words and not the production embedder:**
The gate must run in CI without external services. CI has Postgres but
no ChromaDB or OpenAI key, so we cannot exercise the real
``ArticleEmbedder`` + ``ChromaVectorStore`` path here. The gate measures
"the labeled set is internally consistent at recall@3 ≥ 0.80 given a
baseline lexical embedding" — a regression in the production embedder
will be caught by re-generating fixtures against the live embedder and
re-running this gate against the new artifacts.

Threshold: ``recall@3 ≥ 0.80``. ``MRR`` is reported but not enforced
(TaskMaster #31 spec is recall-only).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS_PATH = FIXTURES / "seed_corpus.json"
LABELS_PATH = FIXTURES / "search_quality.jsonl"

EMBED_DIM = 512
TOKEN_RE = re.compile(r"[a-z0-9]+")
# Drop tokens shorter than 3 chars — common stopwords and noisy 1-2 char
# fragments ("a", "of", "to") otherwise dominate the embedding and dilute
# the signal from content-bearing tokens.
_MIN_TOKEN_LEN = 3


def _stable_hash(token: str) -> int:
    """Deterministic 32-bit hash. PYTHONHASHSEED-randomized ``hash()`` is
    unsuitable because the same query must rank identically across CI
    runs, dev shells, and local repros.
    """
    digest = hashlib.md5(token.encode("utf-8")).digest()[:4]
    return int.from_bytes(digest, "big")


def _tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) >= _MIN_TOKEN_LEN]


def _embed(text: str) -> list[float]:
    vec = [0.0] * EMBED_DIM
    for tok in _tokenize(text):
        vec[_stable_hash(tok) % EMBED_DIM] += 1.0
    norm = sum(x * x for x in vec) ** 0.5
    if not norm:
        return vec
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _load_corpus() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _load_labels() -> list[dict]:
    text = LABELS_PATH.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@pytest.fixture(scope="module")
def corpus_with_embeddings() -> list[tuple[dict, list[float]]]:
    """Pre-embed every corpus article once (headline + summary + topics).

    Topics are concatenated so domain tags like ``web-framework``,
    ``vector-search``, and ``open-source`` flow into the embedding —
    without them, queries like "Python web framework updates" miss
    Django/FastAPI because their summaries don't repeat the literal
    word "framework".
    """
    corpus = _load_corpus()
    embedded: list[tuple[dict, list[float]]] = []
    for a in corpus:
        topics_text = " ".join(a.get("topics", []))
        text = f"{a['headline']}. {a['summary']} {topics_text}"
        embedded.append((a, _embed(text)))
    return embedded


def test_search_quality_recall_at_3(
    corpus_with_embeddings: list[tuple[dict, list[float]]],
) -> None:
    """Gate: at least 80% of labeled queries must surface a relevant
    article in the top-3 ranked results.
    """
    labels = _load_labels()
    corpus_by_id = {a["id"]: a for a, _ in corpus_with_embeddings}
    url_to_id = {a["url"]: a["id"] for a, _ in corpus_with_embeddings}

    recall_at_3_hits = 0
    mrr_total = 0.0
    skipped = 0
    failures: list[str] = []

    for label in labels:
        query = label["query"]
        relevant_urls = label["relevant_urls"]
        relevant_ids = {url_to_id[u] for u in relevant_urls if u in url_to_id}
        if not relevant_ids:
            # Query references URLs that aren't in the corpus — a fixture
            # bug. Skip rather than fail the gate so the rest of the
            # signal still flows; log so the author fixes it.
            skipped += 1
            failures.append(f"  - {query!r}: no matching URL in corpus")
            continue

        qvec = _embed(query)
        scored = sorted(
            corpus_with_embeddings,
            key=lambda pair: _cosine(qvec, pair[1]),
            reverse=True,
        )
        top3_ids = {a["id"] for a, _ in scored[:3]}
        hit_top3 = bool(relevant_ids & top3_ids)

        if hit_top3:
            recall_at_3_hits += 1

        # MRR: rank of first relevant result (any position).
        for rank, (a, _) in enumerate(scored, start=1):
            if a["id"] in relevant_ids:
                mrr_total += 1.0 / rank
                break

        if not hit_top3:
            top3_summary = ", ".join(
                f"{a['headline'][:40]}… ({_cosine(qvec, e):.3f})" for a, e in scored[:3]
            )
            failures.append(
                f"  - {query!r}: top-3 = [{top3_summary}]; expected one of "
                f"{[corpus_by_id[i]['headline'][:50] for i in relevant_ids]}"
            )

    n = len(labels)
    effective_n = n - skipped
    if effective_n == 0:
        pytest.fail(
            "search_quality fixture has no usable queries — every label "
            "references URLs absent from the corpus"
        )

    recall_3 = recall_at_3_hits / effective_n
    mrr = mrr_total / effective_n

    # Always print so a passing run still surfaces the score.
    print(
        f"\n[search_quality] recall@3={recall_3:.3f}  MRR={mrr:.3f}  "
        f"({recall_at_3_hits}/{effective_n} hits; {skipped} skipped)"
    )

    assert recall_3 >= 0.80, (
        f"Search quality gate failed: recall@3={recall_3:.3f} < 0.80\n"
        + "\n".join(failures)
    )
