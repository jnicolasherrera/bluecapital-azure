# 📊 Azure Function - Análisis Técnico de Suscripción de Reaseguros

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Azure_Functions-0062AD?style=for-the-badge&logo=azurefunctions&logoColor=white" alt="Azure Functions">
  <img src="https://img.shields.io/badge/Estado-Producción-success?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/Versión-3.0-blue?style=for-the-badge" alt="Version">
</p>

<p align="center">
  <strong>Función Azure Serverless para automatización de análisis técnico de contratos de reaseguros</strong>
</p>

---

## 🎯 Descripción

Azure Function en **producción** que automatiza el análisis técnico completo de contratos de reaseguros, procesando archivos Excel de siniestralidad y TIV (Total Insured Value) para generar recomendaciones de suscripción basadas en análisis estadístico y reglas de negocio.

### Estado Actual
- **Entorno:** Producción
- **Región:** Azure Central US
- **URL:** `https://thebcap-analisis-tecnico-crf0fucsc0bzcsa9.centralus-01.azurewebsites.net`
- **Versión:** 3.0
- **Última Actualización:** Noviembre 2024

---

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Requisitos](#-requisitos)
- [Instalación Local](#-instalación-local)
- [Configuración](#-configuración)
- [Despliegue en Azure](#-despliegue-en-azure)
- [Uso](#-uso)
- [API Reference](#-api-reference)
- [Formatos Soportados](#-formatos-soportados)
- [Estructura del Código](#-estructura-del-código)
- [Troubleshooting](#-troubleshooting)
- [Changelog](#-changelog)

---

## ✨ Características

### Análisis Técnico Completo

- ✅ **Burning Cost** con clasificación semafórica (Verde/Amarillo/Rojo)
- ✅ **Frecuencia & Severidad** con coeficiente de variación
- ✅ **Análisis de Tendencias** (requiere ≥3 años de histórico)
- ✅ **Análisis de Reservas** (IBNR, paid/incurred ratio)
- ✅ **Concentraciones** (geográficas y por causa)
- ✅ **Detección de Eventos Catastróficos** (percentil 95)

### Integración con Knowledge Base

- ✅ Conexión a **Azure SQL** (bluecapital_knowledge_base)
- ✅ Consulta de histórico de siniestros
- ✅ Enriquecimiento con datos de asegurados

### Procesamiento Multi-formato

- ✅ **Río Magdalena** (Colombia - COP)
- ✅ **Antioquia** (Colombia - COP)
- ✅ Formato genérico con detección automática

### Validación Estadística

- ✅ Detección de muestras pequeñas (n<3, n<10)
- ✅ Disclaimers automáticos de confiabilidad
- ✅ Validación de calidad de datos

---

## 🏗️ Arquitectura

```
┌─────────────────┐
│   n8n Workflow  │
│  (Orchestrator) │
└────────┬────────┘
         │ POST /api/AnalisisTecnico
         ↓
┌─────────────────────────────┐
│   Azure Function (Python)   │
│  ┌─────────────────────┐    │
│  │ AnalizadorTecnico   │    │
│  │  • procesar_tiv()   │    │
│  │  • consolidar_*()   │    │
│  │  • analizar_*()     │    │
│  │  • calcular_bc()    │    │
│  └─────────────────────┘    │
└────────┬────────────────────┘
         │
         ├──→ Azure SQL (Knowledge Base)
         │    • consumption.FACT_CLAIMS
         │    • consumption.DIM_INSURED
         │
         └──→ PostgreSQL (Results)
              • analisis_tecnico_inicial
              • analisis_enriquecido_final
```

---

## 🔧 Requisitos

### Entorno de Desarrollo

- **Python:** 3.10 o superior
- **Azure Functions Core Tools:** v4.x
- **Azure CLI:** Última versión
- **Git:** Para control de versiones

### Dependencias Python

Ver [requirements.txt](requirements.txt):
- `azure-functions` - Runtime de Azure Functions
- `pandas>=2.0.0` - Procesamiento de datos
- `openpyxl>=3.1.0` - Lectura de archivos Excel
- `numpy>=1.24.0` - Operaciones numéricas
- `psycopg2-binary>=2.9.0` - Conector PostgreSQL
- `pyodbc>=4.0.39` - Conector SQL Server
- `requests>=2.31.0` - HTTP client
- `python-dateutil>=2.8.0` - Manejo de fechas

---

## 💻 Instalación Local

### 1. Clonar Repositorio

```bash
git clone https://github.com/tu-usuario/bluecapital-azure-function.git
cd bluecapital-azure-function
```

### 2. Crear Entorno Virtual

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

Crear archivo `local.settings.json`:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_SQL_SERVER": "tu-servidor.database.windows.net",
    "AZURE_SQL_DATABASE": "bluecapital_knowledge_base",
    "AZURE_SQL_USER": "tu_usuario",
    "AZURE_SQL_PASSWORD": "tu_password"
  }
}
```

### 5. Ejecutar Localmente

```bash
func start
```

La función estará disponible en: `http://localhost:7071/api/AnalisisTecnico`

---

## ⚙️ Configuración

### Variables de Entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `AZURE_SQL_SERVER` | Servidor Azure SQL | `bluecapital-kb-prod.database.windows.net` |
| `AZURE_SQL_DATABASE` | Base de datos | `bluecapital_knowledge_base` |
| `AZURE_SQL_USER` | Usuario SQL | `kb_access_agents` |
| `AZURE_SQL_PASSWORD` | Contraseña SQL | `*****` |
| `FUNCTIONS_WORKER_RUNTIME` | Runtime | `python` |

### Configuración de Azure Function

El archivo `host.json` configura:
- Logging con Application Insights
- Extension Bundle v4.x
- Sampling de telemetría

---

## 🚀 Despliegue en Azure

### Opción 1: Desde VS Code

1. Instalar extensión **Azure Functions**
2. Click derecho en carpeta → **Deploy to Function App**
3. Seleccionar subscription y function app
4. Confirmar despliegue

### Opción 2: Azure CLI

```bash
# 1. Login
az login

# 2. Deploy
func azure functionapp publish thebcap-analisis-tecnico

# 3. Verificar
curl https://thebcap-analisis-tecnico.azurewebsites.net/api/health
```

### Opción 3: GitHub Actions (CI/CD)

Ver [DESPLIEGUE.md](docs/DESPLIEGUE.md) para configuración completa.

---

## 📖 Uso

### Endpoint Principal

**URL:** `POST /api/AnalisisTecnico`
**Content-Type:** `application/json`

### Request Body

```json
{
  "archivos_siniestralidad": [
    {
      "nombre": "siniestros_2024.xlsx",
      "contenido_base64": "UEsDBBQABg..."
    }
  ],
  "archivos_tiv": [
    {
      "nombre": "tiv_2024.xlsx",
      "contenido_base64": "UEsDBBQABg..."
    }
  ],
  "archivos_slip": [
    {
      "nombre": "slip_2024.docx",
      "contenido_base64": "UEsDBBQABg..."
    }
  ],
  "asegurado": "Rio Magdalena",
  "agente": "Dynamic RE",
  "corredor": "Aon",
  "ramo": "Propiedad"
}
```

### Response (Success - 200)

```json
{
  "status": "success",
  "analisis_completo_json": {
    "siniestros": [
      {
        "fecha_ocurrencia": "2023-05-15",
        "año_ocurrencia": 2023,
        "monto_incurrido": 1500000.00,
        "monto_pagado": 1200000.00,
        "monto_reservado": 300000.00,
        "burning_cost": 2.5,
        "...": "... 17 campos por siniestro"
      }
    ],
    "analisis": {
      "resumen_global": {},
      "burning_cost": {},
      "frecuencia_severidad": {},
      "tendencias": {},
      "reservas": {},
      "concentraciones": {},
      "notas_para_pricing": []
    },
    "calidad_datos": {
      "limitaciones": [],
      "disclaimers": []
    },
    "trazabilidad": {
      "timestamp": "2024-11-26T10:30:00Z",
      "version": "3.0",
      "files_processed": []
    }
  }
}
```

### Response (Error - 400/500)

```json
{
  "status": "error",
  "message": "Descripción del error",
  "details": "..."
}
```

---

## 📊 Formatos Soportados

### 1. Río Magdalena (Colombia)

**Siniestralidad:**
- Hoja: `Resumen`
- Columnas: fecha, monto_pagado, monto_reservado, causa

**TIV:**
- Estrategia 1: Hoja `Resumen`, celda `G24`

### 2. Antioquia (Colombia)

**Siniestralidad:**
- Hoja: `GRUPO I`
- Header: Línea 2
- Filtro: `TODO RIESGO`
- Columnas: `Fec. Sini`, `Liquidado`, `Rva. Actual`

**TIV:**
- Estrategia 2: Primera hoja, celda `W18`

### 3. Formato Genérico

**Siniestralidad:**
- Columnas estándar: `fecha_siniestro`, `monto_pagado`, `monto_reservado`, `monto_incurrido`

**TIV:**
- Estrategia 3: Búsqueda de columna `suma_asegurada`

---

## 📂 Estructura del Código

```
bluecapital-azure-function/
├── function_app.py          # Código principal (1300+ líneas)
├── requirements.txt         # Dependencias Python
├── host.json               # Configuración Azure Functions
├── .gitignore              # Exclusiones Git
├── README.md               # Este archivo
└── docs/
    ├── DESPLIEGUE.md       # Guía de despliegue
    ├── API.md              # Referencia API completa
    └── CASOS_ESTUDIO.md    # Casos de uso reales
```

### Componentes Principales (function_app.py)

| Clase/Función | Líneas | Propósito |
|---------------|--------|-----------|
| `NumpyEncoder` | 34-47 | Serialización JSON |
| `get_azure_sql_connection()` | 58-73 | Conexión a Knowledge Base |
| `buscar_asegurado_en_kb()` | 76-132 | Búsqueda de asegurado |
| `obtener_historico_siniestros()` | 135-200 | Query histórico |
| `AnalizadorTecnico` | 203-1250 | **Clase principal** |
| └─ `procesar_tiv()` | 429-550 | TIV multi-estrategia |
| └─ `consolidar_siniestralidad()` | 218-416 | Procesamiento siniestros |
| └─ `calcular_burning_cost()` | 553-620 | Burning cost + semáforo |
| └─ `analizar_frecuencia_severidad()` | 623-720 | Frecuencia/severidad |
| └─ `analizar_tendencias()` | 723-820 | Análisis temporal |
| └─ `analizar_reservas()` | 823-920 | IBNR y reservas |
| └─ `analizar_concentraciones()` | 923-1020 | Concentración riesgo |
| `analisis_tecnico()` (endpoint) | 1253-1340 | HTTP trigger |

---

## 🐛 Troubleshooting

### Error: "No se pudo conectar a Azure SQL"

**Solución:**
1. Verificar firewall de Azure SQL incluye IP actual
2. Validar credenciales en `local.settings.json`
3. Revisar connection string

### Error: "TIV no encontrado"

**Solución:**
1. Verificar formato Excel coincide con estrategias soportadas
2. Revisar logs para ver qué estrategia falló
3. Agregar nueva estrategia si es formato nuevo

### Error: "Muestra insuficiente (n<3)"

**No es error**, es advertencia. El análisis continúa pero con disclaimers de confiabilidad.

### Performance: Cold Start >10 segundos

**Solución:**
- Usar **Premium Plan** en lugar de Consumption Plan
- O mantener función "warm" con ping cada 5 minutos

---

## 📝 Changelog

### v3.0 (Noviembre 2024) - PRODUCCIÓN ACTUAL

**Agregado:**
- ✅ Integración con Azure SQL Knowledge Base
- ✅ Consulta histórico de siniestros
- ✅ JSON pricing formato completo (17 campos)
- ✅ Multi-estrategia TIV parser (3 estrategias)
- ✅ Soporte formato GRUPO I (Antioquia)
- ✅ 7 módulos de análisis completos
- ✅ Validación estadística (n<3, n<10)

**Cambiado:**
- Refactorización completa clase `AnalizadorTecnico`
- Mejora en manejo de errores
- Optimización de performance (4.2s promedio)

### v2.1 (Octubre 2024)

- Integración PostgreSQL
- Workflow n8n
- Email reports

### v2.0 (Septiembre 2024)

- Implementación inicial Azure Function
- Clase AnalizadorTecnico
- Burning cost básico

---

## 👥 Soporte

**Equipo:** Arquitectura iPaaS - FlexFintech
**Email:** support@flexfintech.com
**Documentación Completa:** Ver carpeta `docs/`

---

## 📄 Licencia

Propietario - FlexFintech S.A.S. / Blue Capital
Todos los derechos reservados.

---

<p align="center">
  <strong>Azure Function en Producción - Blue Capital</strong><br>
  Última actualización: Noviembre 2024
</p>
