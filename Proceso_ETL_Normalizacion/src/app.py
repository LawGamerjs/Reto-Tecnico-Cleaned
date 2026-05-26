import streamlit as st
import pandas as pd
import plotly.express as px
import os
import datetime
from supabase import create_client, Client

st.set_page_config(
    page_title="Dashboard de Asistencia - Control Operativo",
    layout="wide"
)

@st.cache_resource
def inicializar_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

@st.cache_data
def cargar_datos_supabase() -> pd.DataFrame:
    try:
        supabase = inicializar_supabase()
        response = supabase.table("asistencia_procesada").select("*").limit(20000).execute()
        
        if not response.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        for col in ['id', 'created_at']:
            if col in df.columns:
                df = df.drop(columns=[col])
        
        columnas_mapeo = {
            'dni': 'DNI',
            'apellidos_y_nombres': 'APELLIDOS Y NOMBRES',
            'cargo': 'CARGO',
            'cliente': 'CLIENTE',
            'direccion': 'DIRECCION',
            'supervisor': 'SUPERVISOR',
            'jornada': 'JORNADA',
            'horario': 'HORARIO',
            'descanso': 'DESCANSO',
            'unidad': 'UNIDAD',
            'fecha_ingreso': 'FECHA DE INGRESO',
            'fecha_cese': 'FECHA DE CESE'
        }
        
        columnas_a_renombrar = {k: v for k, v in columnas_mapeo.items() if k in df.columns}
        df = df.rename(columns=columnas_a_renombrar)
        
        if 'DNI' in df.columns:
            df['DNI'] = df['DNI'].astype(str).str.strip().str.zfill(8)
            
        if 'fecha_asistencia' in df.columns:
            df['fecha_asistencia'] = pd.to_datetime(df['fecha_asistencia']).dt.date
            
        if 'FECHA DE INGRESO' in df.columns:
            df['FECHA DE INGRESO'] = pd.to_datetime(df['FECHA DE INGRESO']).dt.date
            
        if 'FECHA DE CESE' in df.columns:
            df['FECHA DE CESE'] = pd.to_datetime(df['FECHA DE CESE']).dt.date
            
        return df
    except Exception:
        return pd.DataFrame()

df_asistencia = cargar_datos_supabase()

if df_asistencia.empty:
    st.error("No se pudieron recuperar datos desde la tabla 'asistencia_procesada' en Supabase.")
else:
    st.title("Métricas de Control de Asistencia y Calidad de Datos")
    st.markdown("---")

    st.sidebar.header("Filtros de Control Operativo")
    
    fecha_min = datetime.date(2026, 4, 19)
    fecha_max = datetime.date(2026, 5, 18)
    
    if 'rango_seleccionado' not in st.session_state:
        st.session_state.rango_seleccionado = [fecha_min, fecha_max]
        
    rango_fechas = st.sidebar.date_input(
        "Periodo de Análisis",
        value=st.session_state.rango_seleccionado,
        min_value=fecha_min,
        max_value=fecha_max
    )
    
    if isinstance(rango_fechas, (list, tuple)) and len(rango_fechas) == 2:
        st.session_state.rango_seleccionado = list(rango_fechas)
        f_inicio, f_fin = rango_fechas
    elif isinstance(rango_fechas, (list, tuple)) and len(rango_fechas) == 1:
        f_inicio = f_fin = rango_fechas[0]
    else:
        f_inicio, f_fin = st.session_state.rango_seleccionado

    mask = (df_asistencia['fecha_asistencia'] >= f_inicio) & (df_asistencia['fecha_asistencia'] <= f_fin)
    
    lista_clientes = sorted(df_asistencia['CLIENTE'].dropna().unique().tolist())
    clientes_sel = st.sidebar.multiselect("Cliente", options=lista_clientes, placeholder="Seleccionar opciones")
    
    lista_unidades = sorted(df_asistencia['UNIDAD'].dropna().unique().tolist())
    unidades_sel = st.sidebar.multiselect("Unidad", options=lista_unidades, placeholder="Seleccionar opciones")
    
    lista_supervisores = sorted(df_asistencia['SUPERVISOR'].dropna().unique().tolist())
    supervisores_sel = st.sidebar.multiselect("Supervisor", options=lista_supervisores, placeholder="Seleccionar opciones")
    
    lista_cargos = sorted(df_asistencia['CARGO'].dropna().unique().tolist())
    cargos_sel = st.sidebar.multiselect("Cargo", options=lista_cargos, placeholder="Seleccionar opciones")
    
    lista_jornadas = sorted(df_asistencia['JORNADA'].dropna().unique().tolist())
    jornadas_sel = st.sidebar.multiselect("Jornada", options=lista_jornadas, placeholder="Seleccionar opciones")
    
    lista_estados = sorted(df_asistencia['estado_normalizado'].dropna().unique().tolist())
    estados_sel = st.sidebar.multiselect("Estado", options=lista_estados, placeholder="Seleccionar opciones")

    if clientes_sel:
        mask &= df_asistencia['CLIENTE'].isin(clientes_sel)
    if unidades_sel:
        mask &= df_asistencia['UNIDAD'].isin(unidades_sel)
    if supervisores_sel:
        mask &= df_asistencia['SUPERVISOR'].isin(supervisores_sel)
    if cargos_sel:
        mask &= df_asistencia['CARGO'].isin(cargos_sel)
    if jornadas_sel:
        mask &= df_asistencia['JORNADA'].isin(jornadas_sel)
    if estados_sel:
        mask &= df_asistencia['estado_normalizado'].isin(estados_sel)
        
    df_filtrado = df_asistencia[mask]

    cabeceras_limpias = {
        'fecha_asistencia': 'Fecha Asistencia',
        'estado_original': 'Estado Original',
        'estado_limpio': 'Estado Limpio',
        'estado_normalizado': 'Estado Normalizado',
        'es_atipico': 'Es Atípico',
        'es_activo_en_fecha': 'Contrato Activo'
    }

    tab_dashboard, tab_calidad, tab_detalle, tab_arquitectura = st.tabs([
        "Dashboard de Gestión", 
        "Módulo de Calidad de Datos", 
        "Vista de Datos Detallada",
        "Modelo de Datos (Arquitectura)"
    ])

    with tab_dashboard:
        df_activos = df_filtrado[df_filtrado['es_activo_en_fecha'] == True]
        headcount_activo = df_activos['DNI'].nunique()
        total_dias_esperados = len(df_activos)
        
        if total_dias_esperados > 0:
            tasa_asistencia = (df_activos['estado_normalizado'] == 'Asistencia').sum() / total_dias_esperados
            tasa_faltas = (df_activos['estado_normalizado'] == 'Falta').sum() / total_dias_esperados
        else:
            tasa_asistencia = tasa_faltas = 0.0

        conteo_descansos = (df_filtrado['estado_normalizado'] == 'Descanso').sum()
        conteo_ceses = (df_filtrado['estado_normalizado'] == 'Cese').sum()
        conteo_atipicos = df_filtrado['es_atipico'].sum()

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Personal Activo", f"{headcount_activo:,}")
        col2.metric("Tasa Asistencia", f"{tasa_asistencia:.1%}")
        col3.metric("Tasa Faltas", f"{tasa_faltas:.1%}")
        col4.metric("Descansos Prog.", f"{conteo_descansos:,}")
        col5.metric("Registros Cese", f"{conteo_ceses:,}")
        col6.metric("Datos Atípicos", f"{conteo_atipicos:,}")

        st.markdown("---")
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.subheader("Evolución Temporal Diaria de Estados")
            df_linea = df_filtrado.groupby(['fecha_asistencia', 'estado_normalizado']).size().reset_index(name='registros')
            fig_linea = px.line(
                df_linea, x='fecha_asistencia', y='registros', color='estado_normalizado',
                labels={'fecha_asistencia': 'Fecha', 'registros': 'Registros', 'estado_normalizado': 'Estado Normalizado'}, template="plotly_white"
            )
            st.plotly_chart(fig_linea, use_container_width=True)
            
        with col_graf2:
            st.subheader("Ranking de Ausentismo por Unidad Operativa")
            df_unidades = df_activos.groupby('UNIDAD').apply(
                lambda x: (x['estado_normalizado'] == 'Falta').sum() / len(x) if len(x) > 0 else 0
            ).reset_index(name='tasa_falta').sort_values(by='tasa_falta', ascending=False).head(10)
            
            fig_barra = px.bar(
                df_unidades, x='tasa_falta', y='UNIDAD', orientation='h',
                labels={'tasa_falta': 'Porcentaje de Faltas', 'UNIDAD': 'Unidad'},
                template="plotly_white", color_discrete_sequence=['#E15759']
            )
            fig_barra.update_layout(xaxis_tickformat='.1%')
            st.plotly_chart(fig_barra, use_container_width=True)

    with tab_calidad:
        st.subheader("Inconsistencias Estructurales Detectadas")
        nulos_horario = df_filtrado['HORARIO'].isna().sum() + (df_filtrado['HORARIO'] == 'nan').sum()
        fuera_contrato = (~df_filtrado['es_activo_en_fecha']).sum()
        
        col_q1, col_q2, col_q3 = st.columns(3)
        col_q1.metric("Registros con Código 16/20/Nulo", f"{conteo_atipicos:,}")
        col_q2.metric("Marcas Fuera de Contrato Activo", f"{fuera_contrato:,}")
        col_q3.metric("Nulos en Columna de Horario", f"{nulos_horario:,}")
        
        st.markdown("---")
        df_errores = df_filtrado[df_filtrado['es_atipico'] | (~df_filtrado['es_activo_en_fecha'])]
        if not df_errores.empty:
            df_errores_print = df_errores[['DNI', 'APELLIDOS Y NOMBRES', 'CLIENTE', 'UNIDAD', 'fecha_asistencia', 'estado_original', 'estado_normalizado', 'es_activo_en_fecha']].rename(columns=cabeceras_limpias)
            df_errores_print = df_errores_print.fillna('NAN').astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            st.dataframe(df_errores_print, use_container_width=True, hide_index=True)
        else:
            st.success("Cero anomalías detectadas para el filtro actual.")

    with tab_detalle:
        st.subheader("Explorador y Descarga de Datos")
        col_down1, col_down2 = st.columns(2)
        
        df_csv_filtrado = df_filtrado.rename(columns=cabeceras_limpias).fillna('NAN')
        for c in df_csv_filtrado.columns:
            df_csv_filtrado[c] = df_csv_filtrado[c].astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            
        csv_filtrado_bytes = df_csv_filtrado.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        col_down1.download_button(
            label="Descargar Base Filtrada (CSV)", data=csv_filtrado_bytes,
            file_name="base_asistencia_filtrada.csv", mime="text/csv"
        )
        
        df_resumen_trabajador = df_activos.groupby(['DNI', 'APELLIDOS Y NOMBRES', 'CLIENTE', 'UNIDAD']).agg(
            Dias_Esperados=('fecha_asistencia', 'count'),
            Asistencias=('estado_normalizado', lambda x: (x == 'Asistencia').sum()),
            Faltas=('estado_normalizado', lambda x: (x == 'Falta').sum())
        ).reset_index()
        
        df_resumen_trabajador_print = df_resumen_trabajador.rename(columns={
            'Dias_Esperados': 'Días Esperados',
            'Asistencias': 'Asistencias',
            'Faltas': 'Faltas'
        }).fillna('NAN')
        
        for c in df_resumen_trabajador_print.columns:
            df_resumen_trabajador_print[c] = df_resumen_trabajador_print[c].astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            
        csv_resumen_bytes = df_resumen_trabajador_print.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        col_down2.download_button(
            label="Descargar Resumen Agregado (CSV)", data=csv_resumen_bytes,
            file_name="resumen_agregado_trabajadores.csv", mime="text/csv"
        )
        
        st.markdown("---")
        search_query = st.text_input("Buscador por Nombre o DNI:")
        
        if search_query:
            clean_query = search_query.strip()
            regex_pattern = rf"\b{clean_query}\b"
            df_display = df_filtrado[
                df_filtrado['APELLIDOS Y NOMBRES'].str.contains(regex_pattern, case=False, na=False, regex=True) | 
                df_filtrado['DNI'].str.contains(regex_pattern, case=False, na=False, regex=True)
            ]
            if df_display.empty:
                df_display = df_filtrado[
                    df_filtrado['APELLIDOS Y NOMBRES'].str.contains(clean_query, case=False, na=False, regex=False) | 
                    df_filtrado['DNI'].str.contains(clean_query, case=False, na=False, regex=False)
                ]
        else:
            df_display = df_filtrado
            
        df_display_print = df_display.rename(columns=cabeceras_limpias).fillna('NAN')
        for c in df_display_print.columns:
            df_display_print[c] = df_display_print[c].astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            
        st.dataframe(df_display_print, use_container_width=True, hide_index=True)

    with tab_arquitectura:
        st.header("Sustentación y Desacoplamiento del Modelo de Datos")
        st.markdown("---")
        
        st.subheader("1. Evidencia en Primera Forma Normal (1FN)")
        df_1fn_print = df_filtrado.sample(min(5, len(df_filtrado))).rename(columns=cabeceras_limpias).fillna('NAN')
        for c in df_1fn_print.columns:
            df_1fn_print[c] = df_1fn_print[c].astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
        st.dataframe(df_1fn_print, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        st.subheader("2. Separación de Entidades en Segunda Forma Normal (2FN)")
        col_dim1, col_dim2 = st.columns(2)
        
        with col_dim1:
            st.markdown("**Dimensión Trabajador (`dim_trabajador`):**")
            dim_trabajador = df_filtrado[['DNI', 'APELLIDOS Y NOMBRES', 'CARGO', 'FECHA DE INGRESO', 'FECHA DE CESE']].drop_duplicates(subset=['DNI']).fillna('NAN')
            for c in dim_trabajador.columns:
                dim_trabajador[c] = dim_trabajador[c].astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            st.dataframe(dim_trabajador.head(5), use_container_width=True, hide_index=True)
            
            st.markdown("**Dimensión Cliente (`dim_cliente`):**")
            dim_cliente = df_filtrado[['CLIENTE', 'DIRECCION']].drop_duplicates().reset_index(drop=True)
            dim_cliente.index.name = 'id_cliente'
            dim_cliente_print = dim_cliente.reset_index().fillna('NAN')
            for c in dim_cliente_print.columns:
                dim_cliente_print[c] = dim_cliente_print[c].astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            st.dataframe(dim_cliente_print.head(5), use_container_width=True, hide_index=True)
            
        with col_dim2:
            st.markdown("**Dimensión Unidad Operativa (`dim_unidad`):**")
            dim_unidad = df_filtrado[['UNIDAD', 'SUPERVISOR', 'JORNADA', 'HORARIO', 'DESCANSO']].drop_duplicates().reset_index(drop=True)
            dim_unidad.index.name = 'id_unidad'
            dim_unidad_print = dim_unidad.reset_index().fillna('NAN')
            for c in dim_unidad_print.columns:
                dim_unidad_print[c] = dim_unidad_print[c].astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            st.dataframe(dim_unidad_print.head(5), use_container_width=True, hide_index=True)
            
        st.markdown("---")
        
        st.subheader("3. Análisis de Variación Histórica (SCD Tipo 2 Real)")
        
        cambios_operacionales = df_asistencia.groupby('DNI')[['UNIDAD', 'SUPERVISOR', 'HORARIO']].nunique()
        dnis_con_cambios = cambios_operacionales[(cambios_operacionales['UNIDAD'] > 1) | (cambios_operacionales['SUPERVISOR'] > 1) | (cambios_operacionales['HORARIO'] > 1)].index.tolist()
        
        if dnis_con_cambios:
            df_scd_real = df_asistencia[df_asistencia['DNI'].isin(dnis_con_cambios)].groupby(
                ['DNI', 'APELLIDOS Y NOMBRES', 'UNIDAD', 'SUPERVISOR', 'HORARIO']
            )['fecha_asistencia'].agg(['min', 'max']).reset_index()
            
            df_scd_real = df_scd_real.rename(columns={'min': 'Valido_Desde', 'max': 'Valido_Hasta'})
            max_fecha_global = df_asistencia['fecha_asistencia'].max()
            df_scd_real['Es_Actual'] = df_scd_real['Valido_Hasta'] == max_fecha_global
            
            df_scd_print = df_scd_real.sort_values(by=['DNI', 'Valido_Desde']).astype(str).replace(['None', 'nan', 'NaN', '<NA>', ''], 'NAN')
            st.dataframe(df_scd_print, use_container_width=True, hide_index=True)
        else:
            st.info("Nota de Arquitectura: Tras auditar el dataset limpio, ningún colaborador cambió de unidad, supervisor u horario durante este bloque de 30 días. Todos mantuvieron asignación fija.")