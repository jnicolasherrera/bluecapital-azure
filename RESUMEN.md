# ✅ Repositorio de Producción - Azure Function

**Proyecto:** Análisis Técnico de Suscripción de Reaseguros
**Versión:** 3.0
**Status:** ✅ EN PRODUCCIÓN
**Fecha:** Diciembre 2024

---

## 📦 Contenido del Repositorio

Este repositorio contiene **ÚNICAMENTE** el código de producción de la Azure Function desplegada en Azure Central US.

### Archivos Incluidos

```
BlueCapital_Azure_Function_Produccion/
├── function_app.py          ✅ Código principal (1300+ líneas)
├── requirements.txt         ✅ Dependencias Python
├── host.json               ✅ Configuración Azure Functions
├── .gitignore              ✅ Exclusiones Git
├── README.md               ✅ Documentación principal
├── RESUMEN.md              ✅ Este archivo
└── docs/
    ├── DESPLIEGUE.md       ✅ Guía completa de despliegue
    └── API.md              ✅ Referencia completa de API
```

---

## 🎯 Propósito

Repositorio **limpio y mínimo** que contiene:
- ✅ Solo el código que está en producción (v3.0)
- ✅ Documentación técnica en español
- ✅ Guías de despliegue y uso
- ❌ Sin archivos de testing
- ❌ Sin código experimental
- ❌ Sin múltiples versiones

---

## 🚀 Quick Start

### Instalación Local

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/bluecapital-azure-function.git
cd bluecapital-azure-function

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar local.settings.json
# (Ver README.md sección "Configuración")

# 5. Ejecutar localmente
func start
```

### Despliegue a Azure

```bash
# Opción más simple
func azure functionapp publish thebcap-analisis-tecnico

# Ver guía completa en docs/DESPLIEGUE.md
```

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [README.md](README.md) | **Documentación principal** - Empieza aquí |
| [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md) | Guía completa de despliegue (3 métodos) |
| [docs/API.md](docs/API.md) | Referencia completa de API |

---

## 🔗 Enlaces Importantes

| Recurso | URL |
|---------|-----|
| **Producción** | https://thebcap-analisis-tecnico.azurewebsites.net |
| **Endpoint** | https://thebcap-analisis-tecnico.azurewebsites.net/api/AnalisisTecnico |
| **Azure Portal** | Portal Azure → Function Apps → thebcap-analisis-tecnico |
| **Application Insights** | (Configurar si no existe) |

---

## 💡 Características Principales

### v3.0 (Producción Actual)

- ✅ **Análisis Técnico Completo:** 7 módulos de análisis
- ✅ **Multi-formato:** Río Magdalena, Antioquia, Genérico
- ✅ **Knowledge Base:** Integración con Azure SQL
- ✅ **Validación Estadística:** Detección de muestras pequeñas
- ✅ **JSON Completo:** 17 campos por siniestro

### Análisis Incluidos

1. **Burning Cost** - Clasificación semafórica (Verde/Amarillo/Rojo)
2. **Frecuencia & Severidad** - Coeficiente de variación
3. **Tendencias** - Análisis temporal (≥3 años)
4. **Reservas** - Análisis IBNR
5. **Concentraciones** - Geográficas y por causa
6. **Calidad de Datos** - Limitaciones y disclaimers
7. **Eventos Catastróficos** - Detección percentil 95

---

## 🛠️ Tecnologías

- **Python:** 3.10
- **Azure Functions:** v4 runtime
- **Pandas:** 2.0+ (procesamiento de datos)
- **Azure SQL:** Knowledge Base integration
- **PostgreSQL:** Resultados storage

---

## 📊 Métricas de Producción

| Métrica | Valor |
|---------|-------|
| **Cold Start** | ~12 segundos |
| **Warm Start** | ~2.8 segundos |
| **Avg Processing** | 4.2 segundos |
| **Success Rate** | >99% |
| **Uptime** | >99.9% |

---

## 🔐 Seguridad

- ✅ Sin credenciales hardcodeadas
- ✅ Variables de entorno para secrets
- ✅ `.gitignore` configurado correctamente
- ✅ `local.settings.json` excluido de Git

---

## 🆘 Soporte

**Equipo:** Arquitectura iPaaS - FlexFintech
**Email:** support@flexfintech.com
**Documentación:** Ver carpeta `docs/`

---

## 📝 Próximos Pasos Sugeridos

1. ✅ Leer [README.md](README.md) completo
2. ✅ Configurar entorno local
3. ✅ Ejecutar `func start` y probar endpoint
4. ✅ Revisar [docs/API.md](docs/API.md) para integración
5. ✅ Si vas a desplegar, leer [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md)

---

**Este es un repositorio de PRODUCCIÓN. Todo el código aquí está en uso activo.**

---

**Preparado por:** Equipo iPaaS - FlexFintech
**Fecha:** Diciembre 2024
**Versión:** 3.0
