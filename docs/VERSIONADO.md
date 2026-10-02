# 🏷️ Sistema de versionado

## Ciclo oficial

```
v1.0.0          🟢 ESTABLE
     ↓
v1.1.0-beta.1   🟡 BETA
     ↓
                🧪 FASE DE PRUEBAS — INESTABLE
     ↓
v1.1.0-rc.1     🟠 CANDIDATA A LANZAMIENTO
     ↓
v1.1.0          🟢 ESTABLE
```

### Estados

- 🟢 **ESTABLE**: versión validada para uso normal.
- 🟡 **BETA**: versión nueva en pruebas; puede contener errores o cambios pendientes.
- 🧪 **FASE DE PRUEBAS — INESTABLE**: estado operativo durante la validación de una beta. No es una versión adicional.
- 🟠 **CANDIDATA A LANZAMIENTO**: versión que superó la fase beta y queda pendiente de la validación final.
- 🔴 **NO APROBADA**: versión que no cumple los controles requeridos.

Los identificadores técnicos siguen SemVer: `MAJOR.MINOR.PATCH`, con etiquetas `-beta.N` y `-rc.N` para versiones previas al lanzamiento estable.

## Reglas

1. No declarar una versión 🟢 ESTABLE sin superar los controles de calidad.
2. Cada cambio relevante debe quedar registrado en `CHANGELOG.md`.
3. `VERSION` contiene únicamente la versión activa, sin prefijos ni texto adicional.
4. README y documentación deben coincidir con `VERSION`.
5. Las familias Principal, GOD, Pluto y Generador deben conservar su aislamiento.
6. Antes de promover BETA → CANDIDATA A LANZAMIENTO → ESTABLE se debe ejecutar una auditoría posterior a las pruebas.
7. Si una validación falla, se corrige y se vuelve a auditar antes de promover la versión.
8. Las versiones estables deben disponer de un punto de rollback identificable.

## Versión actual

**v1.0.0 — 🟢 ESTABLE**

Esta es la línea base estable. Las mejoras futuras se prueban primero como beta antes de promocionarse.
