import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from dateutil.parser import parse

# Configuración de la página
st.set_page_config(page_title="Análisis de Ventas", page_icon="📊", layout="wide")

# Configuración de la conexión a la base de datos
DB_CONFIG = {
    "host": "34.39.128.54",
    "database": "facturador",
    "user": "postgres",
    "password": "qwerty_190421",
    "port": "5432"
}

# Función para parsear fechas
def parse_and_extract_date(date_str):
    try:
        parsed_date = parse(date_str)
        return parsed_date.date() if parsed_date else pd.NaT
    except (ValueError, TypeError, AttributeError):
        return pd.NaT

# Crear conexión SQLAlchemy
@st.cache_resource
def get_db_engine():
    try:
        connection_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        return create_engine(connection_string)
    except Exception as e:
        st.error(f"Error al conectar a la base de datos: {e}")
        return None

# Función para cargar y limpiar datos
def load_and_clean_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()
    try:
        query = """
                SELECT id, correlativo, direccion, fecha_emision, fecha_registro,
                       igv, razon_social, ruc_cliente, serie, subtotal,
                       tipo_documento, tipo_moneda, total, valor_venta
                FROM numeracion_historial
                ORDER BY fecha_emision DESC;
                """
        df = pd.read_sql(query, engine)

        # Convertir y limpiar fechas
        df['fecha_emision'] = df['fecha_emision'].apply(parse_and_extract_date)
        df = df[~df['fecha_emision'].isna()].copy()

        # Mapear tipos de documento
        doc_map = {'01': 'Factura', '03': 'Boleta'}
        df['tipo_documento'] = df['tipo_documento'].map(doc_map)

        return df

    except Exception as e:
        st.error(f"Error al procesar datos: {e}")
        return pd.DataFrame()

# Cargar datos
df = load_and_clean_data()

if df.empty:
    st.warning("No se encontraron datos válidos de ventas.")
    st.stop()

# Sidebar - Filtros
st.sidebar.header("Filtros")

# Filtro por tipo de documento
tipo_doc_options = ["Todos"] + sorted(df['tipo_documento'].dropna().unique().tolist())
selected_doc = st.sidebar.selectbox("Tipo de Documento", tipo_doc_options)

# Filtro por rango de fechas
min_date = df['fecha_emision'].min()
max_date = df['fecha_emision'].max()
date_range = st.sidebar.date_input(
    "Rango de Fechas",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

# Aplicar filtros
df_filtered = df.copy()

# Filtro por tipo de documento
if selected_doc != "Todos":
    df_filtered = df_filtered[df_filtered['tipo_documento'] == selected_doc]

# Filtro por fechas (solo si se seleccionaron 2 fechas válidas)
if len(date_range) == 2:
    try:
        mask = (df_filtered['fecha_emision'] >= date_range[0]) & (df_filtered['fecha_emision'] <= date_range[1])
        df_filtered = df_filtered[mask].copy()
    except Exception as e:
        st.error(f"Error al filtrar por fechas: {e}")
        df_filtered = pd.DataFrame()

# Página principal
st.title("📊 Análisis de Ventas")

if df_filtered.empty:
    st.warning("No hay datos que coincidan con los filtros seleccionados.")
    st.stop()

# Resumen general
st.subheader("Resumen General")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total de Ventas", f"S/. {df_filtered['total'].sum():,.2f}")
with col2:
    st.metric("Número de Transacciones", len(df_filtered))
with col3:
    avg_sale = df_filtered['total'].mean() if len(df_filtered) > 0 else 0
    st.metric("Promedio por Venta", f"S/. {avg_sale:,.2f}")

# Gráfico de ventas por día
st.subheader("Ventas por Día")
if not df_filtered.empty:
    daily_sales = df_filtered.groupby('fecha_emision')['total'].sum().reset_index()
    fig_daily = px.line(
        daily_sales,
        x='fecha_emision',
        y='total',
        title='Evolución de Ventas Diarias',
        markers=True,
        labels={'fecha_emision': 'Fecha', 'total': 'Total Ventas (S/.)'}
    )
    st.plotly_chart(fig_daily, use_container_width=True)

# Estadísticas por tipo de documento
st.subheader("Estadísticas por Tipo de Documento")
if not df_filtered.empty and 'tipo_documento' in df_filtered.columns:
    doc_stats = df_filtered.groupby('tipo_documento').agg({
        'total': ['sum', 'mean', 'count'],
        'valor_venta': 'sum'
    }).reset_index()
    doc_stats.columns = ['Tipo Documento', 'Total Ventas', 'Promedio Venta', 'Cantidad', 'Valor Venta']

    col1, col2 = st.columns(2)
    with col1:
        fig_pie = px.pie(
            doc_stats,
            names='Tipo Documento',
            values='Total Ventas',
            title='Distribución por Tipo de Documento',
            hole=0.3
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        fig_bar = px.bar(
            doc_stats,
            x='Tipo Documento',
            y='Total Ventas',
            text='Total Ventas',
            title='Ventas por Tipo de Documento',
            color='Tipo Documento'
        )
        fig_bar.update_traces(
            texttemplate='S/. %{y:,.2f}',
            textposition='outside'
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

# Top clientes
st.subheader("Top 10 Clientes por Monto Vendido")
if not df_filtered.empty:
    top_clients = df_filtered.groupby(['razon_social', 'ruc_cliente'])['total'] \
        .sum() \
        .nlargest(10) \
        .reset_index()

    fig_clients = px.bar(
        top_clients,
        x='razon_social',
        y='total',
        text='total',
        title='Clientes con Mayor Compras',
        labels={'razon_social': 'Cliente', 'total': 'Total Ventas'},
        color='total',
        color_continuous_scale='Bluered'
    )
    fig_clients.update_traces(
        texttemplate='S/. %{y:,.2f}',
        textposition='outside'
    )
    fig_clients.update_layout(
        xaxis_title='Cliente',
        yaxis_title='Total Ventas (S/.)',
        coloraxis_showscale=False
    )
    st.plotly_chart(fig_clients, use_container_width=True)

# Detalle de ventas
st.subheader("Detalle de Ventas")
if not df_filtered.empty:
    st.dataframe(
        df_filtered.sort_values('fecha_emision', ascending=False),
        column_config={
            "fecha_emision": st.column_config.DateColumn("Fecha Emisión"),
            "razon_social": "Cliente",
            "ruc_cliente": "RUC",
            "tipo_documento": "Tipo Doc",
            "total": st.column_config.NumberColumn("Total", format="S/. %.2f"),
            "valor_venta": st.column_config.NumberColumn("Valor Venta", format="S/. %.2f"),
            "igv": st.column_config.NumberColumn("IGV", format="S/. %.2f")
        },
        hide_index=True,
        use_container_width=True
    )
