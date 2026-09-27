from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Any

from regions import Region

import requests


BOOT_URL = "https://boot.pluto.tv/v4/start"
CHANNELS_URL = "https://service-channels.clusters.pluto.tv/v2/guide/channels"

APP_VERSION = "8.1.0"

# Pluto regional/audio preference.
# MX is the primary region; the language list is sent in preference order
# so Pluto can fall back from Mexican Spanish to LATAM/base Spanish.
PLUTO_COUNTRY = "MX"
PLUTO_MARKETING_REGION = "MX"

# Pluto decide parte de la disponibilidad regional según la IP de origen.
# Usamos la misma IP regional de México empleada por clientes públicos de
# referencia; no sustituye nuestros canales, solo ayuda a que el backend
# entregue el perfil regional correcto.
PLUTO_X_FORWARDED_FOR = "200.68.128.83"

PLUTO_LANGUAGE_PREFERENCES = (
    "es-MX",
    "es-419",
    "es",
)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = (10, 45)
MAX_RETRIES = 3


class PlutoClient:

    def __init__(self, region: Region | None = None) -> None:
        if region is None:
            from regions import get_region
            region = get_region("mx")

        self.region = region
        self.session = requests.Session()

        # Reintentos cortos para fallos transitorios de Pluto/GitHub Actions.
        # No cambia el contenido de la lista; solo evita perder una ejecución
        # por un timeout o un 5xx puntual.
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry = Retry(
            total=MAX_RETRIES,
            connect=MAX_RETRIES,
            read=MAX_RETRIES,
            status=MAX_RETRIES,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Origin": "https://pluto.tv",
                "Referer": "https://pluto.tv/",
                "Accept-Language": f"{region.language},es-419,es,en;q=0.1",
                "X-Forwarded-For": region.forwarded_ip,
            }
        )

        # Identificador efímero.
        # No se guarda en config/client.json.
        self.client_id = str(uuid.uuid4())

        self.session_token: str | None = None
        self.stitcher_url: str | None = None
        self.stitcher_params: str = ""
        self.active_country = region.country
        self.active_language = region.language
        self.token_expiry: int = 0

    @staticmethod
    def _token_expiry(token: str) -> int:
        """
        Obtiene el campo exp del JWT sin validar su firma.
        Solo se utiliza para saber cuándo renovar la sesión.
        """

        try:
            parts = token.split(".")

            if len(parts) != 3:
                return 0

            payload = parts[1]

            padding = "=" * (-len(payload) % 4)

            decoded = base64.urlsafe_b64decode(
                payload + padding
            )

            data = json.loads(decoded)

            return int(data.get("exp", 0))

        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ):
            return 0

    def boot(self) -> dict[str, Any]:
        """
        Obtiene una nueva sesión de Pluto.
        """

        params = {
            "appName": "web",
            "appVersion": APP_VERSION,
            "deviceVersion": "133.0.0",
            "deviceModel": "web",
            "deviceMake": "chrome",
            "deviceType": "web",
            "clientID": self.client_id,
            "clientModelNumber": "1.0.0",
            "serverSideAds": "false",
            "features": "multiAudio",
            "drmCapabilities": "widevine:L3",
            "blockingMode": "",
            # Force Pluto to build the session for Mexico and prefer
            # Mexican/Latin-American Spanish audio.
            "country": self.region.country,
            "marketingRegion": self.region.marketing_region,
            "preferredLanguage": self.active_language,
        }

        response = self.session.get(
            BOOT_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        token = data.get("sessionToken")

        if not token:
            raise RuntimeError(
                "Pluto no devolvió sessionToken."
            )

        stitcher = (
            data.get("servers", {})
            .get("stitcher")
        )

        if not stitcher:
            raise RuntimeError(
                "Pluto no devolvió servidor stitcher."
            )

        self.session_token = token

        self.token_expiry = self._token_expiry(
            token
        )

        self.stitcher_url = stitcher

        self.stitcher_params = data.get(
            "stitcherParams",
            "",
        )

        return data

    def ensure_session(self) -> None:
        """
        Garantiza que exista una sesión válida.
        Renueva el token si está ausente o próximo a expirar.
        """

        if (
            self.session_token
            and self.stitcher_url
            and self.token_expiry
            and time.time() < self.token_expiry - 60
        ):
            return

        self.boot()

    def get_channels(self) -> list[dict]:
        """
        Obtiene los canales disponibles.
        """

        self.ensure_session()

        headers = {
            "Accept": "application/json",
            "Authorization": (
                f"Bearer {self.session_token}"
            ),
            "Origin": "https://pluto.tv",
            "Referer": "https://pluto.tv/",
            "Accept-Language": f"{self.region.language},es-419,es,en;q=0.1",
            "X-Forwarded-For": self.region.forwarded_ip,
        }

        # La API determina la región mediante la sesión/token y los
        # headers. No forzamos country/region en la query.
        params = {
            "channelIds": "",
            "offset": "0",
            "limit": "1000",
            "sort": "number:asc",
        }

        response = self.session.get(
            CHANNELS_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        # Si la sesión expiró entre boot y channels,
        # renovamos una vez y repetimos.
        if response.status_code in (401, 403):
            self.boot()

            headers["Authorization"] = (
                f"Bearer {self.session_token}"
            )

            response = self.session.get(
                CHANNELS_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

        response.raise_for_status()

        data = response.json()

        channels = data.get("data", [])

        if not isinstance(channels, list):
            raise RuntimeError(
                "Respuesta de canales inválida."
            )

        # Pluto puede responder 200 con catálogo vacío. US tiene un
        # segundo intento sin el X-Forwarded-For regional.
        if not channels and self.region.code == "us":
            fallback_headers = dict(headers)
            fallback_headers.pop("X-Forwarded-For", None)

            self.boot()

            fallback_headers["Authorization"] = (
                f"Bearer {self.session_token}"
            )

            fallback = self.session.get(
                CHANNELS_URL,
                params=params,
                headers=fallback_headers,
                timeout=REQUEST_TIMEOUT,
            )
            fallback.raise_for_status()

            fallback_data = fallback.json()
            fallback_channels = fallback_data.get("data", [])

            if not isinstance(fallback_channels, list):
                raise RuntimeError(
                    "Respuesta de canales US inválida."
                )

            channels = fallback_channels

        if not channels:
            raise RuntimeError(
                f"{self.region.code.upper()}: Pluto devolvió 0 canales."
            )

        return channels

    def build_stream_url(
        self,
        channel_id: str,
    ) -> str:
        """
        Construye una URL HLS usando la sesión actual.
        """

        if not channel_id:
            raise ValueError(
                "channel_id vacío."
            )

        self.ensure_session()

        if not self.stitcher_url:
            raise RuntimeError(
                "Pluto no devolvió servidor stitcher."
            )

        if not self.session_token:
            raise RuntimeError(
                "No existe sessionToken."
            )

        url = (
            f"{self.stitcher_url}"
            f"/v2/stitch/hls/channel/"
            f"{channel_id}/master.m3u8"
            f"?jwt={self.session_token}"
            f"&masterJWTPassthrough=true"
        )

        if self.stitcher_params:
            url += (
                f"&{self.stitcher_params}"
            )

        # Keep the language preference explicit even if Pluto's boot response
        # does not echo it into stitcherParams.
        # Do not force a lower quality. Pluto can return 720p, 1080p or higher
        # depending on the channel and manifest available for this region.
        url += (
            f"&country={self.region.country}"
            f"&marketingRegion={self.region.marketing_region}"
            f"&preferredLanguage={self.active_language}"
            f"&quality=1080p"
        )

        return url


if __name__ == "__main__":

    from regions import get_region
    client = PlutoClient(get_region("mx"))

    print(
        "Inicializando sesión Pluto..."
    )

    client.boot()

    print(
        "OK: sesión obtenida"
    )

    print(
        "Client ID:",
        client.client_id
    )

    print(
        "Stitcher:",
        client.stitcher_url
    )

    print(
        "Token válido hasta:",
        client.token_expiry
    )

    channels = client.get_channels()

    print(
        "Canales recibidos:",
        len(channels)
    )

    if not channels:
        raise RuntimeError(
            "Pluto no devolvió canales."
        )

    first = channels[0]

    print()
    print("Primer canal:")
    print(
        "ID:",
        first.get("id")
    )
    print(
        "Nombre:",
        first.get("name")
    )
    print(
        "Slug:",
        first.get("slug")
    )

    stream = client.build_stream_url(
        first.get("id", "")
    )

    print()
    print(
        "URL HLS generada correctamente."
    )

    print(
        "Longitud:",
        len(stream)
    )
