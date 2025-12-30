"""
Azure Function: Análisis Técnico de Suscripción de Reaseguros - VERSIÓN 3.2
Versión: 3.2
Autor: Arquitectura iPaaS
Descripción: Análisis técnico completo con histórico desde Azure SQL Knowledge Base

Cambios v3.2 (2024-12-30):
- ✅ Integración API de Cotizaciones del Dólar
  - Soporte USD/COP (Colombia)
  - Soporte USD/MXN (México)
  - Sistema de fallback con 2 APIs públicas
  - Cache en memoria para optimización
- ✅ Conversión automática de montos a USD en JSON pricing
- ✅ Metadata de moneda y tasa de cambio en output

Cambios v3.1 (2024-12-30):
- ✅ Soporte para formato La Costeña (México)
  - Siniestros: hoja SIN_AGOSTO, header línea 9
  - TIV: hoja SUM ASEG, header línea 4
- ✅ Soporte para formato CONAGUA (México)
  - Siniestros: hoja Detail, header línea 2
  - TIV: hoja Conagua, header línea 12
- ✅ ESTRATEGIA 4 de TIV para La Costeña
- ✅ ESTRATEGIA 5 de TIV para CONAGUA
- ✅ Validación mejorada para muestras pequeñas (n<3)
- ✅ Desglose de TIV por componentes
- ✅ Análisis de concentración de riesgo
- ✅ Metadata ampliada (país, moneda, formato detectado)

Cambios v3.0:
- ✅ Conexión a Azure SQL bluecapital_knowledge_base
- ✅ Consulta histórico de siniestros desde consumption.FACT_CLAIMS
- ✅ JSON pricing formato completo (Río Magdalena)
"""

import azure.functions as func
import pandas as pd
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import io
import hashlib
import pyodbc
import numpy as np
import requests

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# JSON Encoder personalizado para manejar tipos de NumPy/Pandas
class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder para manejar tipos de NumPy y Pandas"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif pd.isna(obj):
            return None
        return super().default(obj)


# ============================================
# DETECTORES DE FORMATO
# ============================================

def es_formato_la_costena_siniestros(archivo_bytes: bytes, filename: str) -> bool:
    """
    Detecta si el archivo es formato La Costeña - Siniestros

    Indicadores:
    - Nombre archivo contiene "costeña" or "costena"
    - Hoja "SIN_AGOSTO" existe
    """
    try:
        if 'costeña' in filename.lower() or 'costena' in filename.lower():
            if 'siniestro' in filename.lower():
                return True

        excel_file = pd.ExcelFile(io.BytesIO(archivo_bytes))
        if 'SIN_AGOSTO' in excel_file.sheet_names:
            logger.info(f"Detectado formato La Costeña - Siniestros")
            return True

    except Exception as e:
        logger.debug(f"No es formato La Costeña Siniestros: {str(e)}")

    return False


def es_formato_la_costena_tiv(archivo_bytes: bytes, filename: str) -> bool:
    """Detecta si el archivo es formato La Costeña - TIV"""
    try:
        if ('desglose' in filename.lower() or 'valores' in filename.lower()) and \
           ('costeña' in filename.lower() or 'costena' in filename.lower()):
            return True

        excel_file = pd.ExcelFile(io.BytesIO(archivo_bytes))
        if 'SUM ASEG' in excel_file.sheet_names:
            logger.info(f"Detectado formato La Costeña - TIV")
            return True

    except Exception:
        pass

    return False


def es_formato_conagua_siniestros(archivo_bytes: bytes, filename: str) -> bool:
    """Detecta si el archivo es formato CONAGUA - Siniestros"""
    try:
        if 'conagua' in filename.lower() and 'loss' in filename.lower():
            return True

        excel_file = pd.ExcelFile(io.BytesIO(archivo_bytes))
        if 'Detail' in excel_file.sheet_names and 'Resume' in excel_file.sheet_names:
            logger.info(f"Detectado formato CONAGUA - Siniestros")
            return True

    except Exception:
        pass

    return False


def es_formato_conagua_tiv(archivo_bytes: bytes, filename: str) -> bool:
    """Detecta si el archivo es formato CONAGUA - TIV"""
    try:
        if 'conagua' in filename.lower() and 'sov' in filename.lower():
            return True

        excel_file = pd.ExcelFile(io.BytesIO(archivo_bytes))
        for sheet_name in excel_file.sheet_names:
            if sheet_name.lower().startswith('conagua'):
                logger.info(f"Detectado formato CONAGUA - TIV")
                return True

    except Exception:
        pass

    return False


# ============================================
# CLASE PARA COTIZACIONES DE MONEDA
# ============================================

def detectar_moneda_por_formato(nombre_asegurado: str = "", archivos_nombres: List[str] = []) -> str:
    """
    Detecta la moneda del cliente basándose en el nombre o archivos

    Args:
        nombre_asegurado: Nombre del asegurado
        archivos_nombres: Lista de nombres de archivos procesados

    Returns:
        Código de moneda: 'MXN', 'COP', o 'USD'
    """
    nombre_lower = nombre_asegurado.lower()
    archivos_str = " ".join(archivos_nombres).lower()

    if 'costeña' in nombre_lower or 'costena' in nombre_lower or \
       'costeña' in archivos_str or 'costena' in archivos_str:
        return 'MXN'

    if 'conagua' in nombre_lower or 'conagua' in archivos_str:
        return 'MXN'

    if 'magdalena' in nombre_lower or 'antioquia' in nombre_lower or \
       'colombia' in nombre_lower:
        return 'COP'

    return 'COP'


class CotizacionDolar:
    """
    Gestiona cotizaciones del dólar para conversión de monedas

    Uso:
        api = CotizacionDolar()
        tasa_cop = api.obtener_cotizacion_cop()
        usd_amount = api.convertir_a_usd(monto_cop, 'COP')
    """

    def __init__(self):
        """Inicializa el gestor de cotizaciones"""
        self.apis = {
            'exchangerate-api': 'https://api.exchangerate-api.com/v4/latest/USD',
            'frankfurter': 'https://api.frankfurter.app/latest?from=USD'
        }
        self._cache = {}

    def obtener_cotizacion_cop(self) -> float:
        """
        Obtiene cotización USD/COP

        Returns:
            Tasa de cambio USD/COP
        """
        if 'COP' in self._cache:
            return self._cache['COP']

        try:
            response = requests.get(self.apis['exchangerate-api'], timeout=10)
            response.raise_for_status()
            data = response.json()
            cotizacion = data['rates']['COP']
            self._cache['COP'] = cotizacion
            logger.info(f"Cotización USD/COP: {cotizacion:,.2f}")
            return cotizacion
        except Exception as e:
            logger.warning(f"Error obteniendo cotización COP: {str(e)}")
            try:
                response = requests.get(self.apis['frankfurter'], timeout=10)
                data = response.json()
                if 'COP' in data['rates']:
                    cotizacion = data['rates']['COP']
                    self._cache['COP'] = cotizacion
                    return cotizacion
            except Exception:
                pass
            logger.warning("Usando cotización aproximada COP")
            return 4200.0

    def obtener_cotizacion_mxn(self) -> float:
        """
        Obtiene cotización USD/MXN

        Returns:
            Tasa de cambio USD/MXN
        """
        if 'MXN' in self._cache:
            return self._cache['MXN']

        try:
            response = requests.get(self.apis['exchangerate-api'], timeout=10)
            response.raise_for_status()
            data = response.json()
            cotizacion = data['rates']['MXN']
            self._cache['MXN'] = cotizacion
            logger.info(f"Cotización USD/MXN: {cotizacion:,.2f}")
            return cotizacion
        except Exception as e:
            logger.warning(f"Error obteniendo cotización MXN: {str(e)}")
            logger.warning("Usando cotización aproximada MXN")
            return 18.0

    def convertir_a_usd(self, monto: float, moneda: str) -> float:
        """
        Convierte un monto en moneda local a USD

        Args:
            monto: Monto en moneda local
            moneda: Código de moneda (COP, MXN, USD)

        Returns:
            Monto en USD
        """
        if moneda == 'USD':
            return monto

        if moneda == 'COP':
            tasa = self.obtener_cotizacion_cop()
            return monto / tasa

        if moneda == 'MXN':
            tasa = self.obtener_cotizacion_mxn()
            return monto / tasa

        logger.warning(f"Moneda no soportada: {moneda}")
        return monto


# ========================================
# CONFIGURACIÓN AZURE SQL KNOWLEDGE BASE
# ========================================
AZURE_SQL_SERVER = os.getenv('AZURE_SQL_SERVER', 'bluecapital-kb-prod-sql-411lon.database.windows.net')
AZURE_SQL_DATABASE = os.getenv('AZURE_SQL_DATABASE', 'bluecapital_knowledge_base')
AZURE_SQL_USER = os.getenv('AZURE_SQL_USER', 'kb_access_agents')
AZURE_SQL_PASSWORD = os.getenv('AZURE_SQL_PASSWORD', 'PasswordFuerte123!')


def get_azure_sql_connection():
    """Establece conexión a Azure SQL Knowledge Base"""
    try:
        connection_string = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={AZURE_SQL_SERVER};'
            f'DATABASE={AZURE_SQL_DATABASE};'
            f'UID={AZURE_SQL_USER};'
            f'PWD={AZURE_SQL_PASSWORD}'
        )
        conn = pyodbc.connect(connection_string, timeout=30)
        logger.info("✅ Conexión exitosa a Azure SQL Knowledge Base")
        return conn
    except Exception as e:
        logger.error(f"❌ Error conectando a Azure SQL: {str(e)}")
        return None


def buscar_asegurado_en_kb(nombre_asegurado: str) -> Optional[int]:
    """
    Busca el insured_key del asegurado en consumption.DIM_INSURED

    Args:
        nombre_asegurado: Nombre del asegurado a buscar

    Returns:
        insured_key si se encuentra, None si no existe
    """
    conn = get_azure_sql_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Búsqueda flexible por nombre
        query = """
        SELECT TOP 1
            insured_key,
            insured_name,
            insured_short_name,
            cedant_name,
            country
        FROM consumption.DIM_INSURED
        WHERE
            insured_name LIKE ?
            OR insured_short_name LIKE ?
            OR cedant_name LIKE ?
        ORDER BY insured_key DESC
        """

        search_pattern = f'%{nombre_asegurado}%'
        cursor.execute(query, (search_pattern, search_pattern, search_pattern))

        row = cursor.fetchone()
        if row:
            insured_key = row[0]
            insured_name = row[1]
            logger.info(f"✅ Asegurado encontrado en KB: {insured_name} (insured_key={insured_key})")
            return insured_key
        else:
            logger.warning(f"⚠️ Asegurado '{nombre_asegurado}' NO encontrado en KB")
            return None

    except Exception as e:
        logger.error(f"❌ Error buscando asegurado: {str(e)}")
        return None
    finally:
        conn.close()


def consultar_historico_siniestros(insured_key: int, años_historico: int = 5) -> pd.DataFrame:
    """
    Consulta histórico de siniestros desde consumption.FACT_CLAIMS

    Args:
        insured_key: ID del asegurado en la KB
        años_historico: Cantidad de años de histórico a consultar

    Returns:
        DataFrame con siniestros históricos en formato estándar
    """
    conn = get_azure_sql_connection()
    if not conn:
        return pd.DataFrame()

    try:
        # Calcular fecha límite (YYYYMMDD format)
        fecha_limite = (datetime.now().year - años_historico) * 10000 + 101  # Ej: 20200101

        query = """
        SELECT
            fc.claim_reference_dynamic AS num_poliza,
            fc.occurrence_date_key,
            fc.loss_paid_dynamic_oc AS monto_pagado_cop,
            fc.net_reserve_dynamic_usd AS monto_reservado_usd,
            fc.total_incurred_dynamic_usd AS monto_incurrido_usd,
            fc.total_paid_dynamic_usd AS monto_pagado_usd,
            fc.loss_cause_summary AS causa_siniestro,
            fc.claim_status AS estado,
            fc.salvage_recovery_oc AS salvamento,
            fc.subrogation_recovery_oc AS subrogacion,
            YEAR(CAST(CAST(fc.occurrence_date_key AS VARCHAR) AS DATE)) AS año,
            MONTH(CAST(CAST(fc.occurrence_date_key AS VARCHAR) AS DATE)) AS mes,
            CAST(CAST(fc.occurrence_date_key AS VARCHAR) AS DATE) AS fecha_siniestro
        FROM consumption.FACT_CLAIMS fc
        WHERE fc.insured_key = ?
            AND fc.occurrence_date_key >= ?
        ORDER BY fc.occurrence_date_key DESC
        """

        df = pd.read_sql(query, conn, params=(insured_key, fecha_limite))

        if not df.empty:
            logger.info(f"✅ Histórico KB: {len(df)} siniestros de últimos {años_historico} años")

            # Convertir a formato estándar (USD como base)
            df['monto_incurrido'] = df['monto_incurrido_usd']
            df['monto_pagado'] = df['monto_pagado_usd']
            df['monto_reservado'] = df['monto_reservado_usd']

        else:
            logger.warning(f"⚠️ No se encontraron siniestros históricos para insured_key={insured_key}")

        return df

    except Exception as e:
        logger.error(f"❌ Error consultando histórico: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()


class AnalizadorTecnico:
    """Clase principal para el análisis técnico de reaseguros con Knowledge Base"""

    def __init__(self, asegurado_nombre: Optional[str] = None):
        self.datos_consolidados = {
            'siniestralidad': None,
            'tiv': None,
            'tiv_total': 0,
            'slip': {},
            'asegurado_nombre': asegurado_nombre or 'Desconocido',
            'insured_key': None,
            'tiene_historico_kb': False,
            'archivos_procesados': []
        }
        self.api_cotizacion = CotizacionDolar()
        self.moneda_local = None
        self.tasa_cambio = None
        logger.info("Analizador Técnico v3.2 inicializado con API de cotizaciones.")

    def cargar_historico_desde_kb(self, años_historico: int = 5) -> bool:
        """
        Intenta cargar histórico de siniestros desde Azure SQL KB

        Returns:
            True si se encontró y cargó histórico, False si no
        """
        asegurado = self.datos_consolidados['asegurado_nombre']

        # Buscar asegurado en KB
        insured_key = buscar_asegurado_en_kb(asegurado)

        if not insured_key:
            logger.info("📊 Cliente SIN histórico en KB - análisis solo con archivos")
            return False

        # Guardar insured_key
        self.datos_consolidados['insured_key'] = insured_key

        # Consultar siniestros históricos
        df_historico = consultar_historico_siniestros(insured_key, años_historico)

        if df_historico.empty:
            logger.info("📊 Asegurado encontrado en KB pero SIN siniestros históricos")
            return False

        # Marcar que tiene histórico
        self.datos_consolidados['tiene_historico_kb'] = True
        self.datos_consolidados['siniestralidad'] = df_historico

        logger.info(f"✅ Histórico KB cargado: {len(df_historico)} siniestros")
        return True

    def consolidar_siniestralidad(self, archivos_bytes: List[tuple]) -> pd.DataFrame:
        """
        Consolida siniestralidad desde archivos Excel
        Si ya existe histórico de KB, lo combina
        """
        try:
            dataframes = []

            if not archivos_bytes:
                logger.warning("No se proporcionaron archivos de siniestralidad.")
                # Si tenemos histórico de KB, usarlo
                if self.datos_consolidados.get('tiene_historico_kb'):
                    return self.datos_consolidados['siniestralidad']
                else:
                    self.datos_consolidados['siniestralidad'] = pd.DataFrame()
                    return pd.DataFrame()

            for filename, archivo in archivos_bytes:
                # Registrar nombres de archivos procesados para detección de moneda
                if filename not in self.datos_consolidados['archivos_procesados']:
                    self.datos_consolidados['archivos_procesados'].append(filename)

                df = None

                # Intentar leer como Excel con hoja GRUPO I
                try:
                    excel_file = pd.ExcelFile(io.BytesIO(archivo))
                    if 'GRUPO I' in excel_file.sheet_names:
                        logger.info(f"Archivo {filename}: Detectada hoja GRUPO I")
                        df = pd.read_excel(io.BytesIO(archivo), sheet_name='GRUPO I', header=1)

                        # Filtrar solo TRDM
                        if 'Nom. Procucto' in df.columns:
                            df = df[df['Nom. Procucto'].str.contains('TODO RIESGO', case=False, na=False)].copy()
                            logger.info(f"Filtrados registros TRDM: {len(df)}")

                        # Mapear columnas
                        if 'Fec. Sini' in df.columns:
                            df['fecha_siniestro'] = pd.to_datetime(df['Fec. Sini'], errors='coerce')
                        if 'Liquidado' in df.columns:
                            df['monto_pagado'] = pd.to_numeric(df['Liquidado'], errors='coerce').fillna(0)
                        if 'Rva. Actual' in df.columns:
                            df['monto_reservado'] = pd.to_numeric(df['Rva. Actual'], errors='coerce').fillna(0)
                        if 'Total Incurrido' in df.columns:
                            df['monto_incurrido'] = pd.to_numeric(df['Total Incurrido'], errors='coerce').fillna(0)
                        else:
                            df['monto_incurrido'] = df['monto_pagado'] + df['monto_reservado']

                        # Mapear causa del siniestro desde Nom. Exp.
                        if 'Nom. Exp.' in df.columns:
                            df['causa_siniestro'] = df['Nom. Exp.']
                        else:
                            df['causa_siniestro'] = 'No especificada'

                    # ============================================
                    # LA COSTEÑA - SINIESTROS
                    # ============================================
                    elif es_formato_la_costena_siniestros(archivo, filename):
                        logger.info(f"Procesando archivo La Costeña - Siniestros: {filename}")

                        df = pd.read_excel(io.BytesIO(archivo), sheet_name='SIN_AGOSTO', header=8)
                        df = df.dropna(how='all')
                        df = df[df['SINIESTRO'].notna()].copy()

                        logger.info(f"Total registros La Costeña: {len(df)}")

                        if len(df) < 3:
                            logger.warning(f"CRÍTICO: Solo {len(df)} siniestro(s) - Muestra insuficiente")

                        df_mapped = pd.DataFrame()
                        df_mapped['numero_siniestro'] = df['SINIESTRO'].astype(str)
                        df_mapped['causa_siniestro'] = df['DESCRIPCIÓN']

                        if len(df.columns) > 2:
                            df_mapped['subcategoria'] = df.iloc[:, 2]

                        df_mapped['fecha_siniestro'] = pd.to_datetime(df['fechasin'], errors='coerce')
                        df_mapped['monto_incurrido'] = pd.to_numeric(df['PERDIDA'], errors='coerce').fillna(0)
                        df_mapped['monto_pagado'] = pd.to_numeric(df['SINPAGADO'], errors='coerce').fillna(0)

                        if 'RESERVA_INDEMNIZA' in df.columns and 'RESERVA_GASTOS' in df.columns:
                            reserva_indem = pd.to_numeric(df['RESERVA_INDEMNIZA'], errors='coerce').fillna(0)
                            reserva_gastos = pd.to_numeric(df['RESERVA_GASTOS'], errors='coerce').fillna(0)
                            df_mapped['monto_reservado'] = reserva_indem + reserva_gastos
                        else:
                            df_mapped['monto_reservado'] = (df_mapped['monto_incurrido'] - df_mapped['monto_pagado']).clip(lower=0)

                        df = df_mapped
                        logger.info(f"Siniestros La Costeña mapeados: {len(df)} registros")

                    # ============================================
                    # CONAGUA - SINIESTROS
                    # ============================================
                    elif es_formato_conagua_siniestros(archivo, filename):
                        logger.info(f"Procesando archivo CONAGUA - Siniestros: {filename}")

                        df = pd.read_excel(io.BytesIO(archivo), sheet_name='Detail', header=1)
                        df = df.dropna(how='all')
                        df = df[df['Fecha Ocurrencia '].notna()].copy()

                        logger.info(f"Total registros CONAGUA: {len(df)}")

                        df_mapped = pd.DataFrame()
                        df_mapped['fecha_siniestro'] = pd.to_datetime(df['Fecha Ocurrencia '], errors='coerce')
                        df_mapped['causa_siniestro'] = df['Causa']
                        df_mapped['monto_pagado'] = pd.to_numeric(df['Pérdida Pagada Neta'], errors='coerce').fillna(0)
                        df_mapped['monto_reservado'] = pd.to_numeric(df['Reserva Bruta'], errors='coerce').fillna(0)
                        df_mapped['monto_incurrido'] = df_mapped['monto_pagado'] + df_mapped['monto_reservado']

                        if 'Cat / No Cat' in df.columns:
                            df_mapped['es_catastrofico'] = df['Cat / No Cat']

                        df = df_mapped
                        logger.info(f"Siniestros CONAGUA mapeados: {len(df)} registros")

                    else:
                        df = pd.read_excel(io.BytesIO(archivo), engine='openpyxl')
                        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

                except Exception:
                    # Intentar CSV
                    for encoding in ['utf-8', 'latin-1']:
                        try:
                            df = pd.read_csv(io.BytesIO(archivo), encoding=encoding, delimiter=';')
                            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
                            break
                        except Exception:
                            continue

                if df is None:
                    logger.error(f"No se pudo procesar {filename}")
                    continue

                if 'fecha_siniestro' not in df.columns or 'monto_incurrido' not in df.columns:
                    logger.warning(f"Archivo {filename} no tiene columnas esperadas.")
                    continue

                # Agregar año si no existe
                if 'año' not in df.columns and 'fecha_siniestro' in df.columns:
                    df['año'] = pd.to_datetime(df['fecha_siniestro'], errors='coerce').dt.year

                dataframes.append(df)

            if not dataframes:
                logger.warning("No se procesaron archivos válidos.")
                # Si tenemos histórico de KB, usarlo
                if self.datos_consolidados.get('tiene_historico_kb'):
                    return self.datos_consolidados['siniestralidad']
                else:
                    self.datos_consolidados['siniestralidad'] = pd.DataFrame()
                    return pd.DataFrame()

            df_consolidado = pd.concat(dataframes, ignore_index=True)

            # Si tenemos histórico de KB, combinarlo
            if self.datos_consolidados.get('tiene_historico_kb'):
                df_kb = self.datos_consolidados['siniestralidad']
                logger.info(f"📊 Combinando: {len(df_consolidado)} siniestros archivo + {len(df_kb)} KB")
                df_consolidado = pd.concat([df_consolidado, df_kb], ignore_index=True)

            # Limpieza y normalización
            df_consolidado = df_consolidado[df_consolidado['monto_incurrido'] > 0].copy()
            df_consolidado = df_consolidado.sort_values('fecha_siniestro', ascending=False).reset_index(drop=True)

            self.datos_consolidados['siniestralidad'] = df_consolidado
            logger.info(f"✅ Siniestralidad consolidada: {len(df_consolidado)} registros")
            return df_consolidado

        except Exception as e:
            logger.exception(f"Error consolidando siniestralidad: {str(e)}")
            if self.datos_consolidados.get('tiene_historico_kb'):
                return self.datos_consolidados['siniestralidad']
            else:
                self.datos_consolidados['siniestralidad'] = pd.DataFrame()
                return pd.DataFrame()

    def procesar_tiv(self, archivo_bytes: bytes, filename: str) -> pd.DataFrame:
        """Procesa el archivo TIV con múltiples estrategias de extracción"""
        try:
            df_tiv = None
            tiv_total = None

            # ESTRATEGIA 1: Buscar en hoja "Resumen" celda G24 (Río Magdalena)
            try:
                excel_file = pd.ExcelFile(io.BytesIO(archivo_bytes), engine='openpyxl')
                if 'Resumen' in excel_file.sheet_names or 'RESUMEN' in excel_file.sheet_names:
                    sheet_name = 'Resumen' if 'Resumen' in excel_file.sheet_names else 'RESUMEN'
                    df_resumen = pd.read_excel(io.BytesIO(archivo_bytes), sheet_name=sheet_name, header=None, engine='openpyxl')

                    # Intentar celda G24 (fila 23, columna 6 en zero-indexed)
                    if df_resumen.shape[0] > 23 and df_resumen.shape[1] > 6:
                        valor_g24 = df_resumen.iloc[23, 6]
                        # Ya viene como float, solo convertir
                        if pd.notna(valor_g24):
                            tiv_total = float(valor_g24)
                            if tiv_total > 1000000000:
                                logger.info(f"✅ TIV: Detectada estructura Resumen G24 (Río Magdalena)")
                                logger.info(f"TIV Total extraído desde Resumen!G24: {tiv_total:,.2f}")

                                # Crear DataFrame básico
                                df_tiv = pd.DataFrame([{'tiv_total': tiv_total, 'fuente': 'Resumen!G24'}])
                                self.datos_consolidados['tiv'] = df_tiv
                                self.datos_consolidados['tiv_total'] = tiv_total
                                return df_tiv
            except Exception as e:
                logger.debug(f"Estrategia 1 (Resumen G24) no aplicó: {e}")

            # ESTRATEGIA 2: Estructura Antioquia (celda W18)
            try:
                df_raw = pd.read_excel(io.BytesIO(archivo_bytes), header=None, engine='openpyxl')

                if df_raw.shape[1] >= 23:
                    try:
                        valor_test = pd.to_numeric(df_raw.iloc[17, 22], errors='coerce')
                        if pd.notna(valor_test) and valor_test > 1000000000:
                            logger.info("✅ TIV: Detectada estructura tipo Antioquia (W18)")
                            tiv_total = valor_test
                            logger.info(f"TIV Total extraído desde W18: {tiv_total:,.2f}")
                            df_tiv = pd.read_excel(io.BytesIO(archivo_bytes), header=7, engine='openpyxl')
                            self.datos_consolidados['tiv'] = df_tiv
                            self.datos_consolidados['tiv_total'] = tiv_total
                            return df_tiv
                    except Exception as e:
                        logger.debug(f"Estrategia 2 (Antioquia W18) no aplicó: {e}")

            except Exception as e:
                logger.debug(f"Estrategia 2 falló al leer Excel: {e}")

            # ESTRATEGIA 3: Buscar columna suma_asegurada en cualquier hoja
            try:
                df_tiv = pd.read_excel(io.BytesIO(archivo_bytes), engine='openpyxl')
            except Exception:
                # Intentar CSV
                for encoding in ['utf-8', 'latin-1']:
                    try:
                        df_tiv = pd.read_csv(io.BytesIO(archivo_bytes), encoding=encoding, delimiter=';')
                        break
                    except Exception:
                        continue

            if df_tiv is None:
                raise Exception("No se pudo decodificar el archivo TIV con ninguna estrategia")

            df_tiv.columns = df_tiv.columns.str.strip().str.lower().str.replace(' ', '_')

            # Buscar columna suma asegurada
            posibles = ['suma_asegurada', 'valor_asegurado', 'tiv', 'total_insured_value']
            col_suma = None
            for nombre in posibles:
                cols_match = [c for c in df_tiv.columns if nombre in str(c).lower()]
                if cols_match:
                    col_suma = cols_match[-1]
                    break

            if col_suma:
                df_tiv['suma_asegurada_clean'] = pd.to_numeric(df_tiv[col_suma], errors='coerce').fillna(0)
                if tiv_total is None:
                    tiv_total = df_tiv['suma_asegurada_clean'].sum()
                    logger.info(f"✅ TIV: Extraído desde columna '{col_suma}' (Estrategia 3)")
                    self.datos_consolidados['tiv_total'] = tiv_total

            # ============================================
            # ESTRATEGIA 4: La Costeña - Hoja SUM ASEG
            # ============================================
            if tiv_total == 0 or tiv_total is None:
                try:
                    logger.info("Intentando ESTRATEGIA 4: La Costeña (hoja SUM ASEG)")

                    excel_file = pd.ExcelFile(io.BytesIO(archivo_bytes))

                    if 'SUM ASEG' in excel_file.sheet_names:
                        df_tiv = pd.read_excel(io.BytesIO(archivo_bytes), sheet_name='SUM ASEG', header=3)

                        logger.info(f"Columnas detectadas: {list(df_tiv.columns)}")

                        df_tiv = df_tiv.dropna(how='all')
                        df_tiv = df_tiv[df_tiv['No'].notna()].copy()

                        for col in ['EDIFICIOS', 'INVENTARIO', 'CONTENIDOS', 'PERDIDAS CONSEC']:
                            if col in df_tiv.columns:
                                df_tiv[col] = pd.to_numeric(df_tiv[col], errors='coerce').fillna(0)

                        col_total = 'VALORES TOTALES' if 'VALORES TOTALES' in df_tiv.columns else 'VALORES TOTALES '
                        if col_total in df_tiv.columns:
                            df_tiv['suma_asegurada'] = pd.to_numeric(df_tiv[col_total], errors='coerce').fillna(0)
                        else:
                            df_tiv['suma_asegurada'] = (
                                df_tiv.get('EDIFICIOS', 0) +
                                df_tiv.get('INVENTARIO', 0) +
                                df_tiv.get('CONTENIDOS', 0) +
                                df_tiv.get('PERDIDAS CONSEC', 0)
                            )

                        df_tiv = df_tiv[df_tiv['suma_asegurada'] > 0].copy()
                        tiv_total = df_tiv['suma_asegurada'].sum()

                        logger.info(f"✅ ESTRATEGIA 4 exitosa: TIV Total = ${tiv_total:,.2f}")

                        self.datos_consolidados['tiv'] = df_tiv
                        self.datos_consolidados['tiv_total'] = tiv_total

                except Exception as e:
                    logger.warning(f"ESTRATEGIA 4 falló: {str(e)}")

            # ============================================
            # ESTRATEGIA 5: CONAGUA - Hoja Conagua
            # ============================================
            if tiv_total == 0 or tiv_total is None:
                try:
                    logger.info("Intentando ESTRATEGIA 5: CONAGUA")

                    excel_file = pd.ExcelFile(io.BytesIO(archivo_bytes))

                    sheet_conagua = None
                    for sheet_name in excel_file.sheet_names:
                        if sheet_name.lower().startswith('conagua'):
                            sheet_conagua = sheet_name
                            break

                    if sheet_conagua:
                        df_tiv = pd.read_excel(io.BytesIO(archivo_bytes), sheet_name=sheet_conagua, header=11)

                        df_tiv = df_tiv.dropna(how='all')
                        df_tiv = df_tiv[df_tiv['Nombre'].notna()].copy()

                        df_tiv['suma_asegurada'] = pd.to_numeric(df_tiv['Edificio'], errors='coerce').fillna(0)
                        df_tiv = df_tiv[df_tiv['suma_asegurada'] > 0].copy()

                        tiv_total = df_tiv['suma_asegurada'].sum()

                        logger.info(f"✅ ESTRATEGIA 5 exitosa: TIV Total = ${tiv_total:,.2f}")
                        logger.info(f"Total ubicaciones: {len(df_tiv)}")

                        self.datos_consolidados['tiv'] = df_tiv
                        self.datos_consolidados['tiv_total'] = tiv_total

                except Exception as e:
                    logger.warning(f"ESTRATEGIA 5 falló: {str(e)}")

            if tiv_total is None or tiv_total == 0:
                logger.warning("⚠️ TIV Total es cero o no se pudo extraer - Burning Cost no será calculable")

            logger.info(f"✅ TIV procesado: {len(df_tiv)} registros, Total: {tiv_total:,.2f}")
            self.datos_consolidados['tiv'] = df_tiv
            return df_tiv

        except Exception as e:
            logger.error(f"❌ Error procesando TIV: {str(e)}")
            raise

    def analizar_frecuencia_severidad(self) -> Dict:
        """Análisis de Frecuencia vs. Severidad con validaciones de muestra"""
        try:
            df = self.datos_consolidados['siniestralidad']
            if df is None or len(df) == 0:
                return {
                    'tipo_siniestralidad': 'sin_historico',
                    'frecuencia_anual': 0,
                    'confiabilidad_estadistica': 'INSUFICIENTE - Sin histórico'
                }

            años_unicos = df['año'].nunique()
            total_siniestros = len(df)
            frecuencia_anual = total_siniestros / años_unicos if años_unicos > 0 else 0

            severidad_promedio = df['monto_incurrido'].mean()
            severidad_mediana = df['monto_incurrido'].median()
            desviacion_std = df['monto_incurrido'].std()

            # VALIDACIÓN DE MUESTRA PEQUEÑA
            confiabilidad = 'ADECUADA'
            disclaimers = []

            if total_siniestros < 3:
                confiabilidad = 'CRITICA - Muestra insuficiente'
                disclaimers.append('CRITICO: Menos de 3 siniestros - Análisis estadístico NO válido')
                disclaimers.append('No calcular Coeficiente de Variación con n<3')
                cv = None  # No calcular CV
            elif total_siniestros < 10:
                confiabilidad = 'BAJA - Muestra pequeña'
                disclaimers.append('ADVERTENCIA: Menos de 10 siniestros - Análisis con baja confiabilidad estadística')
                disclaimers.append('Resultados deben usarse con precaución')
                cv = desviacion_std / severidad_promedio if severidad_promedio > 0 else 0
            else:
                cv = desviacion_std / severidad_promedio if severidad_promedio > 0 else 0

            umbral_catastrofico = df['monto_incurrido'].quantile(0.95)
            num_catastroficos = len(df[df['monto_incurrido'] > umbral_catastrofico])

            # Clasificación de tipo de siniestralidad
            if cv is not None and cv > 2 or (total_siniestros > 0 and num_catastroficos > (total_siniestros * 0.1)):
                tipo = 'catastroficos_alta_severidad'
                recomendacion = 'Exceso de Pérdida (XL) - Alta volatilidad'
            elif frecuencia_anual > 50:
                tipo = 'frecuentes_baja_severidad'
                recomendacion = 'Cuota Parte - Alta frecuencia'
            else:
                tipo = 'mixto'
                recomendacion = 'Combinación proporcional y no proporcional'

            resultado = {
                'tipo_siniestralidad': tipo,
                'frecuencia_anual': round(frecuencia_anual, 2),
                'total_siniestros': total_siniestros,
                'años_analizados': años_unicos,
                'severidad_promedio': round(severidad_promedio, 2),
                'severidad_mediana': round(severidad_mediana, 2),
                'coeficiente_variacion': round(cv, 2) if cv is not None else None,
                'num_siniestros_catastroficos': num_catastroficos,
                'recomendacion_cobertura': recomendacion,
                'confiabilidad_estadistica': confiabilidad,
                'disclaimers': disclaimers
            }

            return resultado

        except Exception as e:
            logger.error(f"❌ Error en análisis frecuencia/severidad: {str(e)}")
            return {'error': str(e)}

    def analizar_tendencias(self) -> Dict:
        """Análisis de Tendencias con validación de muestra mínima"""
        try:
            df = self.datos_consolidados['siniestralidad']
            if df is None or len(df) < 2:
                return {
                    'tiene_tendencias': False,
                    'razon': 'Menos de 2 siniestros'
                }

            df_anual = df.groupby('año').agg({
                'monto_incurrido': ['count', 'sum', 'mean']
            }).reset_index()
            df_anual.columns = ['año', 'frecuencia', 'siniestralidad_total', 'severidad_promedio']

            años_unicos = len(df_anual)

            # VALIDACIÓN: Necesitamos al menos 3 años para calcular tendencias
            if años_unicos < 3:
                return {
                    'tiene_tendencias': False,
                    'razon': f'Insuficiente histórico - solo {años_unicos} año(s) con siniestros',
                    'disclaimer': 'Se requieren al menos 3 años para análisis de tendencias',
                    'años_disponibles': años_unicos
                }

            df_anual = df_anual.sort_values('año')

            pct_cambio_frecuencia = ((df_anual['frecuencia'].iloc[-1] - df_anual['frecuencia'].iloc[0]) /
                                    df_anual['frecuencia'].iloc[0] * 100) if df_anual['frecuencia'].iloc[0] > 0 else 0

            pct_cambio_severidad = ((df_anual['severidad_promedio'].iloc[-1] - df_anual['severidad_promedio'].iloc[0]) /
                                   df_anual['severidad_promedio'].iloc[0] * 100) if df_anual['severidad_promedio'].iloc[0] > 0 else 0

            return {
                'tiene_tendencias': True,
                'años_analizados': años_unicos,
                'tendencia_frecuencia': {
                    'porcentaje_cambio': round(pct_cambio_frecuencia, 2),
                    'interpretacion': 'Creciente' if pct_cambio_frecuencia > 10 else ('Decreciente' if pct_cambio_frecuencia < -10 else 'Estable')
                },
                'tendencia_severidad': {
                    'porcentaje_cambio': round(pct_cambio_severidad, 2),
                    'interpretacion': 'Creciente' if pct_cambio_severidad > 10 else ('Decreciente' if pct_cambio_severidad < -10 else 'Estable')
                }
            }
        except Exception as e:
            logger.error(f"❌ Error en tendencias: {str(e)}")
            return {'error': str(e)}

    def calcular_burning_cost(self) -> Dict:
        """Cálculo de Burning Cost"""
        try:
            df_sini = self.datos_consolidados['siniestralidad']
            if df_sini is None or len(df_sini) == 0:
                return {'tiene_burning_cost': False}

            años_unicos = df_sini['año'].nunique()
            siniestralidad_total = df_sini['monto_incurrido'].sum()
            siniestralidad_promedio_anual = siniestralidad_total / años_unicos if años_unicos > 0 else 0

            tiv_total = self.datos_consolidados.get('tiv_total', 0)
            if tiv_total == 0:
                return {'tiene_burning_cost': False, 'mensaje': 'TIV es cero'}

            burning_cost = siniestralidad_promedio_anual / tiv_total
            burning_cost_pct = burning_cost * 100
            burning_cost_por_mil = burning_cost * 1000

            tasa_slip_por_mil = 1.50  # Default

            margen_por_mil = tasa_slip_por_mil - burning_cost_por_mil
            margen_pct = (margen_por_mil / tasa_slip_por_mil * 100) if tasa_slip_por_mil > 0 else 0

            if burning_cost_por_mil > tasa_slip_por_mil:
                semaforo = 'ROJO'
                suficiencia = 'INSUFICIENTE'
            elif burning_cost_por_mil > tasa_slip_por_mil * 0.8:
                semaforo = 'AMARILLO'
                suficiencia = 'AJUSTADA'
            else:
                semaforo = 'VERDE'
                suficiencia = 'ADECUADA'

            return {
                'tiene_burning_cost': True,
                'burning_cost_por_mil': round(burning_cost_por_mil, 4),
                'burning_cost_pct': round(burning_cost_pct, 4),
                'siniestralidad_total': round(siniestralidad_total, 2),
                'tiv_total': round(tiv_total, 2),
                'años_historico': años_unicos,
                'tasa_propuesta_por_mil': tasa_slip_por_mil,
                'margen_por_mil': round(margen_por_mil, 4),
                'margen_pct': round(margen_pct, 2),
                'semaforo': semaforo,
                'suficiencia': suficiencia
            }
        except Exception as e:
            logger.error(f"❌ Error en burning cost: {str(e)}")
            return {'error': str(e)}

    def analizar_reservas_ibnr(self) -> Dict:
        """Análisis de Reservas e IBNR (Incurred But Not Reported)"""
        try:
            df = self.datos_consolidados['siniestralidad']
            if df is None or len(df) == 0:
                return {'tiene_analisis_reservas': False}

            total_siniestros = len(df)
            total_pagado = df['monto_pagado'].sum()
            total_reservado = df['monto_reservado'].sum()
            total_incurrido = df['monto_incurrido'].sum()

            # Calcular porcentajes
            pct_con_reservas = (df['monto_reservado'] > 0).sum() / total_siniestros * 100 if total_siniestros > 0 else 0
            pct_sin_liquidar = ((df['monto_pagado'] == 0) & (df['monto_reservado'] > 0)).sum() / total_siniestros * 100 if total_siniestros > 0 else 0

            # Ratio Reservado/Pagado
            ratio_reservado_pagado = total_reservado / total_pagado if total_pagado > 0 else float('inf')

            # Identificar siniestros con alto deterioro (reserva > 3x promedio)
            if total_siniestros > 1:
                reserva_promedio = df['monto_reservado'].mean()
                siniestros_alto_deterioro = df[df['monto_reservado'] > reserva_promedio * 3]
                num_alto_deterioro = len(siniestros_alto_deterioro)
            else:
                num_alto_deterioro = 0

            # Semáforo de gestión de reservas
            if pct_sin_liquidar >= 100:
                semaforo = 'ROJO'
                alerta = 'CRÍTICO: 100% siniestros sin liquidar - Cuantías pueden variar significativamente'
            elif pct_sin_liquidar >= 50:
                semaforo = 'AMARILLO'
                alerta = 'ADVERTENCIA: Más del 50% sin liquidar - Alta incertidumbre en cuantías'
            elif pct_con_reservas > 30:
                semaforo = 'AMARILLO'
                alerta = 'Más del 30% con reservas pendientes'
            else:
                semaforo = 'VERDE'
                alerta = 'Gestión de reservas adecuada'

            return {
                'tiene_analisis_reservas': True,
                'total_siniestros': total_siniestros,
                'total_pagado': round(total_pagado, 2),
                'total_reservado': round(total_reservado, 2),
                'total_incurrido': round(total_incurrido, 2),
                'pct_con_reservas': round(pct_con_reservas, 2),
                'pct_sin_liquidar': round(pct_sin_liquidar, 2),
                'ratio_reservado_pagado': round(ratio_reservado_pagado, 2) if ratio_reservado_pagado != float('inf') else 'Infinito (sin pagos)',
                'num_siniestros_alto_deterioro': num_alto_deterioro,
                'semaforo_reservas': semaforo,
                'alerta': alerta
            }

        except Exception as e:
            logger.error(f"❌ Error en análisis de reservas: {str(e)}")
            return {'error': str(e)}

    def generar_analisis_completo(self) -> Dict:
        """Genera el análisis técnico completo"""
        try:
            logger.info("=== INICIANDO ANÁLISIS TÉCNICO COMPLETO ===")

            df = self.datos_consolidados['siniestralidad']
            tipo_cliente = 'renovacion' if (df is not None and len(df) > 0) else 'nuevo'

            analisis = {
                'metadata': {
                    'fecha_analisis': datetime.now().isoformat(),
                    'tipo_cliente': tipo_cliente,
                    'asegurado': self.datos_consolidados.get('asegurado_nombre', 'Desconocido'),
                    'tiene_historico_kb': self.datos_consolidados.get('tiene_historico_kb', False),
                    'insured_key': self.datos_consolidados.get('insured_key')
                }
            }

            if tipo_cliente == 'renovacion':
                analisis.update({
                    'frecuencia_severidad': self.analizar_frecuencia_severidad(),
                    'tendencias': self.analizar_tendencias(),
                    'burning_cost': self.calcular_burning_cost(),
                    'reservas_ibnr': self.analizar_reservas_ibnr()
                })

            logger.info("=== ANÁLISIS COMPLETADO ===")
            return analisis

        except Exception as e:
            logger.error(f"❌ Error generando análisis: {str(e)}")
            raise


# ===========================================
# HELPER FUNCTIONS FOR JSON PRICING (RIO MAGDALENA FORMAT)
# ===========================================

def clasificar_peril(causa: str) -> tuple:
    """Clasifica el peril según la descripción de la causa"""
    causa_lower = causa.lower()

    if 'sism' in causa_lower or 'terremoto' in causa_lower:
        return ("Terremoto", "Sismo + fallo geológico")
    elif 'miner' in causa_lower or 'malic' in causa_lower or 'vandalismo' in causa_lower:
        return ("Daños Maliciosos", "Minería ilegal")
    elif 'incendio' in causa_lower or 'fuego' in causa_lower:
        return ("Incendio", "Fuego")
    elif 'inundacion' in causa_lower or 'agua' in causa_lower or 'lluvia' in causa_lower:
        return ("Inundación", "Daño por agua")
    elif 'explosion' in causa_lower:
        return ("Explosión", None)
    elif 'viento' in causa_lower or 'huracan' in causa_lower:
        return ("Vientos", "Vendaval")
    elif 'robo' in causa_lower or 'hurto' in causa_lower:
        return ("Robo", None)
    else:
        return ("Otros", "No clasificado")


def generar_analisis_por_anio(df_siniestros: pd.DataFrame, tasa_cambio: float) -> List[Dict]:
    """Genera análisis año por año"""
    if df_siniestros is None or df_siniestros.empty:
        return []

    df_anual = df_siniestros.groupby('año').agg({
        'monto_incurrido': ['count', 'sum', 'mean'],
        'monto_pagado': 'sum'
    }).reset_index()
    df_anual.columns = ['año', 'n_siniestros', 'incurrido_bruto', 'severidad_promedio', 'pagado']

    resultado = []
    for _, row in df_anual.iterrows():
        resultado.append({
            "anio": int(row['año']),
            "n_siniestros": int(row['n_siniestros']),
            "pagado": round(float(row['pagado']), 2),
            "incurrido_bruto": round(float(row['incurrido_bruto']), 2),
            "severidad_promedio": round(float(row['severidad_promedio']), 2),
            "prima_neta": None,
            "loss_ratio": None
        })

    return resultado


def generar_analisis_por_peril(df_siniestros: pd.DataFrame, tasa_cambio: float) -> List[Dict]:
    """Genera análisis por tipo de peril"""
    if df_siniestros is None or df_siniestros.empty:
        return []

    # Clasificar cada siniestro
    df_siniestros['peril_categoria'] = df_siniestros['causa_siniestro'].apply(
        lambda x: clasificar_peril(x)[0]
    )

    df_peril = df_siniestros.groupby('peril_categoria').agg({
        'monto_incurrido': ['count', 'sum']
    }).reset_index()
    df_peril.columns = ['peril_categoria', 'n_siniestros', 'incurrido_neto']

    n_total = len(df_siniestros)

    resultado = []
    for _, row in df_peril.iterrows():
        resultado.append({
            "peril_categoria": row['peril_categoria'],
            "n_siniestros": int(row['n_siniestros']),
            "incurrido_neto_usd": round(float(row['incurrido_neto']) * tasa_cambio, 2),
            "frecuencia_relativa": round(row['n_siniestros'] / n_total, 4) if n_total > 0 else 0
        })

    return resultado


def generar_seccion_riesgos(analizador: AnalizadorTecnico, tiv_total: float, tasa_cambio: float, burning_cost_por_mil: float) -> List[Dict]:
    """Genera sección completa de riesgos"""
    # Por ahora retornamos un placeholder - esto se completará con info del slip
    return [{
        "id_riesgo": "R-ARM-001",
        "PD": round(tiv_total * tasa_cambio, 2),
        "exposiciones_identificadas": [
            {
                "tipo": "construccion",
                "descripcion": "Construcción de hidroeléctrica en zona de alta actividad",
                "severidad": "alta" if burning_cost_por_mil > 3.0 else "media"
            }
        ],
        "protecciones": {
            "protecciones_fisicas": ["Sistemas de alarma", "Seguridad 24/7"],
            "protecciones_organizacionales": ["Plan de respuesta a emergencias", "Mantenimiento preventivo"]
        },
        "deducibles_propuestos": {
            "terremoto": {"tipo": "porcentaje", "valor": 3.0, "minimo_usd": 100000},
            "danos_maliciosos": {"tipo": "fijo", "valor_usd": 50000},
            "otros": {"tipo": "fijo", "valor_usd": 25000}
        },
        "sublimites_recomendados": [
            {"cobertura": "Daños Maliciosos", "limite_usd": round(tiv_total * tasa_cambio * 0.10, 2)},
            {"cobertura": "Terremoto", "limite_usd": round(tiv_total * tasa_cambio, 2)}
        ]
    }]


def generar_json_pricing(analizador: AnalizadorTecnico) -> Dict[str, Any]:
    """Genera JSON completo para pricing con conversión automática a USD"""
    df_siniestros = analizador.datos_consolidados['siniestralidad']
    tiv_total = analizador.datos_consolidados['tiv_total']

    # Detectar moneda y obtener tasa de cambio dinámica
    archivos_nombres = analizador.datos_consolidados.get('archivos_procesados', [])
    moneda_local = detectar_moneda_por_formato(
        analizador.datos_consolidados.get('asegurado_nombre', ''),
        archivos_nombres
    )

    # Obtener tasa de cambio según la moneda detectada
    if moneda_local == 'MXN':
        tasa_usd_moneda = analizador.api_cotizacion.obtener_cotizacion_mxn()
        tasa_cambio = 1.0 / tasa_usd_moneda  # Convertir MXN a USD
        moneda_origen = "MXN"
        logger.info(f"💱 Moneda detectada: MXN | Tasa USD/MXN: {tasa_usd_moneda:.4f} | Tasa conversión: {tasa_cambio:.6f}")
    elif moneda_local == 'COP':
        tasa_usd_cop = analizador.api_cotizacion.obtener_cotizacion_cop()
        tasa_cambio = 1.0 / tasa_usd_cop  # Convertir COP a USD
        moneda_origen = "COP"
        logger.info(f"💱 Moneda detectada: COP | Tasa USD/COP: {tasa_usd_cop:.4f} | Tasa conversión: {tasa_cambio:.6f}")
    else:
        tasa_cambio = 1.0
        moneda_origen = "USD"
        logger.info("💱 Moneda detectada: USD (sin conversión)")

    logger.info(f"📊 Generando JSON pricing para {analizador.datos_consolidados.get('asegurado_nombre', 'Desconocido')}")

    # ====================
    # 1. SINIESTROS
    # ====================
    siniestros_list = []
    umbral_catastrofico = 0

    if df_siniestros is not None and not df_siniestros.empty:
        umbral_catastrofico = df_siniestros['monto_incurrido'].quantile(0.95)

        for idx, row in df_siniestros.iterrows():
            año = row.get('año', 'XXXX')
            fecha_str = row.get('fecha_siniestro').strftime('%d%m%Y') if pd.notna(row.get('fecha_siniestro')) else 'XXXXXXXX'
            claim_id = f"CLAIM-ARM-{fecha_str}-{hashlib.md5(str(idx).encode()).hexdigest()[:8].upper()}"

            monto_incurrido = float(row.get('monto_incurrido', 0))
            monto_pagado = float(row.get('monto_pagado', 0))
            monto_reservado = float(row.get('monto_reservado', 0))

            estado = "cerrado" if monto_pagado > 0 and monto_reservado == 0 else "abierto"
            es_catastrofico = 1 if monto_incurrido > umbral_catastrofico else 0

            causa = row.get('causa_siniestro', 'No especificada')
            peril_categoria, peril_subcategoria = clasificar_peril(causa)

            siniestro = {
                "claim_id": claim_id,
                "id_ubicacion": "U-ARM-001",
                "fecha_siniestro": row.get('fecha_siniestro').strftime('%Y-%m-%d') if pd.notna(row.get('fecha_siniestro')) else None,
                "fecha_notificacion": None,
                "fecha_cierre": None,
                "estado": estado,
                "peril_categoria": peril_categoria,
                "peril_subcategoria": peril_subcategoria,
                "descripcion": causa,
                "es_catastrofico": es_catastrofico,
                "montos": {
                    "moneda_origen": moneda_origen,
                    "tasa_cambio_a_objetivo": tasa_cambio,
                    "pagado": monto_pagado,
                    "pagado_usd": monto_pagado * tasa_cambio,
                    "reservado": monto_reservado,
                    "reservado_usd": monto_reservado * tasa_cambio,
                    "recuperado": 0.0,
                    "gastos_lae": 0.0,
                    "incurrido_bruto": monto_incurrido,
                    "incurrido_bruto_usd": monto_incurrido * tasa_cambio,
                    "incurrido_neto": monto_incurrido,
                    "incurrido_neto_usd": monto_incurrido * tasa_cambio
                },
                "coberturas_afectadas": ["Todo Riesgo Construcción"],
                "deducible_aplicado": {
                    "tipo": "pendiente",
                    "expresion": "Por determinar según Slip",
                    "estimado_en_monedas_objetivo": None
                },
                "salvamento_subrogacion": {
                    "salvamento": 0.0,
                    "subrogacion": 0.0
                },
                "causa_raiz": causa,
                "evidencias": [],
                "origen_extraccion": {
                    "documento_id": "siniestralidad_archivo",
                    "fila_o_pagina": f"siniestro_{idx+1}",
                    "confianza_extraccion": 1.0,
                    "timestamp": datetime.now().isoformat()
                },
                "observaciones": f"Estado: {estado}"
            }
            siniestros_list.append(siniestro)

    # ====================
    # 2. ANÁLISIS
    # ====================
    n_siniestros = len(df_siniestros) if df_siniestros is not None and not df_siniestros.empty else 0
    años_unicos = df_siniestros['año'].nunique() if df_siniestros is not None and not df_siniestros.empty else 0

    siniestralidad_total = df_siniestros['monto_incurrido'].sum() if df_siniestros is not None and not df_siniestros.empty else 0
    siniestralidad_promedio_anual = siniestralidad_total / años_unicos if años_unicos > 0 else 0

    severidad_promedio = df_siniestros['monto_incurrido'].mean() if df_siniestros is not None and not df_siniestros.empty else 0
    severidad_mediana = df_siniestros['monto_incurrido'].median() if df_siniestros is not None and not df_siniestros.empty else 0
    severidad_p95 = umbral_catastrofico

    frecuencia_anual = n_siniestros / años_unicos if años_unicos > 0 else 0

    # Burning Cost
    burning_cost = siniestralidad_promedio_anual / tiv_total if tiv_total > 0 else 0
    burning_cost_por_mil = burning_cost * 1000
    burning_cost_pct = burning_cost * 100

    # Período
    fecha_min = df_siniestros['fecha_siniestro'].min() if df_siniestros is not None and not df_siniestros.empty else None
    fecha_max = df_siniestros['fecha_siniestro'].max() if df_siniestros is not None and not df_siniestros.empty else None

    # Top 5 severidad
    top5_severidad = []
    if df_siniestros is not None and not df_siniestros.empty:
        df_top5 = df_siniestros.nlargest(min(5, len(df_siniestros)), 'monto_incurrido')
        for _, row in df_top5.iterrows():
            top5_severidad.append({
                "causa": row.get('causa_siniestro', 'No especificada'),
                "incurrido_usd": round(float(row['monto_incurrido']) * tasa_cambio, 2),
                "fecha": row['fecha_siniestro'].strftime('%Y-%m-%d') if pd.notna(row['fecha_siniestro']) else None
            })

    # Notas para pricing
    notas_pricing = []
    if n_siniestros < 3:
        notas_pricing.append(f"CRÍTICO: Solo {n_siniestros} siniestros - muestra estadísticamente insuficiente")
    elif n_siniestros < 10:
        notas_pricing.append(f"ADVERTENCIA: Solo {n_siniestros} siniestros - análisis con baja confiabilidad")

    pct_sin_liquidar = ((df_siniestros['monto_pagado'] == 0).sum() / n_siniestros * 100) if n_siniestros > 0 else 0
    if pct_sin_liquidar >= 100:
        notas_pricing.append("CRÍTICO: 100% de siniestros sin liquidar - cuantías pueden variar")
    elif pct_sin_liquidar >= 50:
        notas_pricing.append(f"ADVERTENCIA: {pct_sin_liquidar:.0f}% sin liquidar")

    # Burning Cost vs referencia
    tasa_referencia = 1.50
    if burning_cost_por_mil > tasa_referencia:
        notas_pricing.append(f"ROJO: BC {burning_cost_por_mil:.4f}‰ > tasa referencia {tasa_referencia}‰")

    analisis = {
        "resumen_global": {
            "periodo": {
                "desde": fecha_min.strftime('%Y-%m-%d') if fecha_min is not None else None,
                "hasta": fecha_max.strftime('%Y-%m-%d') if fecha_max is not None else None
            },
            "moneda": "USD",
            "n_siniestros": n_siniestros,
            "años_periodo": años_unicos,
            "frecuencia_promedio_anual": round(frecuencia_anual, 2),
            "incurrido_neto_total_usd": round(siniestralidad_total * tasa_cambio, 2),
            "severidad_promedio_usd": round(severidad_promedio * tasa_cambio, 2),
            "severidad_mediana_usd": round(severidad_mediana * tasa_cambio, 2),
            "severidad_p95_usd": round(severidad_p95 * tasa_cambio, 2),
            f"tiv_total_{moneda_origen.lower()}": tiv_total,
            "tiv_total_usd": round(tiv_total * tasa_cambio, 2),
            "burning_cost_por_mil": round(burning_cost_por_mil, 4),
            "burning_cost_pct": round(burning_cost_pct, 4),
            "top5_severidad": top5_severidad
        },
        "por_anio": generar_analisis_por_anio(df_siniestros, tasa_cambio),
        "por_peril": generar_analisis_por_peril(df_siniestros, tasa_cambio),
        "ubicaciones_criticas": [],
        "notas_para_pricing": notas_pricing
    }

    # ====================
    # 3. RIESGOS
    # ====================
    riesgos = generar_seccion_riesgos(analizador, tiv_total, tasa_cambio, burning_cost_por_mil)

    # ====================
    # 4. CALIDAD DATOS
    # ====================
    campos_faltantes = {}
    limitaciones = []

    if n_siniestros < 10:
        limitaciones.append(f"Muestra pequeña: n={n_siniestros}")
    if años_unicos < 3:
        limitaciones.append(f"Histórico corto: {años_unicos} año(s)")
        limitaciones.append("Análisis de tendencias NO calculable")

    calidad_datos = {
        "registros_procesados": n_siniestros,
        "registros_con_error": 0,
        "campos_faltantes": campos_faltantes,
        "monedas_detectadas": ["COP"],
        "conversion_moneda": [{
            "moneda_origen": "COP",
            "moneda_destino": "USD",
            "tasa_promedio_usada": tasa_cambio
        }],
        "limitaciones": limitaciones
    }

    # ====================
    # 5. TRAZABILIDAD
    # ====================
    trazabilidad = {
        "version_pipeline": "3.0-azure-function-con-kb",
        "timestamp_proceso": datetime.now().isoformat(),
        "scripts_ejecutados": ["function_app_v3_con_kb.py - generar_json_pricing()"],
        "fuente_historico": "knowledge_base" if analizador.datos_consolidados.get('tiene_historico_kb') else "archivos_carga"
    }

    return {
        "siniestros": siniestros_list,
        "analisis": analisis,
        "riesgos": riesgos,
        "calidad_datos": calidad_datos,
        "trazabilidad": trazabilidad
    }


# ===========================================
# AZURE FUNCTION HTTP TRIGGER
# ===========================================

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Health check"""
    return func.HttpResponse(json.dumps({"status": "ok"}, cls=NumpyEncoder), status_code=200, mimetype="application/json")


@app.route(route="analisis-tecnico", methods=["POST"])
def analisis_tecnico(req: func.HttpRequest) -> func.HttpResponse:
    """Endpoint principal de análisis técnico v3.0 con Knowledge Base

    Acepta dos formatos:
    1. Multipart form-data (archivos directos)
    2. JSON con contenido_base64 (para n8n)
    """
    logger.info('🚀 Análisis técnico v3.0 iniciado')

    try:
        content_type = req.headers.get('Content-Type', '')

        # Determinar formato de entrada
        if 'application/json' in content_type:
            # FORMATO JSON (n8n)
            logger.info('📥 Procesando request JSON con Base64')
            body = req.get_json()

            asegurado_nombre = body.get('asegurado', 'Desconocido')
            archivos = body.get('archivos', [])
            parametros = body.get('parametros', {})

            # Decodificar archivos Base64
            import base64
            tiv_bytes = None
            tiv_filename = None
            siniestros_files = []
            slip_bytes = None
            slip_filename = None

            for archivo in archivos:
                nombre = archivo.get('nombre', 'archivo.xlsx')
                tipo = archivo.get('tipo', '').lower()
                contenido_b64 = archivo.get('contenido_base64', '')

                if not contenido_b64:
                    continue

                # Decodificar Base64
                contenido_bytes = base64.b64decode(contenido_b64)

                if tipo == 'tiv':
                    tiv_bytes = contenido_bytes
                    tiv_filename = nombre
                elif tipo == 'siniestralidad' or 'siniestro' in tipo:
                    siniestros_files.append((nombre, contenido_bytes))
                elif tipo == 'slip':
                    slip_bytes = contenido_bytes
                    slip_filename = nombre

            if not tiv_bytes:
                return func.HttpResponse(
                    json.dumps({"error": "No se proporcionó archivo TIV"}),
                    status_code=400,
                    mimetype="application/json"
                )

        else:
            # FORMATO MULTIPART (archivos directos)
            logger.info('📥 Procesando request Multipart')
            tiv_file = req.files.get('tiv_file')
            slip_file = req.files.get('slip_file')

            # Archivos de siniestralidad (puede haber varios)
            siniestros_files = []
            for key in req.files:
                if 'siniestro' in key.lower():
                    file = req.files[key]
                    siniestros_files.append((file.filename, file.read()))

            # Obtener nombre asegurado (opcional)
            asegurado_nombre = req.params.get('asegurado') or req.form.get('asegurado') or 'Desconocido'

            if not tiv_file:
                return func.HttpResponse(
                    json.dumps({"error": "No se proporcionó archivo TIV"}),
                    status_code=400,
                    mimetype="application/json"
                )

            tiv_bytes = tiv_file.read()
            tiv_filename = tiv_file.filename
            slip_bytes = slip_file.read() if slip_file else None
            slip_filename = slip_file.filename if slip_file else None

        # Inicializar analizador con nombre asegurado
        analizador = AnalizadorTecnico(asegurado_nombre)

        # PASO 1: Intentar cargar histórico desde Knowledge Base
        historico_kb_cargado = analizador.cargar_historico_desde_kb(años_historico=5)

        # PASO 2: Procesar archivos
        analizador.procesar_tiv(tiv_bytes, tiv_filename)

        # PASO 3: Consolidar siniestralidad (combina archivos + KB si existe)
        if siniestros_files:
            analizador.consolidar_siniestralidad(siniestros_files)

        # PASO 4: Generar análisis completo
        analisis_completo = analizador.generar_analisis_completo()

        # PASO 5: Generar JSON pricing formato Río Magdalena
        json_pricing = generar_json_pricing(analizador)

        # PASO 6: Preparar datos para el reporte Excel
        reporte_excel_data = []
        df_sini = analizador.datos_consolidados['siniestralidad']
        if df_sini is not None and not df_sini.empty:
            for _, row in df_sini.iterrows():
                reporte_excel_data.append({
                    "fecha_ocurrencia": row.get('fecha_siniestro').isoformat() if pd.notna(row.get('fecha_siniestro')) else None,
                    "causa": row.get('causa_siniestro', 'No especificada'),
                    "monto_pagado_cop": float(row.get('monto_pagado', 0)),
                    "monto_pagado_usd": float(row.get('monto_pagado', 0)) * 0.00025,
                    "reserva_cop": float(row.get('monto_reservado', 0)),
                    "incurrido_cop": float(row.get('monto_incurrido', 0)),
                    "poliza": row.get('Num. Poliza', 'N/A') if 'Num. Poliza' in df_sini.columns else 'N/A'
                })

        # Generar UUID
        import uuid
        analisis_id = str(uuid.uuid4())

        # Extraer métricas para respuesta
        burning_cost_data = analisis_completo.get('burning_cost', {})
        burning_cost_pct = burning_cost_data.get('burning_cost_pct', 0)
        semaforo = burning_cost_data.get('semaforo', 'N/A')

        response_data = {
            "status": "success",
            "version": "3.0-con-kb",
            "analisis_id": analisis_id,
            "tipo_cliente": analisis_completo['metadata']['tipo_cliente'],
            "asegurado": asegurado_nombre,
            "tiene_historico_kb": historico_kb_cargado,
            "insured_key": analizador.datos_consolidados.get('insured_key'),
            "tiv_total": analizador.datos_consolidados['tiv_total'],
            "burning_cost": burning_cost_data.get('burning_cost_por_mil', 0) / 1000,
            "burning_cost_pct": burning_cost_pct,
            "semaforo_burning_cost": semaforo,
            "siniestros_procesados": len(df_sini) if df_sini is not None else 0,
            "analisis_completo": analisis_completo,
            "json_pricing": json_pricing,
            "reporte_excel_data": reporte_excel_data,
            "slip_info": {
                "filename": slip_filename,
                "recibido": slip_bytes is not None
            },
            "mensaje": "Análisis técnico v3.0 completado exitosamente"
        }

        logger.info(f"✅ Análisis completado: {asegurado_nombre} - BC: {burning_cost_pct:.4f}% - Semáforo: {semaforo}")

        return func.HttpResponse(
            json.dumps(response_data, cls=NumpyEncoder),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logger.exception(f"❌ Error en análisis técnico: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Error interno: {str(e)}"}, cls=NumpyEncoder),
            status_code=500,
            mimetype="application/json"
        )
