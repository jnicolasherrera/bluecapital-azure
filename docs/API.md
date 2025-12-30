# 📡 Referencia Completa de API

Documentación detallada del endpoint de la Azure Function de Análisis Técnico.

---

## 🎯 Endpoint Principal

### Análisis Técnico

**URL:** `POST /api/AnalisisTecnico`

**Descripción:** Procesa archivos Excel de siniestralidad y TIV para generar análisis técnico completo con recomendaciones de suscripción.

**Content-Type:** `application/json`

**Authentication:** Ninguna (ANONYMOUS)

---

## 📥 Request

### Headers

```http
POST /api/AnalisisTecnico HTTP/1.1
Host: thebcap-analisis-tecnico.azurewebsites.net
Content-Type: application/json
Content-Length: {tamaño}
```

### Body Structure

```json
{
  "archivos_siniestralidad": [
    {
      "nombre": "string",
      "contenido_base64": "string"
    }
  ],
  "archivos_tiv": [
    {
      "nombre": "string",
      "contenido_base64": "string"
    }
  ],
  "archivos_slip": [
    {
      "nombre": "string",
      "contenido_base64": "string"
    }
  ],
  "asegurado": "string",
  "agente": "string",
  "corredor": "string",
  "ramo": "string"
}
```

### Campos

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `archivos_siniestralidad` | array | ✅ Sí | Array de archivos Excel con histórico de siniestros |
| `archivos_tiv` | array | ✅ Sí | Array de archivos Excel con TIV (Total Insured Value) |
| `archivos_slip` | array | ❌ No | Array de archivos Word/PDF con slip de cotización |
| `asegurado` | string | ✅ Sí | Nombre del asegurado |
| `agente` | string | ❌ No | Nombre del agente/broker |
| `corredor` | string | ❌ No | Nombre del corredor |
| `ramo` | string | ✅ Sí | Ramo de seguro (ej: "Propiedad", "Auto", "Transporte") |

### Ejemplo Completo

```json
{
  "archivos_siniestralidad": [
    {
      "nombre": "siniestros_rio_magdalena_2020_2024.xlsx",
      "contenido_base64": "UEsDBBQABgAIAAAAIQD..."
    }
  ],
  "archivos_tiv": [
    {
      "nombre": "tiv_rio_magdalena_2024.xlsx",
      "contenido_base64": "UEsDBBQABgAIAAAAIQC..."
    }
  ],
  "archivos_slip": [
    {
      "nombre": "slip_cotizacion_2024.docx",
      "contenido_base64": "UEsDBBQABgAIAAAAIQB..."
    }
  ],
  "asegurado": "Rio Magdalena S.A.",
  "agente": "Dynamic RE",
  "corredor": "Aon Colombia",
  "ramo": "Propiedad"
}
```

---

## 📤 Response

### Success Response (200)

```json
{
  "status": "success",
  "analisis_completo_json": {
    "siniestros": [ /* array de siniestros */ ],
    "analisis": { /* objeto de análisis */ },
    "calidad_datos": { /* objeto de calidad */ },
    "trazabilidad": { /* objeto de metadata */ }
  },
  "mensaje": "Análisis técnico completado exitosamente",
  "timestamp": "2024-11-26T10:30:00Z"
}
```

### Error Response (400 - Bad Request)

```json
{
  "status": "error",
  "error_type": "ValidationError",
  "message": "archivos_siniestralidad es requerido",
  "details": {
    "campo": "archivos_siniestralidad",
    "valor_recibido": null
  },
  "timestamp": "2024-11-26T10:30:00Z"
}
```

### Error Response (500 - Internal Server Error)

```json
{
  "status": "error",
  "error_type": "ProcessingError",
  "message": "Error procesando archivo Excel",
  "details": {
    "archivo": "siniestros.xlsx",
    "error": "Formato de fecha inválido en columna fecha_siniestro"
  },
  "timestamp": "2024-11-26T10:30:00Z"
}
```

---

## 📊 Estructura Detallada del Response

### 1. siniestros (Array)

Array con información detallada de cada siniestro procesado. **17 campos por siniestro**.

```json
{
  "siniestros": [
    {
      "fecha_ocurrencia": "2023-05-15",
      "año_ocurrencia": 2023,
      "monto_incurrido": 1500000.00,
      "monto_pagado": 1200000.00,
      "monto_reservado": 300000.00,
      "ramo": "Propiedad",
      "region": "Bogotá",
      "cobertura": "Todo Riesgo",
      "descripcion": "Incendio en bodega principal",
      "numero_siniestro": "SIN-2023-001",
      "año_poliza": 2023,
      "estado": "Abierto",
      "pct_incurrido_sobre_tiv": 0.15,
      "pct_reservado_sobre_incurrido": 20.0,
      "dias_desde_ocurrencia": 456,
      "trimestre": "Q2",
      "es_catastrofico": 0
    }
  ]
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `fecha_ocurrencia` | string (ISO 8601) | Fecha del siniestro |
| `año_ocurrencia` | integer | Año del siniestro |
| `monto_incurrido` | float | Monto total incurrido (pagado + reservado) |
| `monto_pagado` | float | Monto ya pagado |
| `monto_reservado` | float | Monto reservado (IBNR) |
| `ramo` | string | Ramo del seguro |
| `region` | string | Región geográfica |
| `cobertura` | string | Tipo de cobertura |
| `descripcion` | string | Descripción del siniestro |
| `numero_siniestro` | string | Número identificador |
| `año_poliza` | integer | Año de la póliza |
| `estado` | string | Estado (Abierto/Cerrado) |
| `pct_incurrido_sobre_tiv` | float | % incurrido sobre TIV |
| `pct_reservado_sobre_incurrido` | float | % reservado sobre incurrido |
| `dias_desde_ocurrencia` | integer | Días desde ocurrencia |
| `trimestre` | string | Trimestre (Q1, Q2, Q3, Q4) |
| `es_catastrofico` | integer | 1 si supera percentil 95, 0 si no |

### 2. analisis (Object)

Objeto con 7 secciones de análisis técnico.

```json
{
  "analisis": {
    "resumen_global": {
      "total_siniestros": 8,
      "años_analisis": 5,
      "monto_total_incurrido": 12500000.00,
      "monto_total_pagado": 8000000.00,
      "monto_total_reservado": 4500000.00,
      "tiv_total": 4400000000.00,
      "frecuencia_anual": 1.6,
      "severidad_promedio": 1562500.00
    },
    "burning_cost": {
      "burning_cost_por_mil": 2.835,
      "semaforo": "ROJO",
      "interpretacion": "Alto riesgo - BC > 2.0‰",
      "recomendacion": "Revisar condiciones o rechazar"
    },
    "frecuencia_severidad": {
      "frecuencia_anual_promedio": 1.6,
      "severidad_promedio": 1562500.00,
      "severidad_mediana": 1250000.00,
      "desviacion_estandar": 450000.00,
      "coeficiente_variacion": null,
      "confiabilidad_estadistica": "BAJA - Muestra pequeña",
      "disclaimers": [
        "ADVERTENCIA: Menos de 10 siniestros - Baja confianza estadística"
      ]
    },
    "tendencias": {
      "tendencia_frecuencia": "Estable",
      "tasa_crecimiento_anual": 0.05,
      "años_con_siniestros": 5,
      "años_sin_siniestros": 0
    },
    "reservas": {
      "total_reservado": 4500000.00,
      "pct_reservado_sobre_incurrido": 36.0,
      "pct_sin_liquidar": 100.0,
      "alerta_ibnr": "CRÍTICO: 100% siniestros sin liquidar",
      "semaforo_reservas": "ROJO"
    },
    "concentraciones": {
      "top_regiones": [
        {"region": "Bogotá", "count": 5, "pct": 62.5}
      ],
      "top_causas": [
        {"causa": "Incendio", "count": 3, "pct": 37.5}
      ]
    },
    "notas_para_pricing": [
      "Burning cost elevado (2.835‰) - ROJO",
      "Muestra pequeña (n=8) - Baja confiabilidad estadística",
      "100% siniestros sin liquidar - Riesgo IBNR alto"
    ]
  }
}
```

### 3. calidad_datos (Object)

Información sobre limitaciones y advertencias.

```json
{
  "calidad_datos": {
    "limitaciones": [
      "Solo 8 siniestros disponibles",
      "Datos de 5 años de histórico"
    ],
    "disclaimers": [
      "Análisis con confianza estadística BAJA (n<10)",
      "Resultados deben complementarse con análisis cualitativo"
    ]
  }
}
```

### 4. trazabilidad (Object)

Metadata del procesamiento.

```json
{
  "trazabilidad": {
    "timestamp": "2024-11-26T10:30:00Z",
    "version": "3.0",
    "files_processed": [
      "siniestros_rio_magdalena.xlsx",
      "tiv_rio_magdalena.xlsx"
    ],
    "asegurado": "Rio Magdalena S.A.",
    "ramo": "Propiedad"
  }
}
```

---

## 🚦 Códigos de Estado HTTP

| Código | Descripción | Cuándo ocurre |
|--------|-------------|---------------|
| **200 OK** | Éxito | Análisis completado correctamente |
| **400 Bad Request** | Error de validación | Campos requeridos faltantes, formato incorrecto |
| **500 Internal Server Error** | Error del servidor | Error procesando Excel, error de BD, etc. |
| **503 Service Unavailable** | Servicio no disponible | Function App caída o en mantenimiento |

---

## 🔍 Ejemplos de Uso

### cURL

```bash
curl -X POST https://thebcap-analisis-tecnico.azurewebsites.net/api/AnalisisTecnico \
  -H "Content-Type: application/json" \
  -d '{
    "archivos_siniestralidad": [{
      "nombre": "siniestros.xlsx",
      "contenido_base64": "UEsDBBQABgAI..."
    }],
    "archivos_tiv": [{
      "nombre": "tiv.xlsx",
      "contenido_base64": "UEsDBBQABgAI..."
    }],
    "asegurado": "Rio Magdalena",
    "ramo": "Propiedad"
  }'
```

### Python (requests)

```python
import requests
import base64

# Leer archivos
with open("siniestros.xlsx", "rb") as f:
    siniestros_b64 = base64.b64encode(f.read()).decode()

with open("tiv.xlsx", "rb") as f:
    tiv_b64 = base64.b64encode(f.read()).decode()

# Request
response = requests.post(
    "https://thebcap-analisis-tecnico.azurewebsites.net/api/AnalisisTecnico",
    json={
        "archivos_siniestralidad": [{
            "nombre": "siniestros.xlsx",
            "contenido_base64": siniestros_b64
        }],
        "archivos_tiv": [{
            "nombre": "tiv.xlsx",
            "contenido_base64": tiv_b64
        }],
        "asegurado": "Rio Magdalena",
        "ramo": "Propiedad"
    }
)

# Resultado
print(response.json())
```

### JavaScript (Node.js)

```javascript
const fs = require('fs');
const axios = require('axios');

// Leer archivos
const siniestrosB64 = fs.readFileSync('siniestros.xlsx').toString('base64');
const tivB64 = fs.readFileSync('tiv.xlsx').toString('base64');

// Request
axios.post('https://thebcap-analisis-tecnico.azurewebsites.net/api/AnalisisTecnico', {
  archivos_siniestralidad: [{
    nombre: 'siniestros.xlsx',
    contenido_base64: siniestrosB64
  }],
  archivos_tiv: [{
    nombre: 'tiv.xlsx',
    contenido_base64: tivB64
  }],
  asegurado: 'Rio Magdalena',
  ramo: 'Propiedad'
})
.then(response => {
  console.log(response.data);
})
.catch(error => {
  console.error(error.response.data);
});
```

---

## 📌 Notas Importantes

### Límites y Restricciones

| Límite | Valor | Nota |
|--------|-------|------|
| **Tamaño máximo del request** | 100 MB | Límite de Azure Functions |
| **Tiempo máximo de ejecución** | 300 segundos (5 min) | Consumption Plan |
| **Archivos simultáneos** | Sin límite | Procesados secuencialmente |
| **Rate limit** | Sin límite | Considerar implementar si crece uso |

### Mejores Prácticas

1. **Comprimir archivos grandes** antes de convertir a Base64
2. **Enviar un archivo de siniestralidad consolidado** en lugar de múltiples
3. **Validar formato Excel localmente** antes de enviar
4. **Implementar retry logic** con exponential backoff
5. **Guardar response completo** para auditoría

---

**Última actualización:** Noviembre 2024
