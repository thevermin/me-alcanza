# La calculadora del bolsillo

Herramientas gratuitas con datos oficiales del INDEC:

- **¿Le ganó tu sueldo a la inflación?** Compará tu sueldo de antes y de ahora.
- **Actualizar un monto.** Cuánto vale hoy un monto de otra fecha.
- **Mi inflación.** Tu inflación personal según en qué gastás.
- **El dato del mes.** La última inflación, explicada simple y lista para compartir.

Funciona en el navegador del celular o la computadora y se puede instalar como app ("Agregar a pantalla de inicio").

## Cómo publicarla gratis en GitHub Pages

1. Creá un repositorio público nuevo (por ejemplo `calculadora-bolsillo`) y subí todos estos archivos, incluida la carpeta oculta `.github`.
2. En el repositorio: **Settings → Pages → Source: Deploy from a branch → `main` / `(root)`** y guardá. En un par de minutos queda en `https://TU-USUARIO.github.io/calculadora-bolsillo/`.
3. En **Settings → Actions → General → Workflow permissions** elegí **Read and write permissions**, para que la actualización automática pueda guardar los datos nuevos.
4. En la pestaña **Actions**, abrí "Actualizar datos del INDEC" y tocá **Run workflow** una vez para probarlo.

Desde ahí, GitHub revisa todos los días si hay datos nuevos y actualiza la página solo. No hay servidores ni costos.

## Archivos

| Archivo | Para qué sirve |
| --- | --- |
| `pagina.html` | La página (diseño y cálculos). Se edita acá. |
| `index.html` | Se arma solo a partir de `pagina.html` con `scripts/armar_index.py`. |
| `data/datos.json` | Datos del IPC (nacional, por región y por rubro) y del índice de salarios. |
| `scripts/actualizar_datos.py` | Descarga los datos (API del INDEC si hay token; si no, datos.gob.ar). |
| `scripts/indec_api.py` | Conexión con la API del INDEC. |
| `pagina-ambar.html` | Variante de color ámbar. Para usarla, renombrala a `pagina.html`. |
| `.github/workflows/actualizar.yml` | Corre la descarga todos los días. |
| `manifest.webmanifest`, `icon.svg`, `sw.js` | Hacen que se pueda instalar como app y abrir sin conexión. |

Para probar en tu compu: `python3 scripts/actualizar_datos.py && python3 scripts/armar_index.py && python3 -m http.server` y abrí `http://localhost:8000`.

## Conectar la API del INDEC (token)

El token nunca va dentro del código ni se pega en un chat: se guarda como secreto de GitHub.

1. En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
2. Nombre: `INDEC_API_TOKEN`. Valor: tu token. Guardá.
3. En **Actions → Actualizar datos del INDEC → Run workflow**.
4. Abrí la ejecución y mirá el paso "Descargar datos". Si dice **"Usando la API del INDEC"**, listo. Si dice que se usa datos.gob.ar, el mensaje explica por qué, y la página sigue funcionando igual.

El script compara la API del INDEC con datos.gob.ar en los meses que tienen en común antes de usarla, y deja en `data/indec_resumen.json` qué regiones y rubros encontró (sin ningún dato tuyo). El token vence a los 12 meses: cuando lo regeneres en el INDEC, actualizá el secreto.

## Ingresos sin cobrar la página

Todo se configura en el bloque `CONFIG` al principio del script de `pagina.html`:

- `cafecito`: tu usuario de Cafecito. Aparece un aviso discreto en el pie de página.
- `adsenseCliente` y `adsenseBloque`: los códigos de Google AdSense. Aparece un solo anuncio debajo de la calculadora.
- `espacioDePrueba`: ponelo en `false` cuando publiques sin AdSense, así no se ve el recuadro vacío.

Para AdSense hace falta un dominio propio (los sitios en `github.io` suelen ser rechazados) y un archivo `ads.txt` en la raíz con la línea que te da AdSense. Después de editar `pagina.html`, corré `python3 scripts/armar_index.py`.

## Fuente y aviso

Fuente: INDEC. Las cuentas son una referencia informativa y no constituyen asesoramiento financiero, legal ni contable.
