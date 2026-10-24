"""Minimal feature extraction for the two pre-trained CatBoost field classifiers."""
import numpy as np
TARGETS = ["Birth_place_ru", "Issue_organization_ru"]

def raw_text(p, k):
    v = (p.get("viz") or {}).get(k) or {}
    return " ".join(" ".join(str(z.get("text", "")) for z in (v.get("lines") or [])).upper().split())

def field_features(p, k):
    v = (p.get("viz") or {}).get(k) or {}
    lines = v.get("lines") or []
    s = raw_text(p, k)
    chars = [float(c) for line in lines for c in (line.get("char_conf") or [])]
    b = v.get("box") or [0, 0, 0, 0]
    return [len(s), len(s.split()), len(lines), float(v.get("conf") or 0),
            min(chars, default=0), float(np.mean(chars)) if chars else 0,
            sum(x < .995 for x in chars), sum(x < .999 for x in chars),
            float(b[2]), float(b[3]),
            len(lines[-1].get("text", "")) if lines else 0]
