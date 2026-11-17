# Cuarentena de canales

## Yu-Gi-Oh! (Latino) [Twitch]

- Estado: cuarentena temporal; excluido de la playlist principal.
- Motivo: el endpoint respondió HTTP 200 con `Content-Type: text/html`, no con un manifiesto de video reproducible.
- Revisión: comprobar periódicamente que la URL entregue HLS válido (`#EXTM3U` y segmentos accesibles) o un flujo directo de video compatible. No restaurar por un HTTP 200 aislado.
- Restauración: cuando pase la validación de manifiesto/segmentos y reproducción, reinsertar la entrada completa en Anime y retirar este registro.

La entrada original se conserva íntegra en `yu-gi-oh-latino-twitch.m3u`, incluidos metadatos y URL.
