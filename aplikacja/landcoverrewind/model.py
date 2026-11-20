"""Random Forest models: sampling, training, saving, loading and prediction.

Hyperparameters follow the reference project model (GEE smileRandomForest): 300 trees, 4 features per split,
minimum leaf size 1, seed 42, 1500 training points per class.
"""
from __future__ import annotations
import json
import pathlib
import warnings
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from .features import NAMES

MODEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "models"
# The models use 18 of the 19 features. NDVI amplitude (feature 19) was unstable between epochs
# (inflated in 1985, which suppressed built-up detections) and is therefore excluded.
USED = list(range(18))


def select_features(X, n_features):
    """Keep the feature columns the model was trained on."""
    return X[:, USED] if (X.shape[1] == 19 and n_features == 18) else X


def sample_points(labels: np.ndarray, F: np.ndarray, per_class=1500, seed=42, mask=None):
    """Stratified sampling: up to `per_class` pixels of each class with complete features (label 255 = ignore)."""
    rng = np.random.default_rng(seed)
    ok = np.all(np.isfinite(F), axis=0) & (labels != 255)
    if mask is not None:
        ok &= mask
    X, y = [], []
    for k in np.unique(labels[ok]):
        idx = np.flatnonzero(ok & (labels == k))
        pick = rng.choice(idx, size=min(per_class, idx.size), replace=False)
        X.append(F.reshape(F.shape[0], -1)[:, pick].T)
        y.append(np.full(pick.size, k))
    return np.vstack(X), np.concatenate(y)


def train(X, y, seed=42, n_jobs=-1):
    rf = RandomForestClassifier(n_estimators=300, max_features=4, min_samples_leaf=1,
                                n_jobs=n_jobs, random_state=seed, oob_score=True)
    rf.fit(X[:, USED] if X.shape[1] == 19 else X, y)
    return rf


def save(rf, name: str, card: dict, directory=None):
    d = pathlib.Path(directory) if directory else MODEL_DIR
    d.mkdir(exist_ok=True, parents=True)
    joblib.dump(rf, d / f"{name}.joblib", compress=3)
    card = dict(card, features=[NAMES[i] for i in USED] if rf.n_features_in_ == 18 else NAMES,
                classes=[int(c) for c in rf.classes_], oob=float(getattr(rf, "oob_score_", np.nan)))
    (d / f"{name}.json").write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")


def load(name_or_path: str):
    """Load a model and its card. If the .joblib file does not match the installed scikit-learn version,
    the model is rebuilt from the stored training points (same seed, same result up to library changes)."""
    p = pathlib.Path(name_or_path)
    if not p.suffix:
        p = MODEL_DIR / f"{name_or_path}.joblib"
    card_path = p.with_suffix(".json")
    card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.exists() else {}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", category=UserWarning)
            return joblib.load(p), card
    except Exception:
        d = np.load(p.with_name(p.stem + "_points.npz"))
        return train(d["X"], d["y"], int(card.get("seed", 42))), card


def predict(rf, F: np.ndarray, block=200_000):
    """Class probabilities (n_classes, H, W); pixels without data are NaN."""
    C, H, W = F.shape
    X = select_features(F.reshape(C, -1).T, rf.n_features_in_)
    ok = np.all(np.isfinite(X), axis=1)
    P = np.full((X.shape[0], len(rf.classes_)), np.nan, "float32")
    idx = np.flatnonzero(ok)
    for i in range(0, idx.size, block):
        j = idx[i:i + block]
        P[j] = rf.predict_proba(X[j])
    return P.T.reshape(len(rf.classes_), H, W)
