# Propuesta de mejoras IPTV — revisión aislada

**Estado:** propuesta en rama independiente; no integrada en `main`.
**Base:** `66d9be3137c51f9e60196397dda9153a98163631`.
**Alcance:** diagnóstico y validación solamente. Esta propuesta no autoriza cambios en playlists, streams, logos, categorías ni workflows de publicación.

## Hallazgos del análisis del código actual

1. `scripts/auditar_fuentes.py` ya compara altas, bajas, renombres, grupos y URLs mediante huellas SHA-256. También conserva el último estado conocido cuando una fuente falla, para evitar interpretar una caída temporal como eliminación masiva.
2. La auditoría de fuentes ya prueba varias cabeceras para dominios `m3u.cl`, pero si la respuesta sigue sin cabecera `#EXTM3U`, registra el fallo. No debe excluir ni reescribir automáticamente la fuente por ese único resultado.
3. `scripts/auditar_logos.py` ya separa fallos confirmados de respuestas inconclusas (por ejemplo HTTP 403 y errores de red) y no modifica logos. Falta una comparación histórica explícita de cada atributo `tvg-logo`/ `logo` entre la playlist anterior y la nueva.
4. `scripts/blindajes_principal.py` contiene protecciones para conservar logos y categorías protegidas. Cualquier mejora debe reforzar las pruebas de esas protecciones, no sustituirlas.
5. El reporte de salud necesita una clasificación más útil para distinguir errores permanentes (404/410, contenido inválido) de respuestas potencialmente transitorias o restringidas (403/401, timeout, SSL, 5xx).

## Cambios propuestos para evaluación

### A. Clasificador de salud sin falsos positivos
- Agrupar resultados por clase: `permanente_confirmado`, `restriccion_acceso`, `transitorio`, `respuesta_invalida` y `sin_verificar`.
- No retirar canales por 401/403, timeout, SSL o 5xx aislados.
- Reintentar únicamente los casos transitorios con espera limitada y registrar el resultado de cada intento.
- Exigir varias observaciones separadas para etiquetar una URL como persistentemente caída.
- No cambiar ni publicar URLs en esta fase.

### B. Diagnóstico aislado de M3U.CL LATAM
- Mantener la URL actual y no alterar la lista principal ni GOD.
- Guardar código HTTP, tipo de contenido, tamaño, cabecera detectada y variante de cabeceras utilizada; nunca guardar credenciales ni tokens.
- Tratar una respuesta sin `#EXTM3U` como fallo de formato de la fuente, no como prueba de que cada canal esté muerto.
- No omitir, reemplazar ni poner en cuarentena la fuente automáticamente.

### C. Auditoría diferencial de logos
- Comparar por identidad de canal los valores exactos de `tvg-logo` y `logo` antes/después.
- Informar por separado: logo conservado, logo agregado, logo retirado, URL de logo cambiada y canal sin identidad inequívoca.
- Marcar como anomalía cualquier cambio de logo existente no autorizado.
- No corregir ni sustituir logos automáticamente. Mantener intactos los logos funcionales y las reglas de CHILE TV/Anime.

### D. Reporte de auditoría consolidado
- Resumen por workflow, fuente y clase de error.
- Separar fuentes publicables de fuentes GOD de solo lectura.
- Mostrar altas, bajas, renombres, cambios de URL y cambios de logo en secciones independientes.
- Ocultar tokens y URLs firmadas completas; usar huellas para comparar.
- Añadir un resultado explícito `APTO PARA REVISIÓN` o `BLOQUEADO`, sin publicar por sí mismo.

## Pruebas de aceptación obligatorias

- 403/401, timeout, SSL y 5xx no se clasifican como caída permanente por una sola observación.
- 404/410 repetidos se muestran como fallo confirmado, sin borrar el canal.
- Respuesta HTML o sin `#EXTM3U` se clasifica como error de formato de fuente.
- Cambios de `tvg-logo` y `logo` se detectan independientemente.
- Una playlist idéntica produce diff vacío.
- La M3U principal y `IPTV-CHILE-MAESTRA_GOD.m3u` permanecen byte por byte intactas durante las pruebas.
- Los workflows de publicación no se ejecutan manualmente y no se modifica su configuración en esta fase.

## Exclusiones expresas

- No modificar `IPTV-CHILE-MAESTRA_CORREGIDO.m3u`.
- No modificar `IPTV-CHILE-MAESTRA_GOD.m3u).
- No modificar tokens, URLs de canales, logos, nombres, categorías ni orden.
- No cambiar la serialización ni los horarios de Actions.
- No fusionar ni aplicar esta propuesta a `main`.

**Siguiente paso:** implementar los diagnósticos como herramientas aisladas y pruebas unitarias en esta rama; revisar diff y resultados antes de solicitar cualquier integración.
