# 🧪 Controles de calidad y promoción de versiones

Una ejecución verde de GitHub Actions no equivale por sí sola a una versión estable.

## Puertas de calidad

Antes de promover una versión se revisa:

- Integridad de archivos.
- Consistencia de referencias y enlaces.
- Ausencia de modificaciones cruzadas entre familias independientes.
- Validaciones específicas de Principal, GOD, Pluto y Generador.
- Funcionamiento de las automatizaciones afectadas.
- Resultados de los self-tests disponibles.
- Calidad de streams cuando el cambio afecte validación de streams.
- Reportes generados y coherentes.
- Documentación y número de versión consistentes.
- Posibilidad de rollback.

## Promoción

**BETA → CANDIDATA A LANZAMIENTO**

Requiere que las pruebas de la beta hayan terminado sin fallos bloqueantes y que los hallazgos conocidos estén documentados.

**CANDIDATA A LANZAMIENTO → ESTABLE**

Requiere una auditoría final, pruebas satisfactorias y ausencia de bloqueadores conocidos.

Si aparece un fallo:

```
FALLA
  ↓
CORREGIR
  ↓
VOLVER A PROBAR
  ↓
VOLVER A AUDITAR
  ↓
PROMOVER SOLO SI CUMPLE
```
