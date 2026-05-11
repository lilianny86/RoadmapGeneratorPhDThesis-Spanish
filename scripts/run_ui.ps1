param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

Write-Host "[UI] Iniciando interfaz Streamlit en puerto $Port ..."
streamlit run app_streamlit.py --server.port $Port
