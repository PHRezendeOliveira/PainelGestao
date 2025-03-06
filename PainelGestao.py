import streamlit as st
import pandas as pd
import folium
import tempfile
import os
import re
import plotly.express as px
from folium.features import DivIcon
from geopy.distance import geodesic

st.title("Painel de Gestão")

# Função para exibir ícones de ajuda com explicação
def help_icon(title, description):
    st.markdown(f'<a href="javascript:void(0)" title="{description}" style="text-decoration: none;">'
                f'<img src="https://img.icons8.com/ios-filled/50/000000/help.png" width="20" height="20" />'
                f'</a>', unsafe_allow_html=True)
    st.markdown(f'<p style="display:inline; font-size: 14px; color: gray;">{title}</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size: 12px; color: gray;">{description}</p>', unsafe_allow_html=True)


# Upload do arquivo XLSX
uploaded_file = st.file_uploader("Envie o arquivo XLSX", type=["xlsx"])

# Função para verificar o tipo de arquivo
def detectar_tipo_arquivo(df):
    if "Carimbo de data/hora" in df.columns:
        return "validacao_respostas"
    elif "data_hora_validacao" in df.columns:
        return "validacao_equipes"
    return None

# Função para corrigir as coordenadas de Latitude e Longitude
def corrigir_lat_long(lat, long):
    try:
        return float(lat.replace(",", ".")), float(long.replace(",", "."))
    except ValueError:
        return None, None

# Função para gerar o mapa
def gerar_mapa(df_filtered, title, color, icon_color):
    if not df_filtered.empty:
        map_center = [df_filtered["Latitude"].mean(), df_filtered["Longitude"].mean()]
        m = folium.Map(
            location=map_center,
            zoom_start=12,
            tiles="Esri.WorldImagery",  # Usando ESRI World Imagery
            attr="Map tiles by Esri, DeLorme, NAVTEQ"
        )

        # Adicionando os marcadores individualmente
        for idx, row in df_filtered.iterrows():
            if tipo_arquivo == "validacao_equipes":
                # Usando 'desc_equipe' para validacao_equipes
                verificador = row['desc_equipe']
            else:
                # Usando 'Verificador' para validacao_respostas
                verificador = row['Verificador']
            
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=f"{title} {idx+1}: {verificador} - {row['Data']}<br>Tempo: {row['Diff']:.2f} min",
                icon=DivIcon(
                    icon_size=(30, 30),
                    icon_anchor=(15, 15),
                    html=f'<div style="font-size: 12pt; color: white; background-color: {icon_color}; border-radius: 50%; text-align: center; line-height: 30px;">{idx+1}</div>'
                )
            ).add_to(m)

        # Adicionando setas para indicar a sequência com cores diferentes
        for i in range(1, len(df_filtered)):
            start = df_filtered.iloc[i - 1]
            end = df_filtered.iloc[i]
            dist = geodesic((start["Latitude"], start["Longitude"]), (end["Latitude"], end["Longitude"])).meters
            if dist < 10:  # Distância menor que 10 metros
                line_color = "darkgreen"
            elif dist < 30:  # Distância entre 10m e 30m
                line_color = "darkorange"
            else:
                line_color = "darkred"
            
            folium.PolyLine([[start["Latitude"], start["Longitude"]], [end["Latitude"], end["Longitude"]]], color=line_color, weight=4, opacity=0.7).add_to(m)

        # Salvando o mapa em um local controlado
        map_filename = "mapa.html"
        m.save(map_filename)
        with open(map_filename, "r", encoding="utf-8") as f:
            map_data = f.read()
            st.components.v1.html(map_data, height=800, width=1200)  # Exibindo em tela cheia (ajustando a altura e largura)

        # Botão para download do mapa
        st.download_button(label="Baixar mapa", data=map_data, file_name=map_filename, mime="text/html")
        os.remove(map_filename)

# Processamento do arquivo
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    tipo_arquivo = detectar_tipo_arquivo(df)

    if tipo_arquivo == "validacao_respostas":
        st.subheader("Painel de Respostas por Verificador")
        help_icon("Painel de Respostas", "Aqui você pode visualizar as respostas por verificador e analisar a diferença de tempo entre elas.")

        df["Carimbo de data/hora"] = pd.to_datetime(df["Carimbo de data/hora"], errors="coerce")
        df["Data"] = df["Carimbo de data/hora"].dt.date
        df["Hora"] = df["Carimbo de data/hora"].dt.time
        df = df.sort_values(["Verificador", "Carimbo de data/hora"])

        verificadores = df["Verificador"].unique()
        selected_verificador = st.selectbox("Selecione um verificador", verificadores)
        help_icon("Selecionar Verificador", "Escolha um verificador para visualizar as respostas relacionadas a ele.")
        
        selected_dates = st.multiselect("Selecione as datas", options=sorted(df["Data"].unique()), default=sorted(df["Data"].unique()))
        help_icon("Selecionar Datas", "Escolha as datas para filtrar as respostas.")

        # Slider para filtrar por intervalo de tempo
        time_slider = st.slider("Selecione o intervalo de tempo (minutos)", min_value=0, max_value=120, step=5, value=(0, 60))
        help_icon("Intervalo de Tempo", "Use este filtro para selecionar um intervalo de tempo entre as respostas.")

        df_filtered = df[(df["Verificador"] == selected_verificador) & (df["Data"].isin(selected_dates))]
        df_filtered["Diff"] = df_filtered["Carimbo de data/hora"].diff().dt.total_seconds() / 60
        df_filtered["Diff"].fillna(0, inplace=True)
        df_filtered.loc[df_filtered["Diff"] < 0.01, "Diff"] = 0

        # Filtro pelo intervalo de tempo selecionado
        df_filtered = df_filtered[(df_filtered["Diff"] >= time_slider[0]) & (df_filtered["Diff"] <= time_slider[1])]

        st.write(f"Total de respostas: {len(df_filtered)}")
        st.write(f"Tempo médio entre respostas: {df_filtered['Diff'].mean():.2f} minutos")
        st.write(f"Desvio padrão: {df_filtered['Diff'].std():.2f} minutos")

        # Gráficos
        fig_bar = px.bar(df_filtered, x="Carimbo de data/hora", y="Diff", title="Diferença de Tempo entre Respostas")
        st.plotly_chart(fig_bar)

        fig_scatter = px.scatter(df_filtered, x="Carimbo de data/hora", y="Diff", title="Distribuição de Tempo entre Respostas")
        st.plotly_chart(fig_scatter)

        st.subheader("Tabela de Respostas")
        st.dataframe(df_filtered)

        if st.button("Mapa"):
            if "Localização Georeferencial" in df.columns:
                regex_pattern = r"EPSG:4326:\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)"
                df_filtered["Latitude"] = df_filtered["Localização Georeferencial"].apply(lambda x: float(re.search(regex_pattern, str(x)).group(2)) if re.search(regex_pattern, str(x)) else None)
                df_filtered["Longitude"] = df_filtered["Localização Georeferencial"].apply(lambda x: float(re.search(regex_pattern, str(x)).group(1)) if re.search(regex_pattern, str(x)) else None)
                df_filtered.dropna(subset=["Latitude", "Longitude"], inplace=True)
                gerar_mapa(df_filtered, "Envio", "red", "red")

    elif tipo_arquivo == "validacao_equipes":
        st.subheader("Painel de Gestão das Equipes CCO")
        help_icon("Painel de Equipes", "Aqui você pode visualizar o desempenho das equipes e a diferença de tempo entre as validações realizadas.")

        df["data_hora_validacao"] = pd.to_datetime(df["data_hora_validacao"], errors="coerce")
        df["Data"] = df["data_hora_validacao"].dt.date
        df["Hora"] = df["data_hora_validacao"].dt.time
        df = df.sort_values(["desc_equipe", "data_hora_validacao"])

        equipes = df["desc_equipe"].unique()
        selected_equipe = st.selectbox("Selecione uma Equipe", equipes)
        help_icon("Selecionar Equipe", "Escolha a equipe para visualizar as validações relacionadas a ela.")

        selected_dates = st.multiselect("Selecione as datas", options=sorted(df[df["desc_equipe"] == selected_equipe]["Data"].unique()), default=sorted(df[df["desc_equipe"] == selected_equipe]["Data"].unique()))
        help_icon("Selecionar Datas", "Escolha as datas para filtrar as validações.")

        df_filtered = df[(df["desc_equipe"] == selected_equipe) & (df["Data"].isin(selected_dates))]
        df_filtered["Diff"] = df_filtered["data_hora_validacao"].diff().dt.total_seconds() / 60
        df_filtered["Diff"].fillna(0, inplace=True)
        df_filtered.loc[df_filtered["Diff"] < 0.01, "Diff"] = 0

        st.write(f"Total de validações: {len(df_filtered)}")
        st.write(f"Tempo médio entre validações: {df_filtered['Diff'].mean():.2f} minutos")
        st.write(f"Desvio padrão: {df_filtered['Diff'].std():.2f} minutos")

        # Gráficos
        fig_bar = px.bar(df_filtered, x="data_hora_validacao", y="Diff", title="Diferença de Tempo entre Validações")
        st.plotly_chart(fig_bar)

        fig_scatter = px.scatter(df_filtered, x="data_hora_validacao", y="Diff", title="Distribuição de Tempo entre Validações")
        st.plotly_chart(fig_scatter)

        st.subheader("Tabela de Validações")
        st.dataframe(df_filtered)

        if st.button("Mapa"):
            # Usando diretamente as colunas Latitude e Longitude
            df_filtered.dropna(subset=["Latitude", "Longitude"], inplace=True)
            gerar_mapa(df_filtered, "Envio", "blue", "blue")
