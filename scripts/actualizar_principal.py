# ============================================================
# BUSCAR CATEGORÍA DEL PAÍS EN LA PRINCIPAL
# ============================================================

def buscar_categoria_principal(
    pais,
    categorias_existentes,
):
    """
    Devuelve ÚNICAMENTE la categoría destino del país.

    Reglas:

    CHILE:
        CL.m3u -> CHILE TV

    Nunca:
        CHILE
        CHILE TV Y RADIO

    Resto:
        Busca la categoría correspondiente al país.
    """

    if not pais:
        return None

    pais = normalizar_texto(pais)

    # ========================================================
    # CHILE
    # ========================================================

    if pais == "chile":

        for categoria in categorias_existentes.values():

            if (
                normalizar_texto(categoria)
                == "chile tv"
            ):
                return categoria

        # Si todavía no existe, el llamador debe crear
        # exactamente CHILE TV.
        return None

    # ========================================================
    # RESTO DE PAÍSES
    # ========================================================

    alias = PAISES.get(
        pais,
        set(),
    )

    alias_normalizados = {
        normalizar_texto(x)
        for x in alias
    }

    # --------------------------------------------------------
    # Coincidencia exacta
    # --------------------------------------------------------

    for categoria in categorias_existentes.values():

        categoria_normalizada = normalizar_texto(
            categoria
        )

        if categoria_normalizada in alias_normalizados:
            return categoria

    # --------------------------------------------------------
    # Coincidencia por palabras
    # --------------------------------------------------------

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
    Determina la categoría FINAL.

    REGLAS:

    - CL.m3u -> CHILE TV
    - Nunca crear/usar CHILE
    - Nunca modificar CHILE TV Y RADIO
    - Cada país va a SU propia categoría.
    - Pluto -> PLUTO TV
    - IPTVSV -> según categoría del canal.
    """

    categoria_fuente = canal.get(
        "categoria",
        "",
    ).strip()

    categoria_configurada = fuente.get(
        "categoria",
        "OTROS",
    ).strip()

    # ========================================================
    # FUENTE FORZADA
    # ========================================================

    if fuente.get("forzar_categoria"):

        categoria_forzada = (
            categoria_configurada
        )

        # Seguridad absoluta:
        # ninguna fuente puede terminar creando CHILE.
        if (
            normalizar_texto(categoria_forzada)
            == "chile"
        ):
            return "CHILE TV"

        return categoria_forzada

    # ========================================================
    # CATEGORÍA DEL CANAL
    # ========================================================

    categoria_para_pais = (
        categoria_fuente
        or categoria_configurada
    )

    pais = identificar_pais(
        categoria_para_pais
    )

    # ========================================================
    # CHILE
    # ========================================================

    if pais == "chile":

        categoria_chile = (
            buscar_categoria_principal(
                "chile",
                categorias_existentes,
            )
        )

        if categoria_chile:
            return categoria_chile

        # IMPORTANTE:
        # si no existe, se crea CHILE TV,
        # nunca CHILE.
        return "CHILE TV"

    # ========================================================
    # RESTO DE PAÍSES
    # ========================================================

    if pais:

        categoria_principal = (
            buscar_categoria_principal(
                pais,
                categorias_existentes,
            )
        )

        if categoria_principal:
            return categoria_principal

        # Si todavía no existe la carpeta del país,
        # se utiliza el nombre configurado por la fuente.
        return categoria_para_pais

    # ========================================================
    # CATEGORÍA NORMAL
    # ========================================================

    if (
        categoria_fuente
        and normalizar_texto(categoria_fuente)
        != "otros"
    ):
        return categoria_fuente

    return categoria_configurada