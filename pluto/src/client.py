from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Any

import requests


BOOT_URL = "https://boot.pluto.tv/v4/start"
CHANNELS_URL = "https://service-channels.clusters.pluto.tv/v2/guide/channels"

APP_VERSION = "8.0.0-111b2b9dc00bd0bea9030b30662159ed9e7c8bc6"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class PlutoClient:

    def __init__(self) -> None:
        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Origin": "https://pluto.tv",
                "Referer": "https://pluto.tv/",
            }
        )

        # Identificador efímero.
        # No se guarda en config/client.json.
        self.client_id = str(uuid.uuid4())

        self.session_token: str | None = None
        self.stitcher_url: str | None = None
        self.stitcher_params: str = ""
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
            "deviceVersion": "122.0.0",
            "deviceModel": "web",
            "deviceMake": "chrome",
            "deviceType": "web",
            "clientID": self.client_id,
            "clientModelNumber": "1.0.0",
            "serverSideAds": "false",
            "drmCapabilities": "widevine:L3",
            "blockingMode": "",
        }

        response = self.session.get(
            BOOT_URL,
            params=params,
            timeout=30,
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
        }

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
            timeout=30,
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
                timeout=30,
            )

        response.raise_for_status()

        data = response.json()

        channels = data.get("data", [])

        if not isinstance(channels, list):
            raise RuntimeError(
                "Respuesta de canales inválida."
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

        return url


if __name__ == "__main__":

    client = PlutoClient()

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
