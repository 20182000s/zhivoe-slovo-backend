"""Semantic shortlist for reflection. Only public corpus text is persisted.

Queries (the private day description) are embedded in memory and never cached.
The index is shared by exact text, model and dimensions, not by user identity.
"""
from array import array
import hashlib
import math
import re
import sqlite3
import threading

MODEL = 'text-embedding-3-small'
DIMENSIONS = 512
DIRECT_LIMIT = 100
INDEX_LOCK = threading.Lock()


def chunks(text, byte_limit=6000):
    """Lossless UTF-8 chunks; byte count is a conservative token upper bound."""
    result = []
    part = ''
    for unit in re.findall(r'\S+\s*|\s+', text):
        # Even a single unbroken word must obey the provider's per-input limit.
        for start in range(0, len(unit), byte_limit // 4):
            piece = unit[start:start + byte_limit // 4]
            if part and len((part + piece).encode()) > byte_limit:
                result.append(part)
                part = ''
            part += piece
    if part:
        result.append(part)
    return result


def vector(values):
    if len(values) != DIMENSIONS or any(not math.isfinite(v) for v in values):
        raise ValueError('Invalid embedding')
    length = math.sqrt(sum(v * v for v in values))
    if length == 0:
        raise ValueError('Empty embedding')
    return array('f', (v / length for v in values))


def cache_key(text):
    return hashlib.sha256(f'{MODEL}:{DIMENSIONS}:v1:{text}'.encode()).hexdigest()


def batches(items):
    batch, size = [], 0
    for item in items:
        n = len(item.encode())
        if batch and (size + n > 180000 or len(batch) >= 512):
            yield batch
            batch, size = [], 0
        batch.append(item)
        size += n
    if batch:
        yield batch


def cached_vectors(texts, embed, db_path, remaining):
    keys = list(dict.fromkeys(cache_key(t) for t in texts))
    lookup = dict(zip((cache_key(t) for t in texts), texts))
    # Deduplicate concurrent cold builds without holding a DB transaction across HTTP.
    if not INDEX_LOCK.acquire(timeout=max(0, min(40, remaining() - 40))):
        raise TimeoutError('Library index is busy')
    try:
        with sqlite3.connect(db_path, timeout=20) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS passage_embeddings (key TEXT PRIMARY KEY, vector BLOB NOT NULL)')
            stored = {}
            for start in range(0, len(keys), 400):
                group = keys[start:start + 400]
                rows = connection.execute('SELECT key,vector FROM passage_embeddings WHERE key IN (' + ','.join('?' for _ in group) + ')', group)
                for key, blob in rows:
                    v = array('f')
                    v.frombytes(blob)
                    if len(v) == DIMENSIONS and all(math.isfinite(x) for x in v) and .99 < sum(x*x for x in v) < 1.01:
                        stored[key] = v
            missing = [lookup[k] for k in keys if k not in stored]
            for batch in batches(missing):
                if remaining() < 40:
                    raise TimeoutError('Library index deadline')
                values = embed(batch, purpose='library_index')
                if len(values) != len(batch):
                    raise ValueError('Incomplete embeddings')
                pairs = [(cache_key(t), vector(v)) for t, v in zip(batch, values)]
                connection.executemany('INSERT OR REPLACE INTO passage_embeddings VALUES (?,?)',
                    [(k, v.tobytes()) for k, v in pairs])
                connection.commit()  # Completed batches survive a later provider failure.
                stored.update(pairs)
        return stored, len(keys) - len(missing), len(missing)
    finally:
        INDEX_LOCK.release()


def queries(story):
    # Whole story plus balanced aspects: a secondary worry should not disappear
    # behind the first/longest part of the user's day.
    units = re.split(r'(?<=[.!?])\s+|\n+', story.strip())
    groups = []
    width = max(1, math.ceil(len(units) / 4))
    for i in range(0, len(units), width):
        groups.extend(chunks(' '.join(units[i:i + width])))
    return list(dict.fromkeys(chunks(story) + groups))


class Search:
    def __init__(self, passages, story, embed, db_path, remaining):
        self.passages = passages
        self.parts = [chunks(p['text']) for p in passages]
        inputs = [p['reference'] + '\n' + part for p, parts in zip(passages, self.parts) for part in parts]
        # A reference may itself be long for a disjoint saved range. Keep every
        # text chunk, but bound its public label rather than discarding verses.
        inputs = [t if len(t.encode()) <= 7500 else t.split('\n', 1)[1] for t in inputs]
        vectors, self.hits, self.misses = cached_vectors(inputs, embed, db_path, remaining)
        query_inputs = queries(story)
        qv = [vector(v) for v in embed(query_inputs, purpose='library_query')]
        if len(qv) != len(query_inputs):
            raise ValueError('Incomplete query embeddings')
        scores, self.best_parts = [], []
        offset = 0
        for parts in self.parts:
            per_chunk = []
            for _ in parts:
                v = vectors[cache_key(inputs[offset])]
                per_chunk.append([sum(a * b for a, b in zip(v, q)) for q in qv])
                offset += 1
            per_query = [max(c[j] for c in per_chunk) for j in range(len(qv))]
            scores.append(per_query)
            self.best_parts.append(max(range(len(parts)), key=lambda k: max(per_chunk[k])))
        # Reserve a few places for each aspect, then fill with strongest matches.
        reserved = []
        quota = max(1, min(4, 24 // len(qv)))
        for j in range(len(qv)):
            for i in sorted(range(len(passages)), key=lambda i: scores[i][j], reverse=True)[:quota]:
                if i not in reserved:
                    reserved.append(i)
        by_score = sorted(range(len(passages)), key=lambda i: max(scores[i]), reverse=True)
        self.order = reserved + [i for i in by_score if i not in reserved]
        peak = max(max(s) for s in scores)
        tops = [max(scores[i]) for i in by_score]
        # Conservative retrieval heuristic, not a claim of calibrated confidence.
        self.weak = peak < .28 or (sum(tops[:5]) / 5 - sum(tops[30:50]) / len(tops[30:50])) < .035
        self.initial_count = min(len(passages), 60 if self.weak else 30)

    def candidates(self, count):
        return [self.passages[i] for i in self.order[:count]]

    def prompt_passages(self, count):
        result = []
        for position, i in enumerate(self.order[:count], 1):
            p, parts = self.passages[i], self.parts[i]
            best = self.best_parts[i]
            # Very long saved ranges still return their original saved ID and
            # exact full text to the app; the model sees an exact contextual span.
            excerpt = len(parts) > 3
            text = ''.join(parts[max(0, best - 1):best + 2]) if excerpt else p['text']
            item = {'id':f'p{position}', 'reference':p['reference'][:600], 'text':text}
            if excerpt:item['excerpt'] = True
            result.append(item)
        return result
