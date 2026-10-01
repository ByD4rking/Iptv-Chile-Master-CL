import re
import unicodedata

PROFILES = {
    "anime": {
        "terms": {
            "anime": 3, "animacion": 2, "animation": 2, "cartoon": 2,
            "pokemon": 4, "naruto": 4, "dragon ball": 4, "yu gi oh": 4,
            "yu-gi-oh": 4, "beyblade": 3, "death note": 4, "elfen lied": 4,
            "macross": 4, "adult swim": 2, "anime vision": 4,
        },
        "category": "Anime",
    },
    "competition_entertainment": {
        "terms": {
            "wipeout": 5, "wipout": 4, "ninja warrior": 5,
            "american ninja warrior": 5, "superhuman": 5,
            "minute to win it": 5, "minuto para ganar": 5,
            "juego de la oca": 5, "takeshi": 4, "takeshi castle": 5,
            "humor amarillo": 4, "game show": 4, "concurso": 3,
            "concursos": 3, "competencia": 3, "reality": 2,
            "entretenimiento": 2,
        },
        "category": "Competencia y entretenimiento",
    },
    "kids": {
        "terms": {
            "kids": 3, "children": 2, "disney": 3, "disney jr": 4,
            "nick": 2, "nickelodeon": 3, "cartoon network": 3,
            "boomerang": 3, "dibujos": 3,
        },
        "category": "Infantil",
    },
}

def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("_", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())

def classify(name="", group="", slug="", extra=""):
    haystack = normalize(" ".join((name, group, slug, extra)))
    matches = []
    for profile, spec in PROFILES.items():
        score = 0
        matched = []
        for term, weight in spec["terms"].items():
            normalized_term = normalize(term)
            if normalized_term and normalized_term in haystack:
                score += weight
                matched.append(term)
        if score:
            matches.append({
                "profile": profile,
                "category": spec["category"],
                "score": score,
                "matched_terms": sorted(set(matched)),
            })
    matches.sort(key=lambda x: (-x["score"], x["category"]))
    if not matches:
        return {
            "category": "Sin clasificar",
            "profile": None,
            "confidence": 0,
            "matched_terms": [],
            "matches": [],
        }
    best = matches[0]
    # Confidence is intentionally bounded and explainable; it is not a claim
    # about the actual programme currently airing.
    confidence = min(100, best["score"] * 15)
    return {
        "category": best["category"],
        "profile": best["profile"],
        "confidence": confidence,
        "matched_terms": best["matched_terms"],
        "matches": matches,
    }
