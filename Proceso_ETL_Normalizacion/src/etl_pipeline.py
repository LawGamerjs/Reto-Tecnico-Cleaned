import pandas as pd
import numpy as np
from datetime import datetime
import os

class AsistenciaETL:
    
    def __init__(self, ruta_input: str, ruta_output: str):
        self.ruta_input = ruta_input
        self.ruta_output = ruta_output
        self.columnas_fijas = [
            'DNI', 'APELLIDOS Y NOMBRES', 'CARGO', 'CLIENTE', 'DIRECCION', 
            'SUPERVISOR', 'JORNADA', 'HORARIO', 'DESCANSO', 
            'UNIDAD', 'FECHA DE INGRESO', 'FECHA DE CESE'
        ]
        self.diccionario_estados = {
            'A': 'Asistencia', 'D': 'Descanso', 'F': 'Falta', 
            'C': 'Cese', 'DM': 'Descanso Médico', 'M': 'Maternidad', 
            'LSG': 'Licencia sin Goce'
        }

    def _normalizar_cabeceras_fechas(self, columnas_variables: list) -> list:
        fechas_procesadas = []
        for col in columnas_variables:
            try:
                serial_num = int(float(col))
                fecha = pd.to_datetime(serial_num, unit='D', origin='1899-12-30').date()
            except (ValueError, TypeError):
                fecha = pd.to_datetime(col, errors='coerce').date()
            fechas_procesadas.append(fecha)
        return fechas_procesadas

    def ejecutar_pipeline(self) -> pd.DataFrame:
        print(f"[{datetime.now().strftime('%X')}] Cargando archivo Excel original...")
        if not os.path.exists(self.ruta_input):
            raise FileNotFoundError(f"No existe el archivo de entrada en: {self.ruta_input}")
            
        df_raw = pd.read_excel(self.ruta_input, sheet_name='Hoja1')
        df_raw.columns = [str(col).strip() for col in df_raw.columns]

        columnas_actuales = df_raw.columns.tolist()
        columnas_variables = [col for col in columnas_actuales if col not in self.columnas_fijas]

        print(f"[{datetime.now().strftime('%X')}] Parseando nombres de columnas a fechas...")
        fechas_normalizadas = self._normalizar_cabeceras_fechas(columnas_variables)
        
        dict_renombrar = dict(zip(columnas_variables, fechas_normalizadas))
        df_renombrado = df_raw.rename(columns=dict_renombrar)

        print(f"[{datetime.now().strftime('%X')}] Forzando tipos de datos y limpieza de texto...")
        df_renombrado['DNI'] = df_renombrado['DNI'].astype(str).str.strip().str.zfill(8)
        df_renombrado['FECHA DE INGRESO'] = pd.to_datetime(df_renombrado['FECHA DE INGRESO'], errors='coerce').dt.date
        df_renombrado['FECHA DE CESE'] = pd.to_datetime(df_renombrado['FECHA DE CESE'], errors='coerce').dt.date
        
        for col in ['APELLIDOS Y NOMBRES', 'CARGO', 'CLIENTE', 'SUPERVISOR', 'UNIDAD']:
            if col in df_renombrado.columns:
                df_renombrado[col] = df_renombrado[col].astype(str).str.strip()

        print(f"[{datetime.now().strftime('%X')}] Aplicando melt para pasar a formato largo...")
        df_largo = df_renombrado.melt(
            id_vars=self.columnas_fijas,
            value_vars=fechas_normalizadas,
            var_name='fecha_asistencia',
            value_name='estado_original'
        )

        print(f"[{datetime.now().strftime('%X')}] Mapeando estados y aislando códigos 16 y 20...")
        df_largo['estado_limpio'] = df_largo['estado_original'].astype(str).str.strip().str.upper()
        df_largo['estado_normalizado'] = df_largo['estado_limpio'].map(self.diccionario_estados)
        
        df_largo['es_atipico'] = df_largo['estado_normalizado'].isna()
        df_largo.loc[df_largo['es_atipico'], 'estado_normalizado'] = 'Atípico por Verificar'

        def verificar_contrato_activo(row):
            ingreso = row['FECHA DE INGRESO']
            cese = row['FECHA DE CESE']
            actual = row['fecha_asistencia']
            if pd.isna(ingreso) or actual is None:
                return False
            if pd.isna(cese):
                return actual >= ingreso
            return ingreso <= actual <= cese

        df_largo['es_activo_en_fecha'] = df_largo.apply(verificar_contrato_activo, axis=1)

        print(f"[{datetime.now().strftime('%X')}] Exportando archivo procesado a la carpeta processed...")
        os.makedirs(os.path.dirname(self.ruta_output), exist_ok=True)
        df_largo.to_csv(self.ruta_output, index=False, encoding='utf-8-sig')
        
        self._imprimir_metricas_auditoria(df_largo)
        return df_largo

    def _imprimir_metricas_auditoria(self, df: pd.DataFrame):
        total_filas = len(df)
        atipicos = df['es_atipico'].sum()
        fuera_contrato = (~df['es_activo_en_fecha']).sum()
        horarios_vacios = df['HORARIO'].isna().sum() + (df['HORARIO'] == 'nan').sum()
        
        print("\n" + "="*60)
        print("      REPORTE DE AUDITORÍA Y CALIDAD DE DATOS (ETL)")
        print("="*60)
        print(f" Total registros generados (Formato Largo) : {total_filas:,}")
        print(f" Marcas con códigos atípicos (16, 20, NaN) : {atipicos:,}")
        print(f" Asistencias fuera de vigencia de contrato : {fuera_contrato:,}")
        print(f" Colaboradores con celda de horario vacía  : {horarios_vacios:,}")
        print("="*60 + "\n")

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RUTA_IN = os.path.join(BASE_DIR, "data", "raw", "Base_a_corregir.xlsx")
    RUTA_OUT = os.path.join(BASE_DIR, "data", "processed", "asistencia_larga_limpia.csv")
    
    try:
        pipeline = AsistenciaETL(ruta_input=RUTA_IN, ruta_output=RUTA_OUT)
        df_final = pipeline.ejecutar_pipeline()
    except Exception as error:
        print(f"\nFallo en la ejecución del script: {error}")