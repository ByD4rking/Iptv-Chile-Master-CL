# 🛡️ Estabilidad y auditoría

El proyecto utiliza un ciclo de mejora continua:

```
AUDITAR
   ↓
DETECTAR POSIBLES ERRORES
   ↓
PROPONER MEJORAS
   ↓
APLICAR
   ↓
PROBAR
   ↓
AUDITAR NUEVAMENTE
   ↓
CORREGIR HALLAZGOS
   ↓
VOLVER A PROBAR
   ↓
VERIFICAR
```

## Principio

Una mejora no se considera terminada por haber sido escrita en el repositorio. Debe verificarse su comportamiento y comprobar que no introduce regresiones.

Las listas y componentes independientes deben permanecer aislados:

- 🇨🇱 Principal
- 🔥 GOD
- 🪐 Pluto TV
- 🧪 IPTV-CHILE-GENERADOR

## Promoción segura

Las versiones experimentales no deben sustituir automáticamente una versión estable hasta superar las puertas de calidad.

El rollback debe conservarse mediante una referencia estable identificable, como una rama o etiqueta de respaldo.
