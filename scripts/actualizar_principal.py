# ============================================================
# FUENTES EXTERNAS
# ============================================================

FUENTES = [
    {
        "url": "https://m3u.cl/lista/XXX.m3u",
        "categoria": "XXX.Adultos.Porno",
        "forzar_categoria": True,
    },
    {
        "url": "https://m3u.cl/lista/religiosos.m3u",
        "categoria": "Religiosos",
        "forzar_categoria": True,
    },
    {
        "url": "https://m3u.cl/lista/musica.m3u",
        "categoria": "Música",
        "forzar_categoria": True,
    },
    {
        "url": "https://m3u.cl/lista/LATAM.m3u",
        "categoria": "LATAM",
        "forzar_categoria": True,
    },

    # --------------------------------------------------------
    # PAÍSES
    # --------------------------------------------------------

    {
        "url": "https://m3u.cl/lista/VE.m3u",
        "categoria": "Venezuela",
    },
    {
        "url": "https://m3u.cl/lista/DO.m3u",
        "categoria": "República Dominicana",
    },
    {
        "url": "https://m3u.cl/lista/PE.m3u",
        "categoria": "Perú",
    },
    {
        "url": "https://m3u.cl/lista/PY.m3u",
        "categoria": "Paraguay",
    },
    {
        "url": "https://m3u.cl/lista/MX.m3u",
        "categoria": "México",
    },
    {
        "url": "https://m3u.cl/lista/ES.m3u",
        "categoria": "España",
    },
    {
        "url": "https://m3u.cl/lista/EC.m3u",
        "categoria": "Ecuador",
    },
    {
        "url": "https://m3u.cl/lista/CR.m3u",
        "categoria": "Costa Rica",
    },
    {
        "url": "https://m3u.cl/lista/CO.m3u",
        "categoria": "Colombia",
    },
    {
        "url": "https://m3u.cl/lista/CL.m3u",
        "categoria": "Chile",
    },
    {
        "url": "https://m3u.cl/lista/BR.m3u",
        "categoria": "Brasil",
    },
    {
        "url": "https://m3u.cl/lista/BO.m3u",
        "categoria": "Bolivia",
    },
    {
        "url": "https://m3u.cl/lista/AR.m3u",
        "categoria": "Argentina",
    },

    # --------------------------------------------------------
    # PLUTO TV
    # --------------------------------------------------------

    {
        "url": (
            "https://raw.githubusercontent.com/"
            "JMigue85/IPTV-SV/refs/heads/main/"
            "PlutoTV.ES.m3u"
        ),
        "categoria": "PLUTO TV",
        "forzar_categoria": True,
    },
    {
        "url": (
            "https://raw.githubusercontent.com/"
            "JMigue85/IPTV-SV/refs/heads/main/"
            "PlutoTV.MX.m3u"
        ),
        "categoria": "PLUTO TV",
        "forzar_categoria": True,
    },

    # --------------------------------------------------------
    # IPTVSV
    # --------------------------------------------------------

    {
        "url": (
            "https://raw.githubusercontent.com/"
            "JMigue85/IPTV-SV/refs/heads/main/"
            "IPTVSV.m3u"
        ),
        "categoria": "OTROS",
        "forzar_categoria": False,
    },
]


# ============================================================
# BUSCAR CATEGORÍA DEL PAÍS
# ============================================================

def buscar_categoria_principal(
    pais,
    categorias_existentes,
):
    """
    Busca la categoría correspondiente al país.

    REGLA ESPECIAL:

        Chile -> CHILE TV

    Nunca utiliza:

        CHILE
        CHILE TV Y RADIO

    Para los demás países busca la categoría del país
    existente en la lista principal.
    """

    if not pais:
        return None

    # --------------------------------------------------------
    # CHILE
    # --------------------------------------------------------

    if pais == "chile":

        for categoria in categorias_existentes.values():

            if (
                normalizar_texto(categoria)
                == "chile tv"
            ):
                return categoria

        return None

    # --------------------------------------------------------
    # RESTO DE PAÍSES
    # --------------------------------------------------------

    alias = PAISES.get(
        pais,
        set(),
    )

    # Coincidencia exacta
    for categoria in categorias_existentes.values():

        categoria_normalizada = normalizar_texto(
            categoria
        )

        if categoria_normalizada in alias:
            return categoria

    # Coincidencia por palabras
    for categoria in categorias_existentes.values():

        categoria_normalizada = normalizar_texto(
            categoria
        )

        palabras = categoria_normalizada.split()

        if pais == "peru":
            if (
                "peru" in palabras
                and "radio" not in palabras
            ):
                return categoria

        elif pais == "bolivia":
            if "bolivia" in palabras:
                return categoria

        elif pais == "argentina":
            if "argentina" in palabras:
                return categoria

        elif pais == "brasil":
            if (
                "brasil" in palabras
                or "brazil" in palabras
            ):
                return categoria

        elif pais == "colombia":
            if "colombia" in palabras:
                return categoria

        elif pais == "ecuador":
            if "ecuador" in palabras:
                return categoria

        elif pais == "venezuela":
            if "venezuela" in palabras:
                return categoria

        elif pais == "paraguay":
            if "paraguay" in palabras:
                return categoria

        elif pais == "mexico":
            if "mexico" in palabras:
                return categoria

        elif pais == "espana":
            if (
                "espana" in palabras
                or "spain" in palabras
            ):
                return categoria

        elif pais == "costa rica":
            if (
                "costa" in palabras
                and "rica" in palabras
            ):
                return categoria

        elif pais == "republica dominicana":
            if (
                "republica" in palabras
                and "dominicana" in palabras
            ):
                return categoria

    return None


# ============================================================
# RESOLVER CATEGORÍA
# ============================================================

def resolver_categoria(
    canal,
    fuente,
    categorias_existentes,
):
    """
    Determina la categoría FINAL donde debe colocarse
    el canal.

    REGLAS:

    1. Chile -> CHILE TV.
    2. Nunca utilizar CHILE.
    3. Nunca utilizar CHILE TV Y RADIO.
    4. Argentina -> categoría ARGENTINA.
    5. Bolivia -> categoría BOLIVIA.
    6. Etc.
    7. PlutoTV -> PLUTO TV.
    8. IPTVSV -> según la categoría del canal.
    """

    categoria_fuente = canal.get(
        "categoria",
        "",
    ).strip()

    categoria_configurada = fuente.get(
        "categoria",
        "OTROS",
    ).strip()

    # --------------------------------------------------------
    # CATEGORÍA FORZADA
    # --------------------------------------------------------

    if fuente.get("forzar_categoria"):

        # Nunca permitir que una fuente forzada
        # cree accidentalmente CHILE.
        if (
            normalizar_texto(categoria_configurada)
            == "chile"
        ):
            return "CHILE TV"

        return categoria_configurada

    # --------------------------------------------------------
    # IPTVSV / FUENTES QUE SE CLASIFICAN POR CANAL
    # --------------------------------------------------------

    categoria_para_pais = (
        categoria_fuente
        or categoria_configurada
    )

    pais = identificar_pais(
        categoria_para_pais
    )

    # --------------------------------------------------------
    # CHILE
    # --------------------------------------------------------

    if pais == "chile":

        categoria_chile_tv = (
            buscar_categoria_principal(
                "chile",
                categorias_existentes,
            )
        )

        if categoria_chile_tv:
            return categoria_chile_tv

        return "CHILE TV"

    # --------------------------------------------------------
    # PAÍS
    # --------------------------------------------------------

    if pais:

        categoria_principal = (
            buscar_categoria_principal(
                pais,
                categorias_existentes,
            )
        )

        if categoria_principal:
            return categoria_principal

        # Si la categoría del país todavía no existe,
        # utiliza la categoría indicada por la fuente.
        return categoria_para_pais

    # --------------------------------------------------------
    # CATEGORÍA NORMAL
    # --------------------------------------------------------

    if (
        categoria_fuente
        and normalizar_texto(categoria_fuente)
        != "otros"
    ):
        return categoria_fuente

    return categoria_configurada