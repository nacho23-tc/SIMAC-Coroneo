## Celda 0 (markdown)

# De medir granos a predecir el rendimiento
**Track Talents · Sesión 3 (segmentación con red neuronal)**

La sesión pasada terminaste con una tabla: una fila por grano, con sus medidas
en milímetros. En el reto 3 la resumiste en una fila por muestra y quedó una
pregunta abierta: con muchas imágenes, ¿lo que se mide en los granos dice algo
de la mazorca de donde salieron?

Hoy lo ponemos a prueba. Con 19 familias de maíz, el cuaderno va a **predecir si
una familia es de rendimiento Alto o Bajo** usando lo que se mide en su imagen y
tres datos de su mazorca. De cuatro familias no conocerá la respuesta: con ellas
se le examina, y el resultado se resume en una **tabla de confusión**.

**Este es el mismo cuaderno de la semana pasada, con más pasos abajo:**

| Pasos | Qué hacen | Qué entregan |
|---|---|---|
| 1 a 11 | De la imagen a la tabla de granos. Lo único nuevo: el recorte del paso 4 ahora lo hace el cuaderno | Imagen numerada y tabla de granos |
| 12 a 15 | La unión grano a grano de la sesión pasada. **Hoy no se usan** | — |
| 16 a 19 | Promedio por familia y lote de imágenes | **Excel 1:** `caracteristicas_por_familia.xlsx` |
| 20 a 26 | Clasificación: unir, normalizar, elegir entradas, entrenar y examinar | **Excel 2:** `clasificacion_rendimiento.xlsx` y la tabla de confusión |

**Dos formas de trabajar hoy:**

- **Con imágenes:** ejecuta las celdas en orden con `Shift + Enter`.
- **Con los dos Excel ya hechos:** ve directo al paso 20. Esa parte funciona
  sola: no necesita instalar la red ni activar la GPU.

Los pasos 13, 14 y 16 muestran su código completo; en los demás, el código
aparece con doble clic sobre la celda.

**Antes de empezar:**
1. Ve a *Archivo → Guardar una copia en Drive*.
2. Si vas a trabajar con imágenes, ve a *Entorno de ejecución → Cambiar tipo de
   entorno de ejecución* y elige **T4 GPU**.

## Celda 1 (markdown)

## Paso 1. Instalar la red

Colab no trae Cellpose instalado, así que hay que descargarlo. Tarda entre dos y
cuatro minutos y solo se hace una vez por sesión.

**Si al terminar aparece un botón que dice "RESTART SESSION"**, presiónalo,
espera a que se reinicie y continúa desde el paso 2. No vuelvas a ejecutar esta
celda.

## Celda 2 (code)

!pip install -q cellpose==3.1.1.2

print("Instalación terminada. Si apareció el botón RESTART SESSION, presiónalo.")

## Celda 3 (markdown)

## Paso 2. Preparar las herramientas

- **cellpose**: la red que separa los objetos.
- **skimage**, **numpy**: manejo de imágenes y medidas.
- **matplotlib**: dibujar.

## Celda 4 (code)

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from skimage import io, color, measure, transform, util
import torch
from cellpose import models

HAY_GPU = torch.cuda.is_available()
print("Cellpose listo.  GPU disponible:", HAY_GPU)
if not HAY_GPU:
    print("Sin GPU la segmentación tarda varios minutos. Puedes activarla en")
    print("Entorno de ejecución -> Cambiar tipo de entorno de ejecución -> T4 GPU")

## Celda 5 (markdown)

## Paso 3. Subir tu imagen

Al ejecutar aparecerá un botón para elegir el archivo. Sube **una sola imagen**
de granos de maíz blanco, con fondo oscuro y sin granos encimados.

## Celda 6 (code)

from google.colab import files

subidos = files.upload()
RUTA = list(subidos.keys())[0]

original = io.imread(RUTA)
if original.ndim == 3 and original.shape[2] == 4:
    original = original[:, :, :3]

print("Archivo:", RUTA)
print("Tamaño en píxeles (alto, ancho):", original.shape[0], original.shape[1])

plt.figure(figsize=(10, 8))
plt.imshow(original)
plt.title("Imagen original")
plt.axis("off")
plt.show()

## Celda 7 (markdown)

## Paso 4. Recortar la zona de los granos

La red debe ver granos, no la regla ni la etiqueta ni el borde de la charola. En
las sesiones pasadas ese recorte se hacía a mano, probando números. Ahora lo
hace el cuaderno, en tres movimientos:

1. **Separa lo claro del fondo.** El fondo negro es lo que más abunda en la
   imagen; todo lo que brilla claramente más que él es "algo".
2. **Decide qué es grano por tamaño y por forma.** Los granos son muchos objetos
   compactos de tamaño parecido. La regla es demasiado alargada, la etiqueta
   demasiado grande y el polvo demasiado chico.
3. **Recorta el rectángulo que contiene a todos los granos,** con medio grano de
   margen y sin pasar por encima de la regla ni de la etiqueta.

**Qué debe aparecer:** a la izquierda, tu imagen con un recuadro verde; a la
derecha, la zona recortada. Revisa dos cosas: que **ningún grano quede fuera**
del recuadro, y que la regla y la etiqueta sí queden fuera.

**Si el recuadro se equivoca,** fíjalo a mano: en `RECORTE` escribe cuatro
fracciones entre 0 y 1, `(izquierda, arriba, derecha, abajo)`. Por ejemplo,
`(0.1, 0.1, 0.9, 0.7)` conserva desde el 10 % hasta el 90 % del ancho y desde el
10 % hasta el 70 % del alto. Con `None` vuelve a ser automático.

## Celda 8 (code)

#@title ▶ Recortar la zona de los granos
RECORTE = None  #@param {type:"raw"}
#@markdown `None` = el cuaderno encuentra la zona. Para fijarla a mano:
#@markdown `(izquierda, arriba, derecha, abajo)`, cuatro fracciones entre 0 y 1.


def recorte_automatico(imagen):
    """Rectángulo que contiene los granos, como (x0, y0, x1, y1) en fracciones
    de la imagen. Devuelve None si no logra reconocerlos."""
    # 1. Miniatura: para ubicar los granos no hace falta todo el detalle
    salto = max(1, max(imagen.shape[:2]) // 1200)
    chica = util.img_as_float(imagen[::salto, ::salto])
    brillo = chica.max(axis=2) if chica.ndim == 3 else chica   # claro en cualquier color de grano

    # 2. Lo claro: lo que supera con holgura al fondo (el fondo es la mediana)
    fondo = np.median(brillo)
    ruido = 1.4826 * np.median(np.abs(brillo - fondo))
    etiquetas = measure.label(brillo > fondo + max(0.12, 6 * ruido))
    objetos = measure.regionprops(etiquetas)

    def alargamiento(o):
        return o.axis_major_length / max(o.axis_minor_length, 1e-9)

    # 3. Tamaño típico de un grano: el grupo de objetos compactos y parecidos entre sí
    #    (al menos 5, áreas dentro de un factor 4) que suma más área
    polvo = 0.00002 * brillo.size
    areas = np.sort([o.area for o in objetos
                     if o.area >= polvo and alargamiento(o) <= 3 and o.solidity >= 0.8])
    if len(areas) < 5:
        return None
    desde = np.arange(len(areas))
    hasta = np.searchsorted(areas, 4 * areas, side="left")
    acumulada = np.concatenate([[0], np.cumsum(areas)])
    suma = np.where(hasta - desde >= 5, acumulada[hasta] - acumulada[desde], 0)
    if suma.max() == 0:
        return None
    mejor = int(np.argmax(suma))
    tipica = np.median(areas[mejor:hasta[mejor]])

    # 4. Granos o grupos de granos pegados (de 1/4 a 4 veces el área típica, no muy
    #    alargados) y estorbos (todo lo demás de ese tamaño o mayor: regla, etiqueta, bordes)
    medianos = [o for o in objetos if o.area >= tipica / 4]
    granos_vistos = [o for o in medianos if o.area <= 4 * tipica and alargamiento(o) <= 4]
    numeros = {o.label for o in granos_vistos}
    estorbos = np.isin(etiquetas, [o.label for o in medianos if o.label not in numeros])

    # 5. Caja que contiene todos los granos
    fila0 = min(o.bbox[0] for o in granos_vistos)
    col0 = min(o.bbox[1] for o in granos_vistos)
    fila1 = max(o.bbox[2] for o in granos_vistos)
    col1 = max(o.bbox[3] for o in granos_vistos)

    # 6. Margen de medio grano por lado, deteniéndose antes de tocar un estorbo
    margen = int(round(0.5 * np.sqrt(4 * tipica / np.pi)))

    def libre(franja):
        """Cuántas líneas se puede crecer; la franja va ordenada de la caja hacia afuera."""
        ocupadas = franja.any(axis=1)
        return int(np.argmax(ocupadas)) if ocupadas.any() else len(ocupadas)

    arriba = libre(estorbos[max(fila0 - margen, 0):fila0, col0:col1][::-1])
    abajo = libre(estorbos[fila1:fila1 + margen, col0:col1])
    izquierda = libre(estorbos[fila0:fila1, max(col0 - margen, 0):col0].T[::-1])
    derecha = libre(estorbos[fila0:fila1, col1:col1 + margen].T)

    filas, columnas = brillo.shape
    return (round(float((col0 - izquierda) / columnas), 4),
            round(float((fila0 - arriba) / filas), 4),
            round(float((col1 + derecha) / columnas), 4),
            round(float((fila1 + abajo) / filas), 4))


def zona_de_recorte(imagen):
    """Las cuatro fracciones que se usarán con esta imagen, y de dónde salieron."""
    if RECORTE is not None:
        return tuple(RECORTE), "a mano"
    calculado = recorte_automatico(imagen)
    if calculado is None:
        return (0.0, 0.0, 1.0, 1.0), "imagen completa"
    return calculado, "automático"


alto, ancho = original.shape[:2]
(x0, y0, x1, y1), ORIGEN_RECORTE = zona_de_recorte(original)
recorte = original[int(y0 * alto):int(y1 * alto), int(x0 * ancho):int(x1 * ancho)]

if ORIGEN_RECORTE == "imagen completa":
    print("⚠️  No reconocí los granos, así que se usa la imagen completa.")
    print("    Fija el recorte a mano en RECORTE, por ejemplo (0.1, 0.1, 0.9, 0.7).")
print(f"Recorte ({ORIGEN_RECORTE}): del {x0:.1%} al {x1:.1%} del ancho "
      f"y del {y0:.1%} al {y1:.1%} del alto")
print("Recorte:", recorte.shape[0], "x", recorte.shape[1], "píxeles")

fig, (ax_completa, ax_recorte) = plt.subplots(1, 2, figsize=(15, 6))
ax_completa.imshow(original)
ax_completa.add_patch(plt.Rectangle((x0 * ancho, y0 * alto), (x1 - x0) * ancho, (y1 - y0) * alto,
                                    fill=False, edgecolor="lime", linewidth=2.5))
ax_completa.set_title("Imagen completa: el recuadro es lo que se conserva")
ax_completa.axis("off")
ax_recorte.imshow(recorte)
ax_recorte.set_title("Zona que verá la red")
ax_recorte.axis("off")
plt.show()

## Celda 9 (markdown)

## Paso 5. Preparar lo que verá la red

Tres decisiones, las mismas del proyecto de investigación:

- **Reducir el tamaño.** Una imagen de escáner es enorme y la red no necesita
  tanto detalle. Reducir a la cuarta parte acelera el proceso sin perder los
  bordes del grano.
- **Pasar a escala de grises.** La red trabaja con un solo canal.
- **Invertir el contraste.** Cellpose fue entrenada con células claras sobre
  fondo oscuro. Si tus granos son claros y el fondo es oscuro, **no** hace falta
  invertir. Si tienes granos oscuros sobre fondo claro, sí.

La imagen que aparece abajo es exactamente lo que recibe la red. Si a ti te
cuesta distinguir los granos ahí, a la red también.

## Celda 10 (code)

REDUCCION = 4          # 1 = tamaño original, 4 = la cuarta parte
INVERTIR = False       # True si los granos son oscuros sobre fondo claro

gris = color.rgb2gray(recorte)
if REDUCCION > 1:
    gris = transform.rescale(gris, 1 / REDUCCION, anti_aliasing=True)
    vista = transform.rescale(recorte, 1 / REDUCCION, anti_aliasing=True, channel_axis=2)
else:
    vista = recorte / 255.0

entrada_red = util.invert(gris) if INVERTIR else gris

print("Tamaño que verá la red:", entrada_red.shape)

plt.figure(figsize=(10, 8))
plt.imshow(entrada_red, cmap="gray")
plt.title("Entrada a la red")
plt.axis("off")
plt.show()

## Celda 11 (markdown)

## Paso 6. Segmentar con la red

Aquí trabaja Cellpose. El parámetro que más importa es el **diámetro**: el
tamaño típico, en píxeles, que la red debe esperar de cada objeto.

- `DIAMETRO = None` deja que la red lo estime sola.
- Un número lo fija a mano.

**Es el parámetro que decide todo.** Si la red espera objetos mucho más chicos
que los granos reales, parte cada grano en pedazos; si los espera mucho más
grandes, une varios en uno.

**Cómo estimarlo:** mira la imagen del paso 5, calcula cuántos píxeles de ancho
tiene un grano típico y usa ese número. Recuerda que la imagen ya está reducida:
si en el original un grano mide 340 píxeles y redujiste a la cuarta parte, el
diámetro es 85.

La primera vez, la red descarga sus pesos; eso tarda un minuto extra.

## Celda 12 (code)

DIAMETRO = None              # None = la red lo estima; o un número en píxeles
FLOW_THRESHOLD = 0.4         # qué tan estricta es con la forma de los objetos
CELLPROB_THRESHOLD = 0.0     # qué tan segura debe estar de que algo es un objeto

modelo = models.Cellpose(gpu=HAY_GPU, model_type="cyto3")

mascaras, flujos, estilos, diametros = modelo.eval(
    entrada_red,
    diameter=DIAMETRO,
    channels=[0, 0],
    flow_threshold=FLOW_THRESHOLD,
    cellprob_threshold=CELLPROB_THRESHOLD,
)

print("Diámetro usado:", round(float(np.ravel(diametros)[0]), 1), "píxeles")
print("Objetos que entregó la red:", int(mascaras.max()))

plt.figure(figsize=(10, 8))
plt.imshow(mascaras, cmap="nipy_spectral")
plt.title(f"{int(mascaras.max())} objetos, cada uno de un color")
plt.axis("off")
plt.show()

## Celda 13 (markdown)

## Paso 7. Filtrar por geometría

La red entrega objetos; nosotros decidimos cuáles son granos. Se descartan por
tres criterios, los mismos del proyecto:

- **Demasiado pequeños:** fragmentos, polvo, reflejos.
- **Demasiado grandes:** dos granos unidos, o algo que no era un grano.
- **Demasiado alargados:** un grano tiene una proporción largo/ancho moderada;
  una sombra o una franja, no.

Si descarta granos buenos, baja `AREA_MINIMA` o sube `ELONGACION_MAXIMA`.

**Cómo elegir `AREA_MINIMA`:** un grano ocupa aproximadamente el 70 % de un
cuadrado de lado igual al diámetro. Con un diámetro de 85 píxeles, el área ronda
los 5000; usa la mitad como mínimo. Si tu imagen es pequeña o la redujiste
mucho, ese número baja: fíjate en los tamaños que imprime la celda.

## Celda 14 (code)

AREA_MINIMA = 1500          # píxeles (en la imagen reducida)
AREA_MAXIMA = 20000        # píxeles
ELONGACION_MAXIMA = 3.0    # largo dividido entre ancho

objetos = measure.regionprops(mascaras)

def elongacion(p):
    return p.axis_major_length / p.axis_minor_length if p.axis_minor_length > 0 else 99

granos, descartados = [], []
for p in objetos:
    if AREA_MINIMA <= p.area <= AREA_MAXIMA and elongacion(p) <= ELONGACION_MAXIMA:
        granos.append(p)
    else:
        descartados.append(p)

print("Objetos de la red:", len(objetos))
print("Granos aceptados: ", len(granos))
print("Descartados:      ", len(descartados))
for p in descartados[:10]:
    print(f"   área={int(p.area):6d}   largo/ancho={elongacion(p):.1f}")
if len(descartados) > 10:
    print(f"   ... y {len(descartados) - 10} más")
if granos:
    areas = sorted(int(p.area) for p in granos)
    print("Área de los granos aceptados: de", areas[0], "a", areas[-1], "píxeles")

## Celda 15 (markdown)

## Paso 8. Marcar y numerar cada grano

Los ordenamos como se lee, de arriba hacia abajo y de izquierda a derecha, y le
ponemos a cada uno una cruz roja con su número.

**Esta imagen es tu resultado.** Cuenta los granos a ojo y compara con el número
que dio la red.

## Celda 16 (code)

FILA = 60     # alto aproximado de una fila de granos, en píxeles de la imagen reducida

granos_ordenados = sorted(granos, key=lambda p: (round(p.centroid[0] / FILA), p.centroid[1]))

fig, ax = plt.subplots(figsize=(12, 9))
ax.imshow(vista)
for numero, p in enumerate(granos_ordenados, start=1):
    y, x = p.centroid
    ax.plot(x, y, marker="+", color="red", markersize=12, markeredgewidth=2)
    t = ax.text(x + 10, y - 10, str(numero), color="red", fontsize=9, weight="bold")
    t.set_path_effects([pe.withStroke(linewidth=2.5, foreground="white")])

ax.set_title(f"{len(granos_ordenados)} granos detectados")
ax.axis("off")
plt.show()

fig.savefig("resultado.png", dpi=130, bbox_inches="tight")
print("Imagen guardada como resultado.png")

## Celda 17 (markdown)

## Paso 9. Descargar tu resultado

Sube la imagen al documento compartido del grupo, junto con el número de granos
que contó la red y el que contaste tú.

## Celda 18 (code)

files.download("resultado.png")

## Celda 19 (markdown)

## Seguimos desde aquí
Si ya tienes tu imagen segmentada y numerada arriba, `granos_ordenados` es la
lista de granos en orden y `mascaras` es la imagen donde cada grano tiene su
propio número de región. Vamos a usar exactamente esas variables para medir y
armar la tabla.

## Celda 20 (markdown)

## Paso 10. De píxeles a milímetros
Los números de `p.area` y `p.axis_major_length` salen en píxeles de la imagen
**ya reducida** (recuerda `REDUCCION` del paso 5). Para llegar a milímetros
reales hacen falta dos cosas:

1. **La resolución del escaneo** (DPI: puntos por pulgada). Una pulgada mide
   25.4 mm.
2. **Deshacer la reducción:** si redujiste a la cuarta parte, cada píxel de
   trabajo vale 4 píxeles del original.

Por eso la escala final se multiplica por `REDUCCION`, no solo por los DPI.

## Celda 21 (code)

#@title ▶ Calcular la escala
DPI = 1200  #@param {type:"integer"}

MM_POR_PX_ORIGINAL = 25.4 / DPI
MM_POR_PX = MM_POR_PX_ORIGINAL * REDUCCION      # deshace la reducción del paso 5

print(f"Resolución: {DPI} DPI  ·  reducción usada: 1/{REDUCCION}")
print(f"Un píxel de la imagen de trabajo mide {MM_POR_PX * 1000:.1f} micras")
print(f"Un milímetro real son {1 / MM_POR_PX:.1f} píxeles de trabajo")

## Celda 22 (markdown)

## Paso 11. Medir cada grano
Cada grano de `granos_ordenados` ya trae medidas calculadas por `skimage` desde
el paso 7. Hoy las convertimos a milímetros, agregamos color (tomado de `vista`,
la imagen que ya tenías preparada) y las juntamos en una tabla, una fila por
grano:

| Columna | De dónde sale |
|---|---|
| `largo_mm`, `ancho_mm` | `p.axis_major_length`, `p.axis_minor_length` × la escala |
| `area_mm2` | `p.area` × la escala al cuadrado (el área es de dos dimensiones) |
| `perimetro_mm` | `p.perimeter` × la escala |
| `razon_aspecto` | largo entre ancho: 1 es redondo, más es alargado |
| `circularidad` | qué tan parecido es a un círculo, de 0 a 1 |
| `solidez` | qué tan "lleno" está su contorno |
| `L`, `a`, `b` | color del grano: luminosidad, eje verde–rojo, eje azul–amarillo |

Usamos **pandas**, una librería para trabajar con tablas dentro de Python.

## Celda 23 (code)

#@title ▶ Medir
import pandas as pd

lab = color.rgb2lab(vista)

filas_tabla = []
for numero, p in enumerate(granos_ordenados, start=1):
    dentro = mascaras == p.label
    filas_tabla.append({
        "imagen": RUTA,
        "grano": numero,
        "largo_mm": p.axis_major_length * MM_POR_PX,
        "ancho_mm": p.axis_minor_length * MM_POR_PX,
        "area_mm2": p.area * MM_POR_PX ** 2,
        "perimetro_mm": p.perimeter * MM_POR_PX,
        "razon_aspecto": p.axis_major_length / p.axis_minor_length,
        "circularidad": 4 * np.pi * p.area / p.perimeter ** 2 if p.perimeter > 0 else np.nan,
        "solidez": p.solidity,
        "L": lab[..., 0][dentro].mean(),
        "a": lab[..., 1][dentro].mean(),
        "b": lab[..., 2][dentro].mean(),
    })
caracteristicas = pd.DataFrame(filas_tabla).round(3)

print(f"Tabla de características: {len(caracteristicas)} filas (granos) × "
      f"{caracteristicas.shape[1]} columnas")
display(caracteristicas.head(8))

## Celda 24 (markdown)

> **Hoy puedes saltar los pasos 12 a 15.** Son la unión grano a grano de la
> sesión pasada y piden el archivo de metadatos de esa sesión. Lo de hoy
> continúa en el paso 16.

## Celda 25 (markdown)

## Paso 12. Subir los metadatos
Los **metadatos** son la información de cada mazorca que no sale de la imagen:
su peso, cuántos días tardó en florecer, qué altura alcanzó la planta. Vienen en
otro archivo (CSV o Excel), con **una fila por muestra** (no por grano).

Fíjate en la columna que identifica cada muestra y en cómo está escrito cada
identificador: lo vas a necesitar en el paso siguiente.

## Celda 26 (code)

#@title ▶ Subir metadatos
subidos_meta = files.upload()
RUTA_META = list(subidos_meta.keys())[0]
from io import StringIO     # no confundir con io de skimage

if RUTA_META.lower().endswith((".xlsx", ".xls")):
    metadatos = pd.read_excel(RUTA_META)
elif RUTA_META.lower().endswith(".csv"):
    crudo = open(RUTA_META, "rb").read()
    try:
        texto = crudo.decode("utf-8-sig")       # CSV guardado como UTF-8
    except UnicodeDecodeError:
        texto = crudo.decode("latin-1")         # CSV guardado por Excel en Windows
    excel_es = ";" in texto.splitlines()[0]     # Excel en español: ";" y coma decimal
    metadatos = pd.read_csv(StringIO(texto),
                            sep=";" if excel_es else ",",
                            decimal="," if excel_es else ".")
else:
    raise ValueError(f"No sé leer '{RUTA_META}'. Sube los metadatos como .csv o .xlsx.")

print(f"Metadatos: {len(metadatos)} muestras × {metadatos.shape[1]} columnas")
print("Columnas:", list(metadatos.columns))
display(metadatos.head(5))

## Celda 27 (markdown)

## Paso 13. Construir la llave
Para unir dos tablas hace falta una **llave**: un texto que aparezca igual en
las dos. Aquí hay un problema típico: tu imagen se llama algo como
`Grano_06.jpg`, pero si la subes dos veces Colab la guarda como
`Grano_06 (1).jpg`; en los metadatos, esa misma muestra aparece en la columna
`nombre_nuevo` como `Grano_06.jpg`. Para la computadora, esos dos textos son
distintos.

Ojo con los nombres: **`Grano_06` es la muestra** (la imagen completa, una
mazorca), mientras que la columna `grano` de tu tabla es el número de cada grano
**dentro** de esa imagen.

La solución es **extraer de ambos lados solo la parte que sí coincide**. El
patrón `GRANO_\d+` significa "la palabra GRANO, un guion bajo y uno o más
dígitos". Va en mayúsculas porque la función convierte todo a mayúsculas antes
de buscar.

Este código se muestra completo: es la idea central de hoy.

## Celda 28 (code)

import re

COLUMNA_ID = "nombre_imagen"  # columna de los metadatos que identifica la muestra
PATRON = r"GRANO_\d+"       # la parte del texto que coincide en ambas tablas

def llave(texto):
    """Extrae el identificador común; si no lo encuentra, devuelve None."""
    hallado = re.search(PATRON, str(texto).upper())
    return hallado.group(0) if hallado else None

caracteristicas["llave"] = caracteristicas["imagen"].map(llave)
metadatos["llave"] = metadatos[COLUMNA_ID].map(llave)

propia = caracteristicas["llave"].iloc[0]
print("Llave de tu imagen:    ", propia)
print("Ejemplos en metadatos: ", list(metadatos["llave"].head(5)))
print("¿Aparece en metadatos? ", propia is not None and propia in set(metadatos["llave"].dropna()))

## Celda 29 (markdown)

## Paso 14. Unir las dos tablas
`merge` pega, a cada fila de la izquierda, las columnas de la fila de la derecha
que tiene la misma llave. Como cada muestra tiene muchos granos, **los datos de
la muestra se repiten en cada uno de sus granos**.

- `how="left"` conserva todos los granos, aunque no encuentren su muestra.
- `validate="many_to_one"` exige que cada llave aparezca **una sola vez** en los
  metadatos. Si aparece dos veces, se detiene: no sabría cuál usar.

## Celda 30 (code)

COMO = "left"      # prueba también "inner"

# Las muestras cuya llave no se pudo construir no pueden unirse con nada
con_llave = metadatos[metadatos["llave"].notna()]
if len(con_llave) < len(metadatos):
    print(f"⚠️  {len(metadatos) - len(con_llave)} muestras de los metadatos no tienen llave")

unida = caracteristicas.merge(
    con_llave.drop(columns=[COLUMNA_ID]),
    on="llave",
    how=COMO,
    validate="many_to_one",
)

print(f"Granos antes de unir:   {len(caracteristicas)}")
print(f"Filas después de unir:  {len(unida)}")
print(f"Columnas después:       {unida.shape[1]}  (antes {caracteristicas.shape[1]})")
display(unida.head(5))

## Celda 31 (markdown)

## Paso 15. Verificar y entregar
Antes de confiar en la tabla unida, tres comprobaciones: que no se perdieron ni
se duplicaron granos, que todos encontraron su muestra, y que los datos de la
muestra son los mismos en todos sus granos.

Al final, el cuaderno entrega **las dos cosas que pediste al principio de la
serie**: la imagen segmentada y numerada, y la tabla con las características y
los metadatos ya unidos.

## Celda 32 (code)

#@title ▶ Verificar y descargar todo
import zipfile

problemas = []
if len(unida) != len(caracteristicas):
    problemas.append("cambió el número de filas al unir")
if (~unida["llave"].isin(con_llave["llave"])).any():
    problemas.append("hay granos que no encontraron su muestra")
columnas_meta = [c for c in metadatos.columns if c not in ("llave", COLUMNA_ID)]
if columnas_meta and unida[columnas_meta].nunique(dropna=False).max() > 1:
    problemas.append("una muestra tiene valores distintos en sus granos")

print("✅ La unión es correcta" if not problemas else "⚠️  Revisar: " + "; ".join(problemas))

ARCHIVO_UNIDO = RUTA.rsplit(".", 1)[0] + "_con_metadatos.csv"
unida.to_csv(ARCHIVO_UNIDO, index=False, encoding="utf-8-sig")

ARCHIVO_ZIP = RUTA.rsplit(".", 1)[0] + "_resultados.zip"
with zipfile.ZipFile(ARCHIVO_ZIP, "w") as z:
    z.write("resultado.png")
    z.write(ARCHIVO_UNIDO)

print("Entregable final:", ARCHIVO_ZIP)
print("  · resultado.png          (imagen segmentada y numerada)")
print("  · " + ARCHIVO_UNIDO + "  (características + metadatos)")
files.download(ARCHIVO_ZIP)

## Celda 33 (markdown)

## De granos a familias
Hasta aquí la tabla tiene **una fila por grano**. Pero la pregunta de fondo no
es sobre un grano suelto, sino sobre la **familia**: todos los granos que
salieron de la misma mazorca, es decir, de la misma imagen. ¿Qué tamaño, qué
forma y qué color tienen, en promedio, los granos de esta familia?

Lo que sigue hace dos cosas:

- **Paso 16:** promedia las medidas de tu imagen. Queda una sola fila: tu
  familia.
- **Pasos 17 a 19:** repiten el proceso completo sobre las imágenes que tú
  decidas y entregan **un solo Excel**, con una fila por familia.

Para estos pasos basta con haber ejecutado del 1 al 11. Los metadatos (pasos 12
a 15) no se usan aquí.

## Celda 34 (markdown)

## Paso 16. Promediar por familia
`groupby` hace tres cosas seguidas: **separa** las filas en grupos (aquí, un
grupo por familia), **aplica** una operación a cada grupo (el promedio) y
**junta** los resultados en una tabla nueva, con una fila por grupo.

El nombre de la familia sale del nombre del archivo: `Grano_06 (1).jpg` es la
familia `Grano_06`.

La tabla trae el promedio de las diez medidas del paso 11 y una columna más,
`n_granos`: sobre cuántos granos se promedió. Un promedio de 5 granos no vale lo
mismo que uno de 50, por eso ese número viaja siempre junto al promedio.

Este código se muestra completo: es la idea nueva de esta parte.

## Celda 35 (code)

import os
import re

# Las medidas del paso 11 que se promedian (todas menos "imagen" y "grano")
MEDIDAS = ["largo_mm", "ancho_mm", "area_mm2", "perimetro_mm",
           "razon_aspecto", "circularidad", "solidez", "L", "a", "b"]

def nombre_familia(archivo):
    """'carpeta/Grano_06 (1).jpg' -> 'Grano_06': sin carpeta, sin extensión y sin '(1)'."""
    nombre = os.path.splitext(os.path.basename(str(archivo)))[0]
    return re.sub(r"\s*\(\d+\)$", "", nombre).strip()

def promediar_por_familia(tabla):
    """Una fila por familia: cuántos granos tiene y el promedio de cada medida."""
    tabla = tabla.assign(familia=tabla["imagen"].map(nombre_familia))
    grupos = tabla.groupby("familia", sort=False)
    resumen = grupos[MEDIDAS].mean()
    resumen.insert(0, "n_granos", grupos.size())
    return resumen.round(3)

mi_familia = promediar_por_familia(caracteristicas)

print(f"{len(caracteristicas)} granos  ->  {len(mi_familia)} familia")
display(mi_familia)

## Celda 36 (markdown)

## Lote: varias imágenes, un solo Excel
Para medir otra familia habría que subir otra imagen y repetir a mano los pasos
3 a 11. Con tres imágenes es tedioso; con treinta, nadie lo hace. La solución es
la de siempre en programación: **lo que se repite se empaca en una función**.

**El recorte se calcula de nuevo en cada imagen** (paso 4), así que la regla
puede estar arriba en una y abajo en otra. Si fijaste `RECORTE` a mano, ese
mismo recorte se aplica a todas.

**Todo lo demás se procesa con los ajustes que ya afinaste arriba:** `REDUCCION`,
`INVERTIR`, `DIAMETRO`, los dos umbrales de la red, `AREA_MINIMA`,
`AREA_MAXIMA`, `ELONGACION_MAXIMA`, `FILA` y `DPI`. Eso solo es válido si todas
las imágenes se tomaron igual: mismo escáner y misma resolución. Como nadie va
a mirar el recuadro verde de cada imagen, el paso 19 anota el recorte que usó
cada una y guarda su imagen numerada: ahí se ve si algo salió mal.

## Celda 37 (markdown)

## Paso 17. Empacar los pasos 3 a 11 en una función
`medir_imagen` recibe la ruta de una imagen y devuelve su tabla de granos, igual
a la del paso 11. Por dentro es el mismo código que ya ejecutaste, con los
mismos nombres; con doble clic sobre la celda lo ves completo.

**La prueba:** antes de usarla con imágenes nuevas, la celda le pide que mida
*tu* imagen del paso 3. Si la función está bien hecha, debe encontrar los mismos
granos y las mismas medidas que tu tabla `caracteristicas`. Si no coinciden, la
celda se detiene y te dice qué hacer.

## Celda 38 (code)

#@title ▶ Crear la función y probarla con tu imagen

def medir_imagen(ruta, archivo_control=None, mostrar=False):
    """Repite los pasos 3 a 11 sobre una imagen, con los ajustes actuales.

    Devuelve (tabla, control):
      tabla    una fila por grano, con las mismas columnas del paso 11
      control  lo que hay que revisar: el recorte usado, objetos de la red,
               granos aceptados, descartados y diámetro usado
    Si recibe `archivo_control`, guarda ahí la imagen numerada del paso 8.
    """
    # Paso 3: leer
    original = io.imread(ruta)
    if original.ndim == 3 and original.shape[2] == 4:
        original = original[:, :, :3]

    # Paso 4: recortar (cada imagen calcula su propia zona, salvo que RECORTE esté fijo)
    alto, ancho = original.shape[:2]
    (x0, y0, x1, y1), origen_recorte = zona_de_recorte(original)
    recorte = original[int(y0 * alto):int(y1 * alto), int(x0 * ancho):int(x1 * ancho)]

    # Paso 5: preparar lo que verá la red
    gris = color.rgb2gray(recorte)
    if REDUCCION > 1:
        gris = transform.rescale(gris, 1 / REDUCCION, anti_aliasing=True)
        vista = transform.rescale(recorte, 1 / REDUCCION, anti_aliasing=True, channel_axis=2)
    else:
        vista = recorte / 255.0
    entrada_red = util.invert(gris) if INVERTIR else gris

    # Paso 6: segmentar con la red
    mascaras, flujos, estilos, diametros = modelo.eval(
        entrada_red,
        diameter=DIAMETRO,
        channels=[0, 0],
        flow_threshold=FLOW_THRESHOLD,
        cellprob_threshold=CELLPROB_THRESHOLD,
    )

    # Paso 7: filtrar por geometría
    objetos = measure.regionprops(mascaras)
    granos = [p for p in objetos
              if AREA_MINIMA <= p.area <= AREA_MAXIMA and elongacion(p) <= ELONGACION_MAXIMA]

    # Paso 8: ordenar como se lee
    granos_ordenados = sorted(granos, key=lambda p: (round(p.centroid[0] / FILA), p.centroid[1]))

    # Paso 11: medir en milímetros y color
    lab = color.rgb2lab(vista)
    filas_tabla = []
    for numero, p in enumerate(granos_ordenados, start=1):
        dentro = mascaras == p.label
        filas_tabla.append({
            "imagen": os.path.basename(ruta),
            "grano": numero,
            "largo_mm": p.axis_major_length * MM_POR_PX,
            "ancho_mm": p.axis_minor_length * MM_POR_PX,
            "area_mm2": p.area * MM_POR_PX ** 2,
            "perimetro_mm": p.perimeter * MM_POR_PX,
            "razon_aspecto": p.axis_major_length / p.axis_minor_length,
            "circularidad": 4 * np.pi * p.area / p.perimeter ** 2 if p.perimeter > 0 else np.nan,
            "solidez": p.solidity,
            "L": lab[..., 0][dentro].mean(),
            "a": lab[..., 1][dentro].mean(),
            "b": lab[..., 2][dentro].mean(),
        })
    tabla = pd.DataFrame(filas_tabla, columns=["imagen", "grano"] + MEDIDAS).round(3)

    # Imagen de control: la misma del paso 8, más chica
    if archivo_control or mostrar:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.imshow(vista)
        for numero, p in enumerate(granos_ordenados, start=1):
            y, x = p.centroid
            ax.plot(x, y, marker="+", color="red", markersize=8, markeredgewidth=1.5)
            t = ax.text(x + 8, y - 8, str(numero), color="red", fontsize=7, weight="bold")
            t.set_path_effects([pe.withStroke(linewidth=2, foreground="white")])
        ax.set_title(f"{nombre_familia(ruta)}: {len(granos_ordenados)} granos")
        ax.axis("off")
        if archivo_control:
            fig.savefig(archivo_control, dpi=100, bbox_inches="tight")
        if mostrar:
            plt.show()
        plt.close(fig)

    control = {
        "recorte": f"{origen_recorte}: ({x0:.3f}, {y0:.3f}, {x1:.3f}, {y1:.3f})",
        "objetos_red": len(objetos),
        "granos": len(granos_ordenados),
        "descartados": len(objetos) - len(granos_ordenados),
        "diametro_px": round(float(np.ravel(diametros)[0]), 1),
    }
    return tabla, control


# ---- Prueba: la función debe repetir exactamente lo que hiciste a mano ----
tabla_prueba, control_prueba = medir_imagen(RUTA)

print(f"Paso 11 (a mano):   {len(caracteristicas)} granos")
print(f"Con la función:     {len(tabla_prueba)} granos")

if len(tabla_prueba) != len(caracteristicas):
    raise RuntimeError(
        "La función no encontró los mismos granos que tu tabla del paso 11. "
        "Casi siempre significa que cambiaste un ajuste después de medir: "
        "vuelve a ejecutar los pasos 4 a 11 y luego esta celda.")

diferencia = np.nanmax(np.abs(tabla_prueba[MEDIDAS].to_numpy(float)
                              - caracteristicas[MEDIDAS].to_numpy(float)))
if not np.allclose(tabla_prueba[MEDIDAS].to_numpy(float),
                   caracteristicas[MEDIDAS].to_numpy(float),
                   rtol=0.01, atol=0.01, equal_nan=True):
    raise RuntimeError(
        f"Mismo número de granos, pero las medidas no coinciden (diferencia máxima "
        f"{diferencia:.3f}). Vuelve a ejecutar los pasos 4 a 11 y luego esta celda.")

print(f"✅ La función mide igual que los pasos 3 a 11 (diferencia máxima: {diferencia:.3f})")

## Celda 39 (markdown)

## Paso 18. Elegir las imágenes del lote
Tú decides cuántas. Hay dos formas de entregarlas:

- **Subirlas:** deja `CARPETA` vacía. Aparece el botón de siempre; en la ventana
  puedes seleccionar **varias imágenes a la vez** (con `Ctrl` o `Shift`).
- **Leerlas de una carpeta:** escribe la ruta en `CARPETA`. Es lo práctico
  cuando son muchas, porque subir decenas de imágenes de escáner es lento. Para
  una carpeta de tu Drive la ruta empieza con `/content/drive/MyDrive/`, y el
  cuaderno pedirá permiso para conectarse.

`CUANTAS` limita el lote a las primeras imágenes de la lista; `0` significa
todas. Sirve para probar con tres antes de lanzar las treinta.

Cada imagen debe llamarse como su familia (`Grano_01.jpg`, `Grano_02.jpg`, ...):
ese nombre será el de su fila en el Excel.

## Celda 40 (code)

#@title ▶ Elegir las imágenes
CARPETA = ""  #@param {type:"string"}
CUANTAS = 0  #@param {type:"integer"}

EXTENSIONES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")

def orden_natural(ruta):
    """Para que Grano_2 quede antes que Grano_10."""
    return [int(parte) if parte.isdigit() else parte.lower()
            for parte in re.split(r"(\d+)", os.path.basename(ruta))]

if CARPETA.strip():
    carpeta = CARPETA.strip()
    if carpeta.startswith("/content/drive") and not os.path.isdir("/content/drive/MyDrive"):
        from google.colab import drive
        drive.mount("/content/drive")
    if not os.path.isdir(carpeta):
        raise FileNotFoundError(
            f"No existe la carpeta '{carpeta}'. Ábrela en el panel de archivos de la "
            "izquierda, clic derecho sobre ella -> Copiar ruta, y pégala en CARPETA.")
    candidatas = [os.path.join(carpeta, nombre) for nombre in os.listdir(carpeta)]
else:
    candidatas = list(files.upload().keys())

# Orden: por familia; dentro de una familia, el original antes que su copia "(1)"
rutas_lote = sorted((r for r in candidatas if r.lower().endswith(EXTENSIONES)),
                    key=lambda r: (orden_natural(nombre_familia(r)), len(os.path.basename(r))))
ignorados = len(candidatas) - len(rutas_lote)
if CUANTAS > 0:
    rutas_lote = rutas_lote[:CUANTAS]

if not rutas_lote:
    raise ValueError("No hay imágenes en el lote. Extensiones aceptadas: " + ", ".join(EXTENSIONES))

print(f"Imágenes en el lote: {len(rutas_lote)}"
      + (f"   (archivos ignorados por no ser imágenes: {ignorados})" if ignorados else ""))
for ruta in rutas_lote:
    print(f"   {os.path.basename(ruta):<28} -> familia {nombre_familia(ruta)}")

## Celda 41 (markdown)

## Paso 19. Procesar el lote y descargar el Excel
Cada imagen pasa por `medir_imagen`, y sus granos se promedian con
`promediar_por_familia`, la misma función del paso 16. Mientras trabaja, la
celda imprime una línea por imagen con su conteo. **Ese conteo es lo primero que
hay que revisar:** un promedio calculado sobre granos mal separados no sirve.

El Excel trae cuatro hojas:

| Hoja | Qué contiene |
|---|---|
| `familias` | **El resultado.** Una fila por familia: `n_granos` y el promedio de las diez medidas |
| `granos` | Todos los granos de todas las imágenes, uno por fila. De aquí salen los promedios |
| `control` | Una fila por imagen: el recorte que se usó, objetos de la red, granos aceptados, descartados, diámetro usado y un `estado` |
| `parametros` | Los ajustes con los que se procesó el lote, para poder repetirlo |

Los controles:

- `GRANOS_ESPERADOS`: si todas tus imágenes deben tener el mismo número de
  granos, escríbelo aquí y la hoja `control` marcará las que no coincidan. `0`
  significa no comparar.
- `MOSTRAR_CONTROL`: muestra la imagen numerada de cada familia mientras avanza.
  Desmárcalo si el lote es grande.
- `INCLUIR_IMAGENES_DE_CONTROL`: en lugar del Excel solo, descarga un `.zip` con
  el Excel y las imágenes numeradas.

Si una imagen falla, el lote **no se detiene**: queda anotada en la hoja
`control` con su error y se sigue con la siguiente.

## Celda 42 (code)

#@title ▶ Procesar el lote y descargar
NOMBRE_EXCEL = ""  #@param {type:"string"}
GRANOS_ESPERADOS = 0  #@param {type:"integer"}
MOSTRAR_CONTROL = False  #@param {type:"boolean"}
INCLUIR_IMAGENES_DE_CONTROL = False  #@param {type:"boolean"}

import shutil
import time
import zipfile
from openpyxl.styles import Font

CARPETA_CONTROL = "control_lote"
shutil.rmtree(CARPETA_CONTROL, ignore_errors=True)      # no mezclar con un lote anterior
os.makedirs(CARPETA_CONTROL)

# ---- 1. Medir cada imagen ----
tablas_lote, filas_control, familias_hechas = [], [], set()
inicio = time.time()
for i, ruta in enumerate(rutas_lote, start=1):
    familia = nombre_familia(ruta)
    fila = {"archivo": os.path.basename(ruta), "familia": familia}
    if familia in familias_hechas:
        fila["estado"] = "repetida: no se procesó"
    else:
        try:
            tabla, control = medir_imagen(
                ruta, os.path.join(CARPETA_CONTROL, familia + ".png"), MOSTRAR_CONTROL)
        except Exception as error:
            mensaje = (str(error).splitlines() or [""])[0]           # solo el primer renglón
            fila["estado"] = f"error: {type(error).__name__}: {mensaje}"
        else:
            familias_hechas.add(familia)
            fila.update(control)
            if control["granos"] == 0:
                fila["estado"] = "sin granos"
            elif control["recorte"].startswith("imagen completa"):
                fila["estado"] = "revisar: no se pudo recortar sola"
            elif GRANOS_ESPERADOS > 0 and control["granos"] != GRANOS_ESPERADOS:
                fila["estado"] = f"revisar: se esperaban {GRANOS_ESPERADOS}"
            else:
                fila["estado"] = "ok"
            if len(tabla):
                tablas_lote.append(tabla)
    filas_control.append(fila)
    print(f"[{i}/{len(rutas_lote)}] {familia:<22} {str(fila.get('granos', '-')):>4} granos   {fila['estado']}")

if not tablas_lote:
    raise RuntimeError("Ninguna imagen del lote dio granos. Revisa los mensajes de arriba.")

# ---- 2. Armar las tablas ----
granos_lote = pd.concat(tablas_lote, ignore_index=True)
familias = promediar_por_familia(granos_lote)
granos_lote.insert(0, "familia", granos_lote["imagen"].map(nombre_familia))
control_lote = pd.DataFrame(filas_control, columns=[
    "archivo", "familia", "recorte", "objetos_red", "granos", "descartados", "diametro_px",
    "estado"])
for columna in ["objetos_red", "granos", "descartados"]:     # enteros, aunque falten datos
    control_lote[columna] = control_lote[columna].astype("Int64")
parametros = pd.DataFrame({
    "parametro": ["fecha_utc", "imagenes_en_el_lote", "red", "RECORTE", "REDUCCION", "INVERTIR",
                  "DIAMETRO", "FLOW_THRESHOLD", "CELLPROB_THRESHOLD", "AREA_MINIMA",
                  "AREA_MAXIMA", "ELONGACION_MAXIMA", "FILA", "DPI", "MM_POR_PX"],
    "valor": [time.strftime("%Y-%m-%d %H:%M", time.gmtime()), len(rutas_lote), "Cellpose cyto3",
              "None (automático, uno por imagen)" if RECORTE is None else str(RECORTE),
              REDUCCION, str(INVERTIR), "None (la red lo estima)" if DIAMETRO is None else DIAMETRO,
              FLOW_THRESHOLD, CELLPROB_THRESHOLD, AREA_MINIMA,
              AREA_MAXIMA, ELONGACION_MAXIMA, FILA, DPI, MM_POR_PX],
})

# ---- 3. Escribir el Excel ----
if not NOMBRE_EXCEL.lower().endswith(".xlsx"):
    NOMBRE_EXCEL += ".xlsx"
with pd.ExcelWriter(NOMBRE_EXCEL, engine="openpyxl") as libro:
    familias.to_excel(libro, sheet_name="familias")
    granos_lote.to_excel(libro, sheet_name="granos", index=False)
    control_lote.to_excel(libro, sheet_name="control", index=False)
    parametros.to_excel(libro, sheet_name="parametros", index=False)
    for hoja in libro.sheets.values():
        hoja.freeze_panes = "B2"                         # encabezado y primera columna fijos
        for celda in hoja[1]:
            celda.font = Font(bold=True)
        for columna in hoja.columns:
            mas_largo = max(len(str(celda.value)) for celda in columna if celda.value is not None)
            hoja.column_dimensions[columna[0].column_letter].width = min(mas_largo + 3, 60)

# ---- 4. Reporte ----
por_revisar = control_lote[control_lote["estado"] != "ok"]
print()
print(f"Imágenes en el lote:    {len(rutas_lote)}")
print(f"Familias en el Excel:   {len(familias)}")
print(f"Granos medidos:         {len(granos_lote)}")
print(f"Tiempo:                 {(time.time() - inicio) / 60:.1f} min")
if len(por_revisar):
    print(f"⚠️  {len(por_revisar)} imágenes necesitan revisión (hoja 'control'):")
    display(por_revisar[["archivo", "granos", "estado"]])
else:
    print("✅ Todas las imágenes se procesaron sin avisos")
display(familias)

# ---- 5. Descargar ----
if INCLUIR_IMAGENES_DE_CONTROL:
    ARCHIVO_LOTE = NOMBRE_EXCEL[:-5] + "_con_control.zip"
    with zipfile.ZipFile(ARCHIVO_LOTE, "w") as z:
        z.write(NOMBRE_EXCEL)
        for nombre in sorted(os.listdir(CARPETA_CONTROL), key=orden_natural):
            z.write(os.path.join(CARPETA_CONTROL, nombre))
else:
    ARCHIVO_LOTE = NOMBRE_EXCEL
print("Entregable:", ARCHIVO_LOTE)
files.download(ARCHIVO_LOTE)

## Celda 43 (markdown)

## Clasificar: de las medidas al rendimiento
Ya hay dos tablas con **una fila por familia**:

- **Lo que dice la imagen:** el Excel 1, con el promedio de las diez medidas.
- **Lo que dice la mazorca:** los metadatos, con el rendimiento y tres datos
  más (`Weight_50K`, `Weight_AllK` y `All_Kernels`).

La pregunta de hoy: **¿se puede saber si una familia es de rendimiento Alto o
Bajo sin mirar su rendimiento?** Para responderla, el cuaderno aprende de las
familias cuya respuesta conoce y luego se examina con cuatro que nunca vio.

| Paso | Qué hace |
|---|---|
| 20 | Une las dos tablas |
| 21 | Define la respuesta (la clase) y las entradas |
| 22 | Aparta las familias de prueba |
| 23 | Normaliza las entradas |
| 24 | Mide qué entradas acompañan al rendimiento y elige las mejores |
| 25 | Entrena y se pone a prueba dejando una familia fuera cada vez |
| 26 | Predice las familias de prueba y entrega la tabla de confusión |

**Se puede empezar aquí.** Si ya tienes los dos archivos de Excel, esta parte no
necesita nada de lo de arriba.

## Celda 44 (markdown)

## Paso 20. Reunir las dos tablas
Para comparar lo que se mide en la imagen con lo que se sabe de la mazorca, las
dos tablas tienen que hablar de las mismas familias. La llave es el nombre:
`Grano_06.jpg` en los metadatos y `Grano_06` en el Excel 1 son la misma familia.

Como aquí hay una fila por familia en cada tabla, la unión es **uno a uno**
(`one_to_one`). Compárala con la del paso 14, que era muchos a uno: allá cada
muestra se repetía en todos sus granos.

**Qué debe aparecer:** cuántas familias tiene cada tabla y cuántas quedaron en
las dos. Una familia que solo está en una de las tablas no puede usarse; la
celda dice cuáles son.

- Si acabas de ejecutar el paso 19, se usa esa tabla. Marca
  `SUBIR_CARACTERISTICAS` para subir en su lugar un Excel 1 ya hecho (por
  ejemplo, el de las 19 familias que te compartieron).
- `COLUMNA_FAMILIA` es la columna de los metadatos que trae el nombre de la
  imagen.

## Celda 45 (code)

#@title ▶ Reunir las dos tablas
SUBIR_CARACTERISTICAS = True  #@param {type:"boolean"}
COLUMNA_FAMILIA = "nombre_imagen"  #@param {type:"string"}

# Lo necesario para poder empezar en este paso, sin haber ejecutado los anteriores
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import files

if "MEDIDAS" not in globals():          # las mismas definiciones del paso 16
    MEDIDAS = ["largo_mm", "ancho_mm", "area_mm2", "perimetro_mm",
               "razon_aspecto", "circularidad", "solidez", "L", "a", "b"]

    def nombre_familia(archivo):
        """'carpeta/Grano_06 (1).jpg' -> 'Grano_06': sin carpeta, sin extensión y sin '(1)'."""
        nombre = os.path.splitext(os.path.basename(str(archivo)))[0]
        return re.sub(r"\s*\(\d+\)$", "", nombre).strip()

# ---- 1. Lo que dice la imagen: características por familia (Excel 1) ----
if SUBIR_CARACTERISTICAS or "familias" not in globals():
    print("Sube el Excel 1, el de características por familia (paso 19):")
    ARCHIVO_CARACTERISTICAS = list(files.upload().keys())[0]
    try:
        tabla_imagen = pd.read_excel(ARCHIVO_CARACTERISTICAS, sheet_name="familias")
    except ValueError:
        raise ValueError(f"'{ARCHIVO_CARACTERISTICAS}' no tiene la hoja 'familias'. "
                         "Sube el Excel que descarga el paso 19.") from None
else:
    ARCHIVO_CARACTERISTICAS = "tabla del paso 19 (en memoria)"
    tabla_imagen = familias.reset_index()
tabla_imagen["familia"] = tabla_imagen["familia"].map(nombre_familia)

# ---- 2. Lo que dice la mazorca: metadatos ----
print("Sube el Excel de metadatos:")
ARCHIVO_METADATOS = list(files.upload().keys())[0]
if ARCHIVO_METADATOS.lower().endswith(".csv"):
    amarillas = pd.read_csv(ARCHIVO_METADATOS)
else:
    amarillas = pd.read_excel(ARCHIVO_METADATOS)
if COLUMNA_FAMILIA not in amarillas.columns:
    raise KeyError(f"Los metadatos no tienen la columna '{COLUMNA_FAMILIA}'. Columnas que sí hay: "
                   f"{list(amarillas.columns)}. Escribe la correcta en COLUMNA_FAMILIA.")
amarillas = amarillas.dropna(subset=[COLUMNA_FAMILIA]).dropna(axis=1, how="all")
amarillas["familia"] = amarillas[COLUMNA_FAMILIA].map(nombre_familia)

for nombre_tabla, tabla_revisada in [("el Excel 1", tabla_imagen), ("los metadatos", amarillas)]:
    repetidas = sorted(set(tabla_revisada["familia"][tabla_revisada["familia"].duplicated()]))
    if repetidas:
        raise ValueError(f"En {nombre_tabla} hay familias repetidas: {repetidas}. "
                         "Cada familia debe aparecer una sola vez.")

# ---- 3. Unir: una fila por familia en las dos tablas ----
datos = tabla_imagen.merge(amarillas.drop(columns=[COLUMNA_FAMILIA]),
                           on="familia", how="inner", validate="one_to_one")

solo_imagen = sorted(set(tabla_imagen["familia"]) - set(amarillas["familia"]))
solo_metadatos = sorted(set(amarillas["familia"]) - set(tabla_imagen["familia"]))
print()
print(f"Familias con imagen:     {len(tabla_imagen)}   ({ARCHIVO_CARACTERISTICAS})")
print(f"Familias con metadatos:  {len(amarillas)}   ({ARCHIVO_METADATOS})")
print(f"Familias en las dos:     {len(datos)}")
if solo_imagen:
    print("⚠️  Con imagen pero sin metadatos (no entran):", solo_imagen)
if solo_metadatos:
    print("⚠️  Con metadatos pero sin imagen (no entran):", solo_metadatos)
if len(datos) < 8:
    print("⚠️  Son muy pocas familias para entrenar. Si tienes el Excel 1 con todas, "
          "marca SUBIR_CARACTERISTICAS y vuelve a ejecutar.")
display(datos.head(8))

## Celda 46 (markdown)

## Paso 21. Definir la respuesta y las entradas
Un clasificador necesita dos cosas, y hay que separarlas con cuidado:

- **La respuesta (la clase):** lo que queremos que aprenda a decir. Sale del
  signo de la columna `Yield-media(yield)`, la regla del registro `Class` de los
  metadatos: **signo positivo → `Alto`, signo negativo → `Bajo`**.
- **Las entradas:** lo que el modelo puede mirar para decidir. Son las diez
  medidas de la imagen y tres metadatos de la mazorca: `Weight_50K`,
  `Weight_AllK` y `All_Kernels`.

**La regla de oro:** la respuesta nunca puede estar entre las entradas. `Yield`
y `Yield-media(yield)` *son* el rendimiento; si el modelo los viera, no estaría
prediciendo: estaría copiando.

`ENTRADAS` decide con qué trabaja el modelo. Es el experimento de hoy: ¿la
imagen aporta algo que los metadatos no traen?

## Celda 47 (code)

#@title ▶ Definir la clase y las entradas
COLUMNA_RENDIMIENTO = "Yield-media(yield)"  #@param {type:"string"}
ENTRADAS = "imagen + metadatos"  #@param ["imagen + metadatos", "solo imagen", "solo metadatos"]

# Metadatos que el modelo puede mirar (se conocen sin saber el rendimiento)
#METADATOS_DE_ENTRADA = ["Weight_50K", "Weight_AllK", "All_Kernels"]
#----------------ENTRADA TRAMPOSA -------------------
METADATOS_DE_ENTRADA = [
    "Weight_50K",
    "Weight_AllK",
    "All_Kernels",
    "Yield-media(yield)"
]
# Columnas que SON la respuesta: nunca deben estar entre las entradas
RESPUESTAS = [COLUMNA_RENDIMIENTO, "Yield", "Class", "clase"]
CLASES = ["Alto", "Bajo"]

if COLUMNA_RENDIMIENTO not in datos.columns:
    raise KeyError(f"No existe la columna '{COLUMNA_RENDIMIENTO}'. Columnas: {list(datos.columns)}")
sin_dato = datos[COLUMNA_RENDIMIENTO].isna()
if sin_dato.any():
    print(f"⚠️  Sin valor en '{COLUMNA_RENDIMIENTO}' (no entran): {list(datos.loc[sin_dato, 'familia'])}")
    datos = datos[~sin_dato].reset_index(drop=True)

# ---- La respuesta: signo positivo -> Alto, signo negativo -> Bajo ----
datos["clase"] = np.where(datos[COLUMNA_RENDIMIENTO] > 0, "Alto", "Bajo")
if "Class" in datos.columns:            # si el archivo trae el registro Class, ese manda
    registro = datos["Class"].astype(str).str.strip().str.capitalize()
    distintas = list(datos.loc[registro != datos["clase"], "familia"])
    if distintas:
        print("⚠️  El signo y la columna Class no coinciden en", distintas, "-> se usa Class")
        datos["clase"] = registro
    else:
        print("✅ El signo coincide con la columna Class en todas las familias")

# ---- Las entradas ----
ENTRADAS_IMAGEN = [c for c in MEDIDAS if c in datos.columns]
ENTRADAS_METADATOS = [c for c in METADATOS_DE_ENTRADA if c in datos.columns]
entradas = {"imagen + metadatos": ENTRADAS_IMAGEN + ENTRADAS_METADATOS,
            "solo imagen": ENTRADAS_IMAGEN,
            "solo metadatos": ENTRADAS_METADATOS}[ENTRADAS]
no_estan = [c for c in METADATOS_DE_ENTRADA if c not in datos.columns]
if no_estan:
    print("⚠️  Estos metadatos de entrada no están en el archivo:", no_estan)
if not entradas:
    raise ValueError("No quedó ninguna entrada. Revisa ENTRADAS y METADATOS_DE_ENTRADA.")
datos[entradas] = datos[entradas].apply(pd.to_numeric, errors="coerce")

tramposas = [c for c in entradas if c in RESPUESTAS]
if tramposas:
    print(f"🚫 {tramposas} es la respuesta y está entre las entradas.")
    print("   El resultado que salga no vale: el modelo estaría copiando, no prediciendo.")

conteo = datos["clase"].value_counts().reindex(CLASES, fill_value=0)
print(f"Familias: {len(datos)}   ->   Alto: {conteo['Alto']}   Bajo: {conteo['Bajo']}")
print(f"Entradas ({ENTRADAS}): {len(entradas)}")
print("   de la imagen:   ", [c for c in entradas if c in ENTRADAS_IMAGEN])
print("   de la mazorca:  ", [c for c in entradas if c not in ENTRADAS_IMAGEN])
display(datos[["familia", COLUMNA_RENDIMIENTO, "clase"]])

## Celda 48 (markdown)

## Paso 22. Apartar las familias de prueba
Si estudias para un examen con ejercicios resueltos y el examen trae esos mismos
ejercicios, un diez no demuestra que aprendiste: demuestra que tienes memoria.
Con un modelo pasa igual. Por eso **cuatro familias se apartan antes de
empezar**: dos de rendimiento Alto y dos de Bajo. El modelo no las usa para
nada: ni para entrenar, ni para normalizar, ni para elegir entradas.

Su clase queda guardada, como en un sobre cerrado, hasta el paso 26.

- `FAMILIAS_PRUEBA`: los nombres de las familias apartadas.
- Con la lista vacía, `[]`, el cuaderno sortea dos por clase; `SEMILLA` fija el
  sorteo para que salga igual cada vez.

**Qué debe aparecer:** cuántas familias quedan para entrenar y la tabla con lo
único que el modelo verá de las de prueba: sus entradas, sin la clase.

## Celda 49 (code)

#@title ▶ Apartar las familias de prueba
FAMILIAS_PRUEBA = ["Grano_01", "Grano_02", "Grano_04", "Grano_06"]  #@param {type:"raw"}
SEMILLA = 42  #@param {type:"integer"}

if FAMILIAS_PRUEBA:
    nombres_prueba = [nombre_familia(f) for f in FAMILIAS_PRUEBA]
    no_existen = [f for f in nombres_prueba if f not in set(datos["familia"])]
    if no_existen:
        raise ValueError(f"Estas familias de prueba no están en la tabla del paso 20: {no_existen}. "
                         f"Las que hay: {list(datos['familia'])}")
else:
    nombres_prueba = list(datos.groupby("clase").sample(n=2, random_state=SEMILLA)["familia"])
    print("Sorteo con semilla", SEMILLA, "->", sorted(nombres_prueba))

es_prueba = datos["familia"].isin(nombres_prueba)
entrenamiento = datos[~es_prueba].reset_index(drop=True)
prueba = datos[es_prueba].reset_index(drop=True)

en_entrenamiento = entrenamiento["clase"].value_counts().reindex(CLASES, fill_value=0)
en_prueba = prueba["clase"].value_counts().reindex(CLASES, fill_value=0)
if (en_entrenamiento < 2).any():
    raise ValueError("En entrenamiento deben quedar al menos 2 familias de cada clase. "
                     f"Quedaron: {en_entrenamiento.to_dict()}. Cambia FAMILIAS_PRUEBA.")

print(f"Entrenamiento: {len(entrenamiento)} familias   (Alto: {en_entrenamiento['Alto']}, Bajo: {en_entrenamiento['Bajo']})")
print(f"Prueba:        {len(prueba)} familias   (Alto: {en_prueba['Alto']}, Bajo: {en_prueba['Bajo']})")
if en_prueba["Alto"] != en_prueba["Bajo"]:
    print("⚠️  La prueba no tiene las mismas familias de cada clase.")
print()
print("Lo único que el modelo verá de las familias de prueba (su clase sigue en el sobre):")
display(prueba[["familia"] + entradas].round(3))

## Celda 50 (markdown)

## Paso 23. Normalizar
Las entradas están en unidades distintas: `All_Kernels` ronda los 450 granos,
`largo_mm` los 10 milímetros y `circularidad` no pasa de 1. Si se comparan así,
la que tiene los números más grandes parece la más importante solo por su
unidad.

**Normalizar** pone todas en la misma regla: a cada columna se le resta su media
y se divide entre su desviación estándar. Después, todas tienen media 0 y
desviación 1, y un valor de +1 significa lo mismo en cualquiera: "una desviación
por encima de lo típico".

Dos cuidados:

- **La media y la desviación se calculan solo con las familias de
  entrenamiento,** y con esos mismos números se normalizan las de prueba. Si la
  prueba participara en el cálculo, ya habría influido en el modelo.
- **Cuánto varía una entrada se mira antes de normalizar,** porque después todas
  varían igual. La columna `variacion_%` es la desviación como porcentaje de la
  media. Una entrada que casi no cambia de una familia a otra no puede servir
  para distinguirlas. Para `a` y `b` queda vacía (`NaN`): son coordenadas de
  color que pueden ser negativas, y un porcentaje de ellas no significa nada.

**Qué debe aparecer:** la tabla con cada entrada antes y después, y dos
gráficas. En la de la izquierda una o dos entradas aplastan a las demás; en la
de la derecha, todas se pueden comparar.

## Celda 51 (code)

#@title ▶ Normalizar
SIN_CERO_NATURAL = ["a", "b"]      # coordenadas de color: su "variación %" no significa nada

media_ent = entrenamiento[entradas].mean()
desv_ent = entrenamiento[entradas].std().replace(0, 1)      # una columna constante no se divide entre 0


def normalizar(tabla, media, desv):
    """A cada columna: restarle la media y dividir entre la desviación.
    Un dato que falta queda en 0, que es la media de entrenamiento."""
    return ((tabla[media.index] - media) / desv).fillna(0)


Z_ent = normalizar(entrenamiento, media_ent, desv_ent)
Z_pru = normalizar(prueba, media_ent, desv_ent)             # con la media y desviación de ENTRENAMIENTO

variacion = 100 * entrenamiento[entradas].std() / media_ent.abs()
sin_porcentaje = [c for c in entradas if c in SIN_CERO_NATURAL or (entrenamiento[c] < 0).any()]
variacion[sin_porcentaje] = np.nan                           # con valores negativos, el % no significa nada

resumen_normalizacion = pd.DataFrame({
    "media": media_ent,
    "desviacion": entrenamiento[entradas].std(),
    "variacion_%": variacion.round(1),
    "media_normalizada": Z_ent.mean(),
    "desviacion_normalizada": Z_ent.std(),
}).round(3)

faltan_datos = int(entrenamiento[entradas].isna().sum().sum() + prueba[entradas].isna().sum().sum())
if faltan_datos:
    print(f"⚠️  Hay {faltan_datos} datos vacíos en las entradas: se tratan como la media.")
print("Media y desviación calculadas con", len(entrenamiento), "familias de entrenamiento")
display(resumen_normalizacion)

fig, (ax_antes, ax_despues) = plt.subplots(1, 2, figsize=(13, 0.38 * len(entradas) + 2), sharey=True)
ax_antes.boxplot([entrenamiento[c].dropna() for c in entradas[::-1]], vert=False)
ax_antes.set_title("Antes: cada entrada en sus unidades")
ax_despues.boxplot([Z_ent[c] for c in entradas[::-1]], vert=False)
ax_despues.axvline(0, color="gray", linewidth=0.8)
ax_despues.set_title("Después: todas en desviaciones respecto a la media")
ax_antes.set_yticks(range(1, len(entradas) + 1))            # el eje se comparte entre las dos gráficas
ax_antes.set_yticklabels(entradas[::-1])
plt.tight_layout()
plt.show()

## Celda 52 (markdown)

## Paso 24. ¿Qué entradas acompañan al rendimiento?
Que una entrada varíe mucho entre familias es necesario, pero no basta: puede
variar por razones que no tienen que ver con el rendimiento. Lo que importa es
**cuánto de esa variación va junto con el rendimiento**. Eso mide la
**correlación**, un número entre −1 y +1:

- cerca de **+1**: cuando la entrada sube, el rendimiento sube;
- cerca de **−1**: cuando la entrada sube, el rendimiento baja;
- cerca de **0**: la entrada cambia sin relación con el rendimiento.

Con las columnas ya normalizadas la cuenta es directa: la correlación es el
promedio del producto de las dos columnas, familia por familia.

La **importancia** de una entrada es el tamaño de su correlación, sin el signo.
El modelo no usa todas: se queda con las `N_CARACTERISTICAS` más importantes.
Con tan pocas familias, darle muchas entradas es darle muchas formas de
encontrar coincidencias que no existen.

**Qué debe aparecer:**

- La tabla ordenada de mayor a menor importancia.
- Una gráfica de barras con dos líneas punteadas. Marcan el tamaño de
  correlación que el puro azar produce con facilidad cuando hay tan pocas
  familias: **una barra que no pasa de la línea no demuestra nada.**
- Una gráfica de variación contra importancia. Sirve para comprobar la idea con
  tus datos: ¿las entradas que más varían son las más importantes?

Todo se calcula solo con las familias de entrenamiento.

## Celda 53 (code)

#@title ▶ Correlación con el rendimiento
N_CARACTERISTICAS = 1  #@param {type:"integer"}
from scipy import stats

N_CARACTERISTICAS = max(1, min(int(N_CARACTERISTICAS), len(entradas)))


def correlaciones(tabla):
    """Correlación de cada entrada con el rendimiento, usando solo las familias de `tabla`."""
    return tabla[entradas].corrwith(tabla[COLUMNA_RENDIMIENTO]).fillna(0)


def elegir_entradas(tabla):
    """Las N entradas de mayor importancia (|correlación|), calculada solo con `tabla`."""
    orden = correlaciones(tabla).abs().sort_values(ascending=False, kind="stable")
    return list(orden.index[:N_CARACTERISTICAS])


corr_ent = correlaciones(entrenamiento)
orden_importancia = corr_ent.abs().sort_values(ascending=False, kind="stable").index
elegidas = elegir_entradas(entrenamiento)

analisis = pd.DataFrame({
    "origen": ["imagen" if c in ENTRADAS_IMAGEN else "mazorca" for c in entradas],
    "variacion_%": variacion.round(1),
    "correlacion": corr_ent.round(3),
    "importancia": corr_ent.abs().round(3),
}, index=entradas).reindex(orden_importancia)
analisis["elegida"] = ["sí" if c in elegidas else "" for c in analisis.index]

# Tamaño de correlación que el azar alcanza 1 de cada 20 veces con este número de familias
n_ent = len(entrenamiento)
t_critico = stats.t.ppf(0.975, n_ent - 2)
r_azar = t_critico / np.sqrt(n_ent - 2 + t_critico ** 2)
superan = int((corr_ent.abs() > r_azar).sum())

print(f"Familias de entrenamiento: {n_ent}")
print(f"Con {n_ent} familias, el puro azar produce sin dificultad correlaciones de hasta ±{r_azar:.2f}.")
print(f"Entradas que superan esa línea: {superan} de {len(entradas)}")
print(f"Elegidas para el modelo ({N_CARACTERISTICAS}): {elegidas}")
display(analisis)

fig, (ax_barras, ax_variacion) = plt.subplots(1, 2, figsize=(14, 0.38 * len(entradas) + 2.2))
en_orden = analisis.iloc[::-1]
ax_barras.barh(en_orden.index, en_orden["correlacion"],
               color=["#C8891B" if e == "sí" else "#C9CDD2" for e in en_orden["elegida"]])
for limite in (-r_azar, r_azar):
    ax_barras.axvline(limite, color="black", linestyle="--", linewidth=1)
ax_barras.axvline(0, color="gray", linewidth=0.8)
ax_barras.set_xlim(-1, 1)
ax_barras.set_xlabel("correlación con " + COLUMNA_RENDIMIENTO)
ax_barras.set_title("En color, las elegidas · punteado: lo que alcanza el azar")

con_variacion = analisis.dropna(subset=["variacion_%"])
ax_variacion.scatter(con_variacion["variacion_%"], con_variacion["importancia"], color="#22262B")
for entrada, fila_analisis in con_variacion.iterrows():
    ax_variacion.annotate(entrada, (fila_analisis["variacion_%"], fila_analisis["importancia"]),
                          textcoords="offset points", xytext=(5, 4), fontsize=8)
ax_variacion.axhline(r_azar, color="black", linestyle="--", linewidth=1)
ax_variacion.set_xlabel("variación entre familias (%)")
ax_variacion.set_ylabel("importancia (|correlación|)")
ax_variacion.set_ylim(0, 1)
ax_variacion.set_title("¿Las que más varían son las más importantes?")
plt.tight_layout()
plt.show()

## Celda 54 (markdown)

## Paso 25. Entrenar y validar dejando una fuera
El modelo es una **regresión logística**. Funciona como una balanza: cada
entrada empuja hacia `Alto` o hacia `Bajo` con un peso, y los pesos se ajustan
con las familias de entrenamiento hasta que la balanza se equivoca lo menos
posible. El resultado es una probabilidad: arriba de 0.5 dice `Alto`; abajo,
`Bajo`.

Antes de abrir el sobre conviene saber si el modelo aprende algo. Con tan pocas
familias no se puede apartar otro grupo, así que se hace un examen por turnos,
**dejando una fuera**:

1. se esconde una familia de entrenamiento;
2. con las demás se repite todo: normalizar, elegir entradas y ajustar el modelo;
3. se predice la familia escondida y se anota si acertó;
4. se repite con cada una.

Así salen tantas predicciones como familias de entrenamiento, y ninguna se hizo
con un modelo que hubiera visto a esa familia.

**Qué debe aparecer:**

- La predicción de cada familia y una primera **tabla de confusión**: las filas
  dicen qué era la familia y las columnas qué dijo el modelo. Los aciertos están
  en la diagonal.
- Una referencia sin la cual el número no significa nada: cuántas acertaría
  alguien que respondiera siempre la clase más común, sin mirar ningún dato.
- Cuántas veces se eligió cada entrada. Si la lista cambia mucho al quitar una
  sola familia, la elección depende de pocos datos.

## Celda 55 (code)

#@title ▶ Entrenar y validar dejando una fuera
from collections import Counter
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix


def entrenar_y_predecir(ent, nuevas):
    """Aprende SOLO de `ent` (media, desviación, elección de entradas y pesos) y predice `nuevas`.
    Devuelve (clase predicha, probabilidad de Alto, entradas usadas)."""
    usadas = elegir_entradas(ent)
    media, desv = ent[usadas].mean(), ent[usadas].std().replace(0, 1)
    clasificador = LogisticRegression(class_weight="balanced")
    clasificador.fit(normalizar(ent, media, desv).to_numpy(), ent["clase"])
    z_nuevas = normalizar(nuevas, media, desv).to_numpy()
    prob_alto = clasificador.predict_proba(z_nuevas)[:, list(clasificador.classes_).index("Alto")]
    return clasificador.predict(z_nuevas), prob_alto, usadas


def tabla_de_confusion(real, predicha):
    """Filas: la clase real. Columnas: lo que dijo el modelo."""
    return pd.DataFrame(confusion_matrix(list(real), list(predicha), labels=CLASES),
                        index=["real " + c for c in CLASES],
                        columns=["predicha " + c for c in CLASES])


# ---- Dejar una fuera: cada familia se predice con un modelo que nunca la vio ----
filas_validacion, veces_elegida = [], Counter()
for i in range(len(entrenamiento)):
    escondida = entrenamiento.iloc[[i]]
    las_demas = entrenamiento.drop(entrenamiento.index[i])
    clase_predicha, prob_alto, usadas = entrenar_y_predecir(las_demas, escondida)
    veces_elegida.update(usadas)
    filas_validacion.append({
        "familia": escondida["familia"].iloc[0],
        "clase_real": escondida["clase"].iloc[0],
        "clase_predicha": clase_predicha[0],
        "prob_alto": round(float(prob_alto[0]), 2),
    })
validacion = pd.DataFrame(filas_validacion)
validacion["acierto"] = np.where(validacion["clase_real"] == validacion["clase_predicha"], "sí", "no")
confusion_validacion = tabla_de_confusion(validacion["clase_real"], validacion["clase_predicha"])

aciertos_val = int((validacion["acierto"] == "sí").sum())
clase_comun = entrenamiento["clase"].value_counts().idxmax()
aciertos_referencia = int((entrenamiento["clase"] == clase_comun).sum())

display(validacion)
display(confusion_validacion)
print(f"Aciertos dejando una fuera:             {aciertos_val} de {len(validacion)}")
print(f"Referencia (decir siempre '{clase_comun}'):      {aciertos_referencia} de {len(validacion)}")
if aciertos_val <= aciertos_referencia:
    print("-> El modelo no supera a quien responde siempre lo mismo sin mirar los datos.")
else:
    print(f"-> El modelo supera a la referencia por {aciertos_val - aciertos_referencia}.")
print()
print(f"Veces que se eligió cada entrada en las {len(validacion)} rondas:")
for entrada, veces in veces_elegida.most_common():
    print(f"   {entrada:<16} {veces}")

## Celda 56 (markdown)

## Paso 26. Abrir el sobre: las familias de prueba
Ahora sí. El modelo se ajusta con todas las familias de entrenamiento y predice
las cuatro que se apartaron en el paso 22. Solo entonces se compara con su clase
real.

**La tabla de confusión** tiene cuatro casillas:

| | el modelo dijo `Alto` | el modelo dijo `Bajo` |
|---|---|---|
| **era `Alto`** | acierto | error: se le escapó una de alto rendimiento |
| **era `Bajo`** | error: anunció una de alto rendimiento que no lo era | acierto |

Los dos errores no cuestan lo mismo: no es igual descartar una familia buena que
sembrar una mala. Por eso se reporta la tabla completa y no solo un porcentaje.

**Cómo leer el resultado con honestidad:**

- Con cuatro familias, la suerte pesa mucho. La celda dice qué tan seguido
  alguien que adivina al azar igualaría o superaría el resultado.
- La tabla de la validación (paso 25) tiene más familias y dice más. Si las dos
  cuentan la misma historia, se le puede creer; si se contradicen, manda la que
  tiene más familias.

Al final se descarga el **Excel 2**, `clasificacion_rendimiento.xlsx`, junto con
la imagen de las dos tablas de confusión.

## Celda 57 (code)

#@title ▶ Predecir las familias de prueba y ver la tabla de confusión
import time
import zipfile
from math import comb
from openpyxl.styles import Font

# ---- 1. Entrenar con todo el entrenamiento y predecir la prueba ----
clase_predicha, prob_alto, usadas_final = entrenar_y_predecir(entrenamiento, prueba)
resultado_prueba = pd.DataFrame({
    "familia": prueba["familia"],
    "clase_real": prueba["clase"],            # aquí se abre el sobre
    "clase_predicha": clase_predicha,
    "prob_alto": np.round(prob_alto, 2),
})
resultado_prueba["acierto"] = np.where(resultado_prueba["clase_real"] == resultado_prueba["clase_predicha"], "sí", "no")
confusion_prueba = tabla_de_confusion(resultado_prueba["clase_real"], resultado_prueba["clase_predicha"])

aciertos_pru, n_pru = int((resultado_prueba["acierto"] == "sí").sum()), len(resultado_prueba)
azar = sum(comb(n_pru, k) for k in range(aciertos_pru, n_pru + 1)) / 2 ** n_pru

print("Entradas que usó el modelo final:", usadas_final)
display(resultado_prueba)

# ---- 2. Las dos tablas de confusión ----
def dibujar_confusion(ax, matriz, titulo):
    maximo = max(int(matriz.to_numpy().max()), 1)
    ax.imshow(matriz.to_numpy(), cmap="YlOrBr", vmin=0, vmax=maximo)
    for fila_m in range(2):
        for columna_m in range(2):
            valor = int(matriz.iloc[fila_m, columna_m])
            ax.text(columna_m, fila_m, valor, ha="center", va="center", fontsize=22, weight="bold",
                    color="white" if valor > 0.6 * maximo else "black")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["dijo " + c for c in CLASES])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["era " + c for c in CLASES])
    ax.set_title(titulo, fontsize=11)

fig, (ax_prueba, ax_validacion) = plt.subplots(1, 2, figsize=(11, 4.6))
dibujar_confusion(ax_prueba, confusion_prueba,
                  f"PRUEBA: {n_pru} familias que el modelo nunca vio\n{aciertos_pru} de {n_pru} aciertos")
dibujar_confusion(ax_validacion, confusion_validacion,
                  f"VALIDACIÓN: dejando una fuera, {len(validacion)} familias\n{aciertos_val} de {len(validacion)} aciertos")
fig.suptitle(f"Tabla de confusión · entradas: {ENTRADAS}", fontsize=12)
plt.tight_layout()
fig.savefig("tabla_de_confusion.png", dpi=130, bbox_inches="tight")
plt.show()

print(f"PRUEBA:      {aciertos_pru} de {n_pru} aciertos")
cuantas = f"las {n_pru}" if aciertos_pru == n_pru else f"{aciertos_pru} o más de {n_pru}"
print(f"             Adivinando al azar, {cuantas} se aciertan el {azar:.0%} de las veces.")
print(f"VALIDACIÓN:  {aciertos_val} de {len(validacion)} aciertos   "
      f"(decir siempre '{clase_comun}': {aciertos_referencia} de {len(validacion)})")

# ---- 3. Excel 2 ----
ARCHIVO_CLASIFICACION = "clasificacion_rendimiento.xlsx"
hoja_datos = datos[list(dict.fromkeys(["familia", COLUMNA_RENDIMIENTO, "clase"] + entradas))].copy()
hoja_datos.insert(1, "conjunto", np.where(es_prueba, "prueba", "entrenamiento"))
hoja_confusion = pd.concat({"prueba": confusion_prueba, "validación": confusion_validacion},
                           names=["conjunto", "clase real"]).reset_index()
hoja_parametros = pd.DataFrame({
    "parametro": ["fecha_utc", "caracteristicas", "metadatos", "COLUMNA_RENDIMIENTO", "regla de clase",
                  "ENTRADAS", "entradas disponibles", "N_CARACTERISTICAS", "entradas del modelo final",
                  "FAMILIAS_PRUEBA", "modelo", "aciertos en prueba", "aciertos en validación",
                  "referencia en validación"],
    "valor": [time.strftime("%Y-%m-%d %H:%M", time.gmtime()), ARCHIVO_CARACTERISTICAS, ARCHIVO_METADATOS,
              COLUMNA_RENDIMIENTO, "signo positivo = Alto, signo negativo = Bajo",
              ENTRADAS, ", ".join(entradas), N_CARACTERISTICAS, ", ".join(usadas_final),
              ", ".join(sorted(nombres_prueba)), "regresión logística, clases equilibradas",
              f"{aciertos_pru} de {n_pru}", f"{aciertos_val} de {len(validacion)}",
              f"{aciertos_referencia} de {len(validacion)} (decir siempre {clase_comun})"],
})
with pd.ExcelWriter(ARCHIVO_CLASIFICACION, engine="openpyxl") as libro:
    hoja_datos.to_excel(libro, sheet_name="datos", index=False)
    analisis.to_excel(libro, sheet_name="correlaciones", index_label="entrada")
    validacion.to_excel(libro, sheet_name="validacion", index=False)
    resultado_prueba.to_excel(libro, sheet_name="prueba", index=False)
    hoja_confusion.to_excel(libro, sheet_name="confusion", index=False)
    hoja_parametros.to_excel(libro, sheet_name="parametros", index=False)
    for hoja in libro.sheets.values():
        hoja.freeze_panes = "B2"
        for celda in hoja[1]:
            celda.font = Font(bold=True)
        for columna in hoja.columns:
            mas_largo = max(len(str(celda.value)) for celda in columna if celda.value is not None)
            hoja.column_dimensions[columna[0].column_letter].width = min(mas_largo + 3, 60)

# ---- 4. Descargar ----
ARCHIVO_ENTREGA = "clasificacion_rendimiento.zip"
with zipfile.ZipFile(ARCHIVO_ENTREGA, "w") as z:
    z.write(ARCHIVO_CLASIFICACION)
    z.write("tabla_de_confusion.png")
print()
print("Entregable:", ARCHIVO_ENTREGA)
print("  · " + ARCHIVO_CLASIFICACION + "   (datos, correlaciones, predicciones, confusión y parámetros)")
print("  · tabla_de_confusion.png")
files.download(ARCHIVO_ENTREGA)

## Celda 58 (markdown)

---

## Tarea para la próxima sesión

### Reto 1: la entrada tramposa
En el paso 21, haz doble clic sobre la celda y agrega la columna del rendimiento
a los metadatos de entrada:

    METADATOS_DE_ENTRADA = ["Weight_50K", "Weight_AllK", "All_Kernels", "Yield-media(yield)"]

En el paso 24 escribe `N_CARACTERISTICAS = 1` y vuelve a ejecutar del paso 21 al
26.
- ¿Qué entrada eligió el modelo y con qué correlación? ¿Cuántas acertó en la
  validación y en la prueba?
- Es un resultado casi perfecto. ¿Por qué no vale?
- Aun con la respuesta en la mano, el modelo falla una familia en la
  validación. Búscala en la tabla del paso 25: ¿qué tiene de particular su valor
  de rendimiento?
- El cuaderno te avisó en el paso 21. En un proyecto real nadie avisa: ¿cómo
  reconocerías una entrada que trae escondida la respuesta?

Al terminar, deja la lista y `N_CARACTERISTICAS` como estaban.

### Reto 2: ¿cuánto vale acertar en cuatro?
En el paso 22 escribe `FAMILIAS_PRUEBA = []` para que el cuaderno sortee las
familias de prueba. Ejecuta del paso 22 al 26 con `SEMILLA` igual a 1, 2, 3, 4 y
5, y anota los aciertos en la prueba y en la validación de cada sorteo.
- ¿El resultado de la prueba se mantiene o cambia de un sorteo a otro? ¿Y el de
  la validación?
- Si solo hubieras hecho el sorteo que mejor salió, ¿qué habrías concluido? ¿Y
  con el que peor salió?
- Ningún ajuste del cuaderno arregla esto. ¿Qué haría falta para que el
  resultado dejara de depender del sorteo?

### Reto 3: de la familia a la mazorca
En la tabla `datos` cada familia tiene sus medidas de imagen y los datos de su
mazorca en la misma fila. Agrega esta celda al final y ejecútala:

    datos.plot.scatter(x="area_mm2", y="Weight_50K")
    print(datos[["area_mm2", "Weight_50K"]].corr().round(2))

- Cada punto es una familia. ¿Las familias de granos más grandes tienen granos
  más pesados?
- `Weight_50K` es el peso de 50 granos. ¿Qué otra medida de la imagen probarías
  en lugar de `area_mm2`, y por qué?
- Si la relación fuera muy clara, ¿se podría estimar el peso de un grano solo
  con su fotografía? ¿Qué tendrías que medir para comprobarlo?
