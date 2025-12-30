# 🚀 Guía de Despliegue - Azure Function

Guía completa para desplegar la Azure Function de Análisis Técnico en diferentes entornos.

---

## 📋 Tabla de Contenidos

- [Requisitos Previos](#requisitos-previos)
- [Método 1: Azure CLI](#método-1-azure-cli)
- [Método 2: VS Code](#método-2-vs-code)
- [Método 3: GitHub Actions CI/CD](#método-3-github-actions-cicd)
- [Configuración Post-Despliegue](#configuración-post-despliegue)
- [Verificación](#verificación)
- [Troubleshooting](#troubleshooting)

---

## ✅ Requisitos Previos

### Software Necesario

- [x] **Azure CLI** instalado y configurado
- [x] **Azure Functions Core Tools** v4.x
- [x] **Python 3.10+**
- [x] **Git** (para deployment desde repositorio)

### Acceso y Permisos

- [x] Subscription activa de Azure
- [x] Permisos de **Contributor** en el Resource Group
- [x] Acceso a:
  - Azure SQL Database (bluecapital_knowledge_base)
  - PostgreSQL Database (agente_marketing)

### Recursos Azure Existentes

- [x] **Function App** ya creada: `thebcap-analisis-tecnico`
- [x] **Storage Account** configurada
- [x] **Application Insights** (opcional pero recomendado)

---

## 🔧 Método 1: Azure CLI

### Paso 1: Autenticación

```bash
# Login a Azure
az login

# Verificar subscription activa
az account show

# Cambiar subscription si es necesario
az account set --subscription "nombre-o-id-subscription"
```

### Paso 2: Preparación Local

```bash
# Navegar a la carpeta del proyecto
cd BlueCapital_Azure_Function_Produccion

# Verificar que existen los archivos necesarios
ls -la
# Debe mostrar: function_app.py, requirements.txt, host.json
```

### Paso 3: Despliegue

```bash
# Opción A: Deploy directo
func azure functionapp publish thebcap-analisis-tecnico

# Opción B: Deploy con build remoto (recomendado para Windows)
func azure functionapp publish thebcap-analisis-tecnico --build remote

# Opción C: Deploy sin sobreescribir settings
func azure functionapp publish thebcap-analisis-tecnico --no-build
```

**Salida esperada:**
```
Getting site publishing info...
Creating archive for current directory...
Uploading 2.5 MB...
Upload completed successfully.
Deployment completed successfully.
Remote build in progress, please wait...
Remote build succeeded!
Syncing triggers...
Functions in thebcap-analisis-tecnico:
    AnalisisTecnico - [httpTrigger]
        Invoke url: https://thebcap-analisis-tecnico.azurewebsites.net/api/AnalisisTecnico
```

### Paso 4: Configurar Variables de Entorno

```bash
# Configurar Azure SQL
az functionapp config appsettings set \
  --name thebcap-analisis-tecnico \
  --resource-group rg-bluecapital \
  --settings \
    AZURE_SQL_SERVER="bluecapital-kb-prod-sql.database.windows.net" \
    AZURE_SQL_DATABASE="bluecapital_knowledge_base" \
    AZURE_SQL_USER="kb_access_agents" \
    AZURE_SQL_PASSWORD="tu_password_aqui"

# Verificar settings
az functionapp config appsettings list \
  --name thebcap-analisis-tecnico \
  --resource-group rg-bluecapital
```

---

## 💻 Método 2: VS Code

### Paso 1: Instalar Extensión

1. Abrir VS Code
2. Ir a Extensions (Ctrl+Shift+X)
3. Buscar "Azure Functions"
4. Instalar extensión oficial de Microsoft

### Paso 2: Sign In

1. Presionar `F1` o `Ctrl+Shift+P`
2. Escribir "Azure: Sign In"
3. Completar autenticación en navegador

### Paso 3: Deploy

1. Click en ícono de Azure en barra lateral
2. Expandir "Functions"
3. Click derecho en `thebcap-analisis-tecnico`
4. Seleccionar "Deploy to Function App..."
5. Confirmar deployment

### Paso 4: Configurar Settings

1. Click derecho en Function App
2. Seleccionar "Upload Local Settings..."
3. Seleccionar `local.settings.json`
4. Confirmar upload

---

## ⚙️ Método 3: GitHub Actions CI/CD

### Paso 1: Crear Workflow File

Crear archivo `.github/workflows/azure-deploy.yml`:

```yaml
name: Deploy to Azure Function

on:
  push:
    branches: [ main ]
  workflow_dispatch:

env:
  AZURE_FUNCTIONAPP_NAME: thebcap-analisis-tecnico
  AZURE_FUNCTIONAPP_PACKAGE_PATH: '.'
  PYTHON_VERSION: '3.10'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
    - name: 'Checkout GitHub Action'
      uses: actions/checkout@v3

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt --target=".python_packages/lib/site-packages"

    - name: 'Deploy to Azure Functions'
      uses: Azure/functions-action@v1
      with:
        app-name: ${{ env.AZURE_FUNCTIONAPP_NAME }}
        package: ${{ env.AZURE_FUNCTIONAPP_PACKAGE_PATH }}
        publish-profile: ${{ secrets.AZURE_FUNCTIONAPP_PUBLISH_PROFILE }}
```

### Paso 2: Configurar Secret

1. Ir a Azure Portal
2. Navegar a Function App `thebcap-analisis-tecnico`
3. Ir a "Deployment Center" → "Manage publish profile"
4. Click "Download publish profile"
5. Copiar contenido del archivo XML
6. Ir a GitHub Repository → Settings → Secrets
7. Crear nuevo secret `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`
8. Pegar contenido del XML

### Paso 3: Trigger Deploy

```bash
# Push a branch main
git add .
git commit -m "deploy: update function code"
git push origin main

# O ejecutar manualmente desde GitHub Actions tab
```

---

## 🔐 Configuración Post-Despliegue

### 1. Configurar CORS (si aplica)

```bash
az functionapp cors add \
  --name thebcap-analisis-tecnico \
  --resource-group rg-bluecapital \
  --allowed-origins "https://n8n.yourdomain.com"
```

### 2. Habilitar Application Insights

```bash
az functionapp config appsettings set \
  --name thebcap-analisis-tecnico \
  --resource-group rg-bluecapital \
  --settings \
    APPINSIGHTS_INSTRUMENTATIONKEY="tu-instrumentation-key"
```

### 3. Configurar Managed Identity (Recomendado)

```bash
# Habilitar System-Assigned Managed Identity
az functionapp identity assign \
  --name thebcap-analisis-tecnico \
  --resource-group rg-bluecapital

# Asignar permisos a Azure SQL
# (Requiere configuración adicional en SQL Database)
```

### 4. Configurar Always On (Premium Plan)

```bash
az functionapp config set \
  --name thebcap-analisis-tecnico \
  --resource-group rg-bluecapital \
  --always-on true
```

---

## ✅ Verificación

### 1. Health Check

```bash
# Opción A: Curl
curl https://thebcap-analisis-tecnico.azurewebsites.net/api/health

# Opción B: Browser
# Navegar a: https://thebcap-analisis-tecnico.azurewebsites.net/api/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "version": "3.0",
  "timestamp": "2024-11-26T10:30:00Z"
}
```

### 2. Ver Logs en Tiempo Real

```bash
# Azure CLI
func azure functionapp logstream thebcap-analisis-tecnico

# O desde Azure Portal
# Function App → Monitor → Log stream
```

### 3. Test End-to-End

```bash
# Ejecutar test con datos de ejemplo
curl -X POST https://thebcap-analisis-tecnico.azurewebsites.net/api/AnalisisTecnico \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

### 4. Verificar Métricas

Azure Portal → Function App → Monitor → Metrics

Métricas clave:
- **Function Execution Count** (debe incrementar)
- **Function Execution Units** (debe ser <1000ms promedio)
- **Http Server Errors** (debe ser 0)

---

## 🐛 Troubleshooting

### Error: "Deployment failed"

**Síntomas:**
```
Error: Failed to deploy web package to App Service.
```

**Solución:**
```bash
# 1. Verificar status de Function App
az functionapp show --name thebcap-analisis-tecnico --resource-group rg-bluecapital --query "state"

# 2. Restart si está stopped
az functionapp restart --name thebcap-analisis-tecnico --resource-group rg-bluecapital

# 3. Retry deployment
func azure functionapp publish thebcap-analisis-tecnico --build remote
```

### Error: "Python version mismatch"

**Síntomas:**
```
Error: The Python version '3.11' is not supported.
```

**Solución:**
```bash
# Verificar versión configurada en Azure
az functionapp config show --name thebcap-analisis-tecnico --resource-group rg-bluecapital --query "pythonVersion"

# Cambiar a Python 3.10
az functionapp config set --name thebcap-analisis-tecnico --resource-group rg-bluecapital --linux-fx-version "Python|3.10"
```

### Error: "Cannot connect to Azure SQL"

**Síntomas:**
```
Error: Login failed for user 'kb_access_agents'
```

**Solución:**
```bash
# 1. Verificar firewall rules de Azure SQL
az sql server firewall-rule list --server bluecapital-kb-prod-sql --resource-group rg-bluecapital

# 2. Agregar regla para Azure Services
az sql server firewall-rule create \
  --server bluecapital-kb-prod-sql \
  --resource-group rg-bluecapital \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# 3. Verificar credentials en App Settings
az functionapp config appsettings list --name thebcap-analisis-tecnico --resource-group rg-bluecapital --query "[?name=='AZURE_SQL_PASSWORD']"
```

### Performance: Cold Start >10s

**Síntomas:**
- Primera ejecución tarda >10 segundos
- Errores de timeout

**Solución:**
```bash
# Opción 1: Habilitar Always On (Premium Plan solamente)
az functionapp config set --name thebcap-analisis-tecnico --resource-group rg-bluecapital --always-on true

# Opción 2: Configurar Application Insights para pre-warming
# (Ver documentación de Azure)

# Opción 3: Implementar Health Check ping cada 5 minutos
# (Desde n8n o Azure Logic App)
```

---

## 📊 Monitoring y Alertas

### Configurar Alertas

```bash
# Alerta por errores HTTP 5xx
az monitor metrics alert create \
  --name "AnalisisTecnico-HTTP5xx" \
  --resource-group rg-bluecapital \
  --scopes "/subscriptions/{sub-id}/resourceGroups/rg-bluecapital/providers/Microsoft.Web/sites/thebcap-analisis-tecnico" \
  --condition "count Http5xx > 5" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action email your-email@company.com
```

### Dashboards

Azure Portal → Function App → Monitoring → Dashboard

Widgets recomendados:
- Function Execution Count (línea de tiempo)
- Average Execution Time (gráfico)
- Error Rate (alerta)
- Resource Utilization (CPU/Memory)

---

## 🔄 Rollback

Si el deployment causa problemas:

```bash
# Ver deployments históricos
az functionapp deployment list --name thebcap-analisis-tecnico --resource-group rg-bluecapital

# Rollback al deployment anterior
az functionapp deployment source config-zip \
  --name thebcap-analisis-tecnico \
  --resource-group rg-bluecapital \
  --src deployment-{previous-id}.zip
```

---

## 📝 Checklist de Despliegue

**Pre-Deployment:**
- [ ] Tests locales pasando (`func start` + manual testing)
- [ ] `requirements.txt` actualizado
- [ ] Variables de entorno documentadas
- [ ] Backup de código actual en producción

**During Deployment:**
- [ ] Deployment exitoso (sin errores)
- [ ] Logs muestran startup correcto
- [ ] Health check responde 200

**Post-Deployment:**
- [ ] Test end-to-end con datos reales
- [ ] Verificar métricas en Application Insights
- [ ] Notificar a stakeholders
- [ ] Actualizar documentación de versión

---

**Última actualización:** Noviembre 2024
**Mantenido por:** Equipo iPaaS - FlexFintech
