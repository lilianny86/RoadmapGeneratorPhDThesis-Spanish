# RoadmapGenerator

Framework para capturar datos de empresa, procesar cuestionarios y generar roadmaps tecnológicos para PyMEs agrícolas.

## Código seudonimizado estable para estadísticas

Para relacionar mediciones sucesivas de una misma empresa sin incluir su nombre, RUT ni correo en los CSV, configure una clave privada en los Secrets locales y de Streamlit:

```toml
ROADMAP_PARTICIPANT_SALT = "clave-privada-larga-y-aleatoria"
```

RoGen deriva el código estable a partir del RUT normalizado mediante HMAC-SHA256. La clave no debe subirse a Git ni cambiarse mientras existan datos del estudio, ya que un cambio produciría códigos distintos para la misma empresa.


