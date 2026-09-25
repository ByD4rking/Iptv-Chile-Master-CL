# ============================================================
# BUSCAR CATEGORÍA DEL PAÍS EN LA PRINCIPAL
# ============================================================

def buscar_categoria_principal(
    pais,
    categorias_existentes,
):
    """
    Busca la categoría correspondiente al país.

    REGLA ESPECIAL PARA CHILE:

        CHILE TV
            -> categoría de los canales de TV de Chile

        CHILE TV Y RADIO
            -> NO se utiliza
            -> NO se modifica
            -> NO recibe canales de CL.m3u

        CHILE
            -> NO se utiliza

    Si CHILE TV no existe, devuelve None para que
    resolver_categoria() utilice exactamente CHILE TV.
    """

    if not pais:
        return None

    # ========================================================
    # CHILE
    # ========================================================

    if pais == "chile":

        for categoria in categorias_existentes.values():

            categoria_normalizada = normalizar_texto(
                categoria
            )

            # ÚNICAMENTE CHILE TV
            if categoria_normalizada == "chile tv":
                return categoria

        # No devolver ninguna otra categoría de Chile.
        return None

    # ========================================================
    # RESTO DE PAÍSES
    # ========================================================

    alias = PAISES.get(
        pais,
        set(),
    )

    # --------------------------------------------------------
    # Coincidencia exacta
    # --------------------------------------------------------

    for categoria in categorias_existentes.values():

        categoria_normalizada = normalizar_texto(
            categoria
        )

        if categoria_normalizada in alias:
            return categoria

    # --------------------------------------------------------
    # Variantes
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
    REGLAS DE CATEGORIZACIÓN.

    CHILE:

        CL.m3u
            ↓
        CHILE TV

    Nunca:

        Chile
        CHILE
        CHILE TV Y RADIO

    CHILE TV Y RADIO queda completamente intacta.
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
    # CATEGORÍAS FORZADAS
    # ========================================================

    if fuente.get("forzar_categoria"):
        return categoria_configurada

    # ========================================================
    # IDENTIFICAR PAÍS
    # ========================================================

    pais = identificar_pais(
        categoria_configurada
    )

    # ========================================================
    # CHILE
    # ========================================================
    #
    # ESTA ES LA REGLA DEFINITIVA:
    #
    # Todo lo que venga de CL.m3u va a CHILE TV.
    #
    # No importa qué group-title traiga la fuente.
    # No importa si existe CHILE.
    # No importa si existe CHILE TV Y RADIO.
    #
    # ========================================================

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

        return categoria_configurada

    # ========================================================
    # NO ES PAÍS
    # ========================================================

    if (
        categoria_fuente
        and normalizar_texto(categoria_fuente)
        != "otros"
    ):
        return categoria_fuente

    return categoria_configurada