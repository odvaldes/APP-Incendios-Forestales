# Visor WMS SENAPRED (Amenaza Incendio 2025) – Streamlit

App Streamlit para:
- Conectarse a un servicio WMS (GetCapabilities)
- Visualizar capas en mapa (OSM/Esri)
- Dibujar y confirmar polígono
- Calcular exposición por mayoría de pixeles (clasificación por color)
- Guardar resultado + comentarios en sesión (persistente)
- Botón **Guardar print (PDF)** que abre el diálogo de impresión del navegador (equivalente a Ctrl+P)

## Ejecutar local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy en Streamlit Community Cloud
- Repo: tu repo
- Branch: main
- Main file: app.py
