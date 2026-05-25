# Documentación Técnica: Pipeline de Asistencia y Dashboard Operativo

Este proyecto resuelve la transformación de la matriz de asistencia a formato largo (1FN), la auditoría de calidad de datos y la visualización de KPIs para la gestión operativa.

## 1. Supuestos de Negocio Adoptados

* **Periodo de Análisis:** Se acotó estrictamente al intervalo de 30 días detectado entre el 19/04/2026 y el 18/05/2026 según la estructura de la base original.
* **Ventana Laboral Activa:** Un registro de asistencia solo computa para las métricas operativas si la fecha cae dentro del periodo de vigencia de su contrato (`fecha_ingreso` <= `fecha_asistencia` <= `fecha_cese`).
* **Aislamiento Preventivo:** Los códigos 16, 20 o celdas vacías se clasificaron bajo la etiqueta de "Atípico por Verificar" para no distorsionar ni sesgar el cálculo real de las tasas de faltas y asistencias de la operación.

## 2. Pasos de Limpieza y Transformación (ETL)

1. **Ingesta y Parsing:** Lectura automatizada del archivo origen convirtiendo cabeceras seriales numéricas de Excel a tipos de datos temporales nativos de Python.
2. **Sanitización:** Homologación del DNI a formato string con relleno de ceros a la izquierda (`zfill`) para mitigar la pérdida de precisión numérica de la librería de datos.
3. **Reestructuración (Unpivot):** Pivotaje de la matriz de columnas de fechas diarias a un formato largo (1FN) indexado por la tupla colaborador-fecha para permitir consultas rápidas.
4. **Validación de Reglas:** Mapeo de estados contra el diccionario maestro y evaluación lógica de la vigencia de contratación de cada trabajador.

## 3. Justificación del Modelo de Datos

* **Fase de Consumo (1FN):** El pipeline desestructura la matriz y exporta un archivo plano largo (`asistencia_larga_limpia.csv`). Esto permite que Streamlit cargue y compute agrupaciones vectorizadas directo en la memoria RAM del servidor de forma instantánea, eliminando la latencia de consultas concurrentes a bases de datos en pruebas rápidas.
* **Fase de Producción Propuesta (Esquema en Estrella 2FN):** Para un Data Warehouse centralizado, la estructura óptima separa la tabla de hechos relacional (`fact_asistencia`) enlazada a las dimensiones normalizadas de `dim_trabajador`, `dim_cliente`, `dim_unidad`, `dim_calendario` y `dim_estado`. Esto elimina la redundancia masiva de nombres y direcciones en cada registro diario de la base de datos.
* **Historización de Atributos (SCD Tipo 2):** Ante potenciales cambios en el tiempo de variables críticas (como traslados de unidad de negocio, cambios de supervisor asignado u horarios), se propone la creación de una dimensión histórica (`dim_asignacion_hist`) controlada por rangos de vigencia mediante las columnas `valid_from` y `valid_to`. Esto garantiza la inmutabilidad y la trazabilidad de los reportes del pasado.

## 4. Limitaciones de la Solución y Calidad de Datos

* **Falta de Catálogo de Estados:** Al carecer de documentación para los códigos "16" y "20", estos registros quedan flotando como atípicos a la espera de una aclaración operativa del área correspondiente.
* **Integridad de Horarios:** La existencia de nulos en los horarios maestros de origen restringe el poder cruzar o conciliar si el turno trabajado corresponde estrictamente al planificado en los contratos.
* **Módulo de Calidad de Datos:** El sistema reporta proactivamente las siguientes inconsistencias detectadas: nulos en horario, registros fuera del periodo activo del contrato y celdas vacías de asistencia en ventanas activas.

## 5. Instrucciones de Despliegue en Hugging Face Spaces

El proyecto está configurado para ejecutarse directamente en la nube utilizando el SDK de Streamlit. El entorno requiere los siguientes archivos en la raíz del repositorio:

* `app.py`: Aplicación web interactiva que ejecuta la visualización y lógica de KPIs.
* `etl_pipeline.py`: Script modular de transformación de datos.
* `requirements.txt`: Definición de dependencias del sistema (`pandas`, `plotly`, `openpyxl`).
* `Base_a_corregir.xlsx - Hoja1.csv`: Dataset de entrada para el pipeline.