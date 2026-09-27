from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    country: str
    marketing_region: str
    forwarded_ip: str
    language: str


# Regional source addresses are used only as Pluto's regional hint.
# They are public examples also used by other Pluto clients; they are not
# used to replace or remove any channel from another region.
REGIONS = {
    "cl": Region("cl", "Chile", "CL", "CL", "161.238.0.0", "es-CL"),
    "mx": Region("mx", "Mexico", "MX", "MX", "200.68.128.83", "es-MX"),
    "ar": Region("ar", "Argentina", "AR", "AR", "104.103.238.0", "es-AR"),
    "br": Region("br", "Brasil", "BR", "BR", "177.47.27.205", "pt-BR"),
    "es": Region("es", "España", "ES", "ES", "88.26.241.248", "es-ES"),
    "us": Region("us", "United States", "US", "US", "185.236.200.172", "en-US"),
}


def get_region(code: str) -> Region:
    key = code.lower().strip()
    try:
        return REGIONS[key]
    except KeyError as exc:
        raise ValueError(f"Región no configurada: {code}") from exc
