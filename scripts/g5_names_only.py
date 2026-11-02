"""G5 study 4, H10: can the cause be predicted from identifiers alone?

A classifier sees ONLY the opaque identifiers of an instance: the public dataset_id, the
zone and restaurant tokens (and the zone of each restaurant). It is trained on the
development seed and tested on the final seed (L0-L2, 20 per level, as in G3).
Pre-registered prediction: accuracy <= majority class + 0.10.

Usage: uv run python scripts/g5_names_only.py [--train-per-level 100]
Output: docs/reports/G5_NAMES_ONLY.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from g3_report import wilson
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import LogisticRegression

from deliverytwin.benchmark.generator import generate_instance

ROOT = Path(__file__).resolve().parents[1]
DEV, FINAL = 2026, 515_151
LEVELS = ("L0", "L1", "L2")


def names_text(job) -> tuple[str, str, str]:
    level, i, seed = job
    inst = generate_instance(level, i, master_seed=seed)
    tel = inst.public
    parts = [tel.dataset_id] + [f"{e.kind}:{e.token}:z{e.zone}" for e in tel.entities]
    return level, " ".join(parts), inst.private.family


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-per-level", type=int, default=100)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    train_jobs = [(lv, i, DEV) for lv in LEVELS for i in range(a.train_per_level)]
    test_jobs = [(lv, i, FINAL) for lv in LEVELS for i in range(20)]
    with ProcessPoolExecutor(a.workers) as ex:
        train = list(ex.map(names_text, train_jobs))
        test = list(ex.map(names_text, test_jobs))
    vec = HashingVectorizer(analyzer="char_wb", ngram_range=(2, 4), n_features=2**16,
                            alternate_sign=False)
    rep = {"train_n": len(train), "test_n": len(test), "per_level": {}}
    for lv in LEVELS:
        tr = [(x, y) for level, x, y in train if level == lv]
        te = [(x, y) for level, x, y in test if level == lv]
        clf = LogisticRegression(max_iter=2000).fit(vec.transform([x for x, _ in tr]),
                                                    [y for _, y in tr])
        pred = clf.predict(vec.transform([x for x, _ in te]))
        k = sum(p == y for p, (_, y) in zip(pred, te, strict=True))
        maj_label = Counter(y for _, y in tr).most_common(1)[0][0]
        km = sum(y == maj_label for _, y in te)
        n = len(te)
        rep["per_level"][lv] = {"n_train": len(tr), "n_test": n, "names_only_correct": k,
                                "names_only_acc": round(k / n, 3), "ci": wilson(k, n),
                                "majority_correct": km, "majority_acc": round(km / n, 3),
                                "label": "principal",
                                "within_prediction": k / n <= km / n + 0.10}
    (ROOT / "docs" / "reports" / "G5_NAMES_ONLY.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
