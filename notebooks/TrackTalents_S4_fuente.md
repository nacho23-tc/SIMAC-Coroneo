# Fuentes S4, sin ejecutar ni copiar salidas

## Celda 0 (markdown)

# De medir granos a predecir el rendimiento
**Track Talents · Sesión 4 (segmentación con red neuronal) · cierre de la serie**

La sesión pasada terminó con un clasificador de regresión logística y una
pregunta incómoda: ¿acertaba más que quien responde siempre la clase más común?
Hoy cambiamos de modelo, una **máquina de soporte vectorial** (SVM) con cuatro
kernels distintos, y cada quien arma su propio clasificador: elige las medidas,
el kernel y sus ajustes, lo revisa en entrenamiento y lo enfrenta a las imágenes
de prueba.

**Este es el mismo cuaderno de la semana pasada, con más pasos abajo:**

| Pasos | Qué hacen | Qué entregan |
|---|---|---|
| 1 a 11 | De la imagen a la tabla de granos | Imagen numerada y tabla de granos |
| 12 a 15 | La unión grano a grano de la sesión 2. **Hoy no se usan** | — |
| 16 a 19 | Promedio por familia y lote de imágenes | **Excel 1:** `caracteristicas_por_familia.xlsx` |
| 20 a 26 | Clasificación con regresión logística (sesión 3) | **Excel 2:** `clasificacion_rendimiento.xlsx` |
| 27 a 38 | **Nuevo:** SVM con cuatro kernels; tu modelo frente a las imágenes de prueba | **Excel 3:** `svm_kernels.xlsx` y las figuras |

**Dos formas de trabajar hoy:**

- **Con el Excel 1 y los metadatos (la de hoy):** ve directo al paso 27. No
  necesita instalar la red ni activar la GPU. Para el paso 37 necesitarás las
  cuatro imágenes de prueba.
- **Con imágenes:** ejecuta las celdas en orden con `Shift + Enter`. En el paso 38
  puedes clasificar familias nuevas, pero antes sus imágenes tienen que pasar por
  los pasos 17 a 19.

En los pasos 13, 14, 16 y 33 el código se muestra completo; en los demás,
aparece con doble clic sobre la celda.

**Antes de empezar:** ve a *Archivo → Guardar una copia en Drive*.

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

COLUMNA_ID = "nombre_nuevo"  # columna de los metadatos que identifica la muestra
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
NOMBRE_EXCEL = "caracteristicas_por_familia"  #@param {type:"string"}
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
if not NOMBRE_EXCEL.strip():                         # vacío: el nombre de siempre
    NOMBRE_EXCEL = "caracteristicas_por_familia"
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
SUBIR_CARACTERISTICAS = False  #@param {type:"boolean"}
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
METADATOS_DE_ENTRADA = ["Weight_50K", "Weight_AllK", "All_Kernels"]
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
columnas_hoja = list(dict.fromkeys(["familia", COLUMNA_RENDIMIENTO, "clase"] + entradas))
hoja_datos = pd.concat([entrenamiento[columnas_hoja].assign(conjunto="entrenamiento"),
                        prueba[columnas_hoja].assign(conjunto="prueba")], ignore_index=True)
hoja_datos.insert(1, "conjunto", hoja_datos.pop("conjunto"))
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
# Sesión 4. Un pasillo entre dos clases
La regresión logística del paso 25 funcionaba como una balanza. Una **máquina de
soporte vectorial** (SVM, por sus siglas en inglés) piensa distinto: busca el
**pasillo más ancho** que separa las familias `Alto` de las `Bajo`. Y con un
**kernel** puede doblar ese pasillo cuando una recta no alcanza. Hoy se prueban
cuatro: **lineal, polinomial, radial y sigmoide**.

| Paso | Qué hace |
|---|---|
| 27 | Sube los datos: Excel 1 y `metadatosTT.xlsx` completo |
| 28 | Saca las familias que contaminan los datos |
| 29 | Define la clase con la mediana del rendimiento |
| 30 | Elige la prueba (al menos 2 y 2), balancea el entrenamiento y confirma |
| 31 | La idea de la SVM, en un plano: el pasillo más ancho |
| 32 | Cuatro kernels, cuatro formas de frontera |
| 33 | Compara los cuatro kernels en entrenamiento |
| 34 | Experimento: mover `C`, `γ` y el grado |
| 35 | El examen dentro del examen: una sugerencia de kernel |
| 36 | **Arma tu modelo** y mira su tabla de confusión de entrenamiento |
| 37 | **Abre el sobre:** tu modelo frente a las imágenes de prueba |
| 38 | Clasifica familias nuevas y descarga todo |

Los pasos 36 y 37 se usan juntos: cambia las medidas o los ajustes en el 36,
mira el entrenamiento, pásalo por la prueba del 37 y anota el resultado en la
bitácora, hasta quedarte con el mejor modelo.

**Se puede empezar aquí.** Basta con el Excel 1 y los metadatos.

## Celda 59 (markdown)

## Paso 27. Subir los datos
Igual que en el paso 20: una tabla con lo que dice la imagen (el **Excel 1**, hoja
`familias`) y otra con lo que se sabe de la planta y la mazorca. Hoy son los
metadatos **completos**, `metadatosTT.xlsx`. La llave que las une es el nombre de
la familia: `Grano_06.jpg` en los metadatos y `Grano_06` en el Excel 1 son la
misma familia.

**Las columnas amarillas.** En `metadatosTT.xlsx` hay columnas marcadas en
amarillo: `Yield`, `Yield-media(yield)`, `Weight_50K`, `Weight_AllK` y
`All_Kernels`. Son el rendimiento o están hechas de sus mismos componentes: darían
pistas demasiado claras. La celda las detecta por su color y **ninguna entra al
modelo como medida**. `Yield` se usa una sola vez, en el paso 29, para definir la
clase.

- Si en esta sesión ya ejecutaste el paso 19 o el 20, se usa esa tabla de la
  imagen. Marca `SUBIR_ARCHIVOS` para subir otros archivos.
- El cuaderno pide primero el Excel 1 y después `metadatosTT.xlsx`.
- `COLUMNA_FAMILIA` es la columna de los metadatos con el nombre de la imagen.

**Qué debe aparecer:** cuántas familias tiene cada tabla, cuántas quedaron en las
dos y cuáles columnas son amarillas.

## Celda 60 (code)

#@title ▶ Subir los datos
SUBIR_ARCHIVOS = False  #@param {type:"boolean"}
COLUMNA_FAMILIA = "nombre_imagen"  #@param {type:"string"}

# Lo necesario para poder empezar en este paso, sin haber ejecutado los anteriores
import os
import re
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import files

warnings.filterwarnings("ignore", module="sklearn")    # avisos internos que no cambian el resultado

if "MEDIDAS" not in globals():          # las mismas definiciones del paso 16
    MEDIDAS = ["largo_mm", "ancho_mm", "area_mm2", "perimetro_mm",
               "razon_aspecto", "circularidad", "solidez", "L", "a", "b"]

    def nombre_familia(archivo):
        """'carpeta/Grano_06 (1).jpg' -> 'Grano_06': sin carpeta, sin extensión y sin '(1)'."""
        nombre = os.path.splitext(os.path.basename(str(archivo)))[0]
        return re.sub(r"\s*\(\d+\)$", "", nombre).strip()

# Lo que usan todos los pasos de hoy
CLASES = ["Alto", "Bajo"]
COLOR = {"Alto": "#eb6834", "Bajo": "#2a78d6"}     # naranja y azul: se distinguen con daltonismo
MARCA = {"Alto": "o", "Bajo": "s"}                  # y además cambia la forma del punto
TINTA, GRIS, ERROR = "#22262B", "#A3A7AD", "#B33A21"
KERNELS = ["linear", "poly", "rbf", "sigmoid"]
NOMBRE_KERNEL = {"linear": "lineal", "poly": "polinomial", "rbf": "radial (RBF)", "sigmoid": "sigmoide"}
CARPETA_FIGURAS = "figuras_s4"
os.makedirs(CARPETA_FIGURAS, exist_ok=True)


def requiere(*nombres, paso):
    """Detiene la celda con un mensaje claro si falta ejecutar un paso anterior."""
    faltan = [n for n in nombres if n not in globals()]
    if faltan:
        raise RuntimeError(f"Antes de esta celda hay que ejecutar el paso {paso} "
                           f"(falta: {', '.join(faltan)}). Ejecuta las celdas en orden desde el paso 27.")


def subir_uno(mensaje):
    print(mensaje)
    subidos = list(files.upload().keys())
    if not subidos:
        raise RuntimeError("No se subió ningún archivo. Vuelve a ejecutar la celda y elige uno.")
    return subidos[0]


def guardar_figura(fig, nombre):
    fig.savefig(os.path.join(CARPETA_FIGURAS, nombre), dpi=130, bbox_inches="tight")


AMARILLAS_DE_SIEMPRE = ["Yield", "Yield-media(yield)", "Weight_50K", "Weight_AllK", "All_Kernels"]


def columnas_amarillas(archivo):
    """Los encabezados con relleno amarillo en la primera hoja del Excel (None si no se puede saber)."""
    if not str(archivo).lower().endswith((".xlsx", ".xlsm")):
        return None
    from openpyxl import load_workbook
    hoja = load_workbook(archivo).worksheets[0]
    encontradas = []
    for celda in hoja[1]:
        color = celda.fill.fgColor.rgb if celda.fill is not None and celda.fill.fill_type else None
        if isinstance(color, str) and len(color) >= 6 and celda.value is not None:
            r, g, b = (int(color[-6:][i:i + 2], 16) for i in (0, 2, 4))
            if r > 200 and g > 180 and b < 215 and r - b > 30:      # amarillo: rojo y verde altos, azul bajo
                encontradas.append(str(celda.value).strip())
    return encontradas


# ---- 1. Lo que dice la imagen: características por familia (Excel 1) ----
if not SUBIR_ARCHIVOS and "tabla_imagen" in globals():
    print("Características: la tabla del paso 20, que ya está en memoria")
elif not SUBIR_ARCHIVOS and "familias" in globals():
    ARCHIVO_CARACTERISTICAS = "tabla del paso 19 (en memoria)"
    tabla_imagen = familias.reset_index()
else:
    ARCHIVO_CARACTERISTICAS = subir_uno("Sube el Excel 1, el de características por familia (paso 19):")
    try:
        tabla_imagen = pd.read_excel(ARCHIVO_CARACTERISTICAS, sheet_name="familias")
    except ValueError:
        raise ValueError(f"'{ARCHIVO_CARACTERISTICAS}' no tiene la hoja 'familias'. "
                         "Sube el Excel que descarga el paso 19.") from None
if "familia" not in tabla_imagen.columns:
    raise KeyError("El Excel 1 no tiene la columna 'familia'. Sube el Excel que descarga el paso 19.")
tabla_imagen["familia"] = tabla_imagen["familia"].map(nombre_familia)

# ---- 2. Lo que se sabe de la planta y la mazorca: metadatosTT completo ----
if not SUBIR_ARCHIVOS and "metadatos_tt" in globals():
    print("Metadatos: los que ya subiste en este paso")
else:
    ARCHIVO_METADATOS = subir_uno("Sube los metadatos completos (metadatosTT.xlsx):")
    if ARCHIVO_METADATOS.lower().endswith(".csv"):
        metadatos_tt = pd.read_csv(ARCHIVO_METADATOS, encoding="utf-8-sig")
    else:
        metadatos_tt = pd.read_excel(ARCHIVO_METADATOS)
    COLUMNAS_AMARILLAS = columnas_amarillas(ARCHIVO_METADATOS)
    if not COLUMNAS_AMARILLAS:
        print("ℹ️  No se pudieron leer los colores del archivo: se toman como amarillas las de siempre.")
        COLUMNAS_AMARILLAS = list(AMARILLAS_DE_SIEMPRE)
metadatos_tt.columns = [str(c).strip() for c in metadatos_tt.columns]
if COLUMNA_FAMILIA not in metadatos_tt.columns:
    otras = [c for c in ["nombre_imagen", "nombre_nuevo", "imagen", "archivo"] if c in metadatos_tt.columns]
    if not otras:
        raise KeyError(f"Los metadatos no tienen la columna '{COLUMNA_FAMILIA}'. Columnas que sí hay: "
                       f"{list(metadatos_tt.columns)}. Escribe la correcta en COLUMNA_FAMILIA.")
    print(f"ℹ️  Los metadatos no tienen '{COLUMNA_FAMILIA}'; se usa '{otras[0]}'.")
    COLUMNA_FAMILIA = otras[0]
metadatos_tt = metadatos_tt.dropna(subset=[COLUMNA_FAMILIA]).dropna(axis=1, how="all")
metadatos_tt = metadatos_tt.loc[:, [not c.startswith("Unnamed") for c in metadatos_tt.columns]]
metadatos_tt["familia"] = metadatos_tt[COLUMNA_FAMILIA].map(nombre_familia)

for nombre_tabla, tabla_revisada in [("el Excel 1", tabla_imagen), ("los metadatos", metadatos_tt)]:
    repetidas = sorted(set(tabla_revisada["familia"][tabla_revisada["familia"].duplicated()]))
    if repetidas:
        raise ValueError(f"En {nombre_tabla} hay familias repetidas: {repetidas}. "
                         "Cada familia debe aparecer una sola vez.")

# ---- 3. Unir: una fila por familia en las dos tablas ----
metadatos_sin_llave = metadatos_tt.drop(columns=[COLUMNA_FAMILIA])
metadatos_sin_llave = metadatos_sin_llave.drop(
    columns=[c for c in metadatos_sin_llave.columns if c != "familia" and c in tabla_imagen.columns])
datos_unidos = tabla_imagen.merge(metadatos_sin_llave, on="familia", how="inner", validate="one_to_one")
datos = datos_unidos.copy()

solo_imagen = sorted(set(tabla_imagen["familia"]) - set(metadatos_tt["familia"]))
solo_metadatos = sorted(set(metadatos_tt["familia"]) - set(tabla_imagen["familia"]))
print()
print(f"Familias con imagen:     {len(tabla_imagen)}   ({globals().get('ARCHIVO_CARACTERISTICAS', 'en memoria')})")
print(f"Familias con metadatos:  {len(metadatos_tt)}   ({globals().get('ARCHIVO_METADATOS', 'en memoria')})")
print(f"Familias en las dos:     {len(datos_unidos)}")
if solo_imagen:
    print("⚠️  Con imagen pero sin metadatos (no entran):", solo_imagen)
if solo_metadatos:
    print("⚠️  Con metadatos pero sin imagen (no entran):", solo_metadatos)
print(f"Columnas amarillas (nunca entran como medidas): {', '.join(COLUMNAS_AMARILLAS)}")
display(datos_unidos.head(5))

## Celda 61 (markdown)

## Paso 28. Sacar las familias que contaminan los datos
Un promedio vale lo que valen los granos que promedia. Antes de definir clases o
entrenar, salen las familias cuya imagen no se midió bien. Hay dos razones para
sacar una familia:

- **Una razón que conocemos:** `FAMILIAS_EXCLUIDAS` es la lista de familias que se
  sacan a mano. **Grano_05** es de grano rojo y su segmentación no salió bien: sus
  medidas no describen sus granos.
- **Una señal en los datos:** una familia con muchos menos granos que las demás
  probablemente tuvo un recorte fallido (como Grano_14 en el paso 19).
  `MIN_GRANOS_RELATIVO` fija el mínimo como fracción del conteo típico: con `0.5`,
  una familia necesita al menos la mitad de los granos de una familia típica.

**Qué debe aparecer:** las familias que salen, con el motivo y sus medidas de
forma junto al rango de las demás, y cuántas familias quedan.

## Celda 62 (code)

#@title ▶ Sacar las familias que contaminan los datos
FAMILIAS_EXCLUIDAS = ["Grano_05"]  #@param {type:"raw"}
MIN_GRANOS_RELATIVO = 0.5  #@param {type:"slider", min:0, max:1, step:0.05}

requiere("datos_unidos", paso=27)
datos = datos_unidos.copy()            # siempre parte de la tabla del paso 27
motivos = {}

# ---- 1. Las que se sacan a mano ----
for familia in [nombre_familia(f) for f in FAMILIAS_EXCLUIDAS]:
    if familia not in set(datos["familia"]):
        print(f"⚠️  {familia} está en FAMILIAS_EXCLUIDAS pero no en los datos: se ignora.")
    else:
        motivos[familia] = "excluida a mano (FAMILIAS_EXCLUIDAS)"

# ---- 2. Las que tienen pocos granos ----
granos_tipicos = None
if "n_granos" in datos.columns:
    datos["n_granos"] = pd.to_numeric(datos["n_granos"], errors="coerce")
    granos_tipicos = datos.loc[~datos["familia"].isin(motivos), "n_granos"].median()
    granos_minimos = MIN_GRANOS_RELATIVO * granos_tipicos
    for familia in datos.loc[datos["n_granos"] < granos_minimos, "familia"]:
        motivos.setdefault(familia, f"pocos granos (menos de {granos_minimos:.0f})")
    print(f"Granos por familia: típico {granos_tipicos:.0f}. Mínimo para entrar: {granos_minimos:.0f} "
          f"({MIN_GRANOS_RELATIVO:.0%} del típico).")
else:
    print("⚠️  El Excel 1 no trae la columna 'n_granos': no se revisa el conteo.")

excluidas = list(motivos)
salen = datos["familia"].isin(excluidas)
if excluidas:
    forma = [c for c in ["n_granos", "circularidad", "solidez", "area_mm2", "L", "a"] if c in datos.columns]
    tabla_excluidas = datos.loc[salen, ["familia"] + forma].copy()
    tabla_excluidas.insert(1, "motivo", tabla_excluidas["familia"].map(motivos))
    rango = datos.loc[~salen, forma].agg(["min", "max"]).round(3)
    rango.insert(0, "motivo", "")
    rango.insert(0, "familia", ["las demás: mínimo", "las demás: máximo"])
    print(f"Salen {len(excluidas)} familias:")
    display(pd.concat([tabla_excluidas.round(3), rango], ignore_index=True))
else:
    tabla_excluidas = pd.DataFrame(columns=["familia", "motivo"])
    print("✅ No sale ninguna familia.")

datos = datos[~salen].reset_index(drop=True)
datos_limpios = datos.copy()
print(f"Familias que entran a los análisis: {len(datos_limpios)}")

## Celda 63 (markdown)

## Paso 29. Definir la clase con la mediana
En la sesión 3 la clase salió del signo de una columna precalculada. Hoy sale
directamente del rendimiento medido, `Yield`, y de su **mediana**: el valor que
deja la mitad de las familias arriba y la mitad abajo. `Yield` es amarilla: se
usa aquí para poner la etiqueta y nunca como medida de entrada.

La columna `Class` de los metadatos **no se usa**: es la etiqueta de la sesión 3
(que resultó invertida) y, como es la respuesta, tampoco puede ser una entrada.

- **`Alto`:** la familia rinde **más** que la mediana.
- **`Bajo`:** rinde la mediana o menos.

¿Por qué la mediana y no el promedio?

- **Clases parejas.** Por definición, la mitad de las familias queda de cada lado.
  Con clases parejas, decir siempre lo mismo ya no da un buen resultado de
  regalo.
- **Resiste a los extremos.** Una familia con un rendimiento muy alto mueve el
  promedio, pero no la mediana.

La mediana se calcula **solo con las familias que entraron** en el paso 28: si
una familia mal medida participara, movería la frontera entre las clases.

**Qué debe aparecer:** la mediana, cuántas familias hay de cada clase y una
gráfica con el rendimiento de cada familia.

## Celda 64 (code)

#@title ▶ Definir la clase con la mediana
COLUMNA_RENDIMIENTO = "Yield"  #@param {type:"string"}

requiere("datos_limpios", paso=28)
datos = datos_limpios.copy()           # siempre parte de la tabla del paso 28
if COLUMNA_RENDIMIENTO not in datos.columns:
    raise KeyError(f"No existe la columna '{COLUMNA_RENDIMIENTO}'. Columnas: {list(datos.columns)}")
datos[COLUMNA_RENDIMIENTO] = pd.to_numeric(datos[COLUMNA_RENDIMIENTO], errors="coerce")
sin_dato = datos[COLUMNA_RENDIMIENTO].isna()
if sin_dato.any():
    print(f"⚠️  Sin valor en '{COLUMNA_RENDIMIENTO}' (no entran): {list(datos.loc[sin_dato, 'familia'])}")
    datos = datos[~sin_dato].reset_index(drop=True)

mediana_rendimiento = datos[COLUMNA_RENDIMIENTO].median()
datos["clase"] = np.where(datos[COLUMNA_RENDIMIENTO] > mediana_rendimiento, "Alto", "Bajo")
conteo = datos["clase"].value_counts().reindex(CLASES, fill_value=0)

print(f"Familias: {len(datos)}")
print(f"Mediana de {COLUMNA_RENDIMIENTO}: {mediana_rendimiento:.4f}")
print(f"Alto (más que la mediana): {conteo['Alto']}   Bajo (la mediana o menos): {conteo['Bajo']}")

# Si el archivo trae la columna de la sesión 3, se compara con la regla de entonces
if "Yield-media(yield)" in datos.columns:
    regla_s3 = np.where(pd.to_numeric(datos["Yield-media(yield)"], errors="coerce") > 0, "Alto", "Bajo")
    print(f"Comparada con la regla del paso 21, cambian de clase {int((regla_s3 != datos['clase']).sum())} "
          f"de {len(datos)} familias.")

# El segundo testigo: la física (más granos por mazorca, más rendimiento)
if "All_Kernels" in datos.columns:
    r_granos = datos[COLUMNA_RENDIMIENTO].corr(pd.to_numeric(datos["All_Kernels"], errors="coerce"))
    print(f"Correlación entre {COLUMNA_RENDIMIENTO} y All_Kernels (granos por mazorca): {r_granos:+.2f}")

# Gráfica: cada punto es una familia, sin nombre
orden = datos.sort_values(COLUMNA_RENDIMIENTO).reset_index(drop=True)
fig, ax = plt.subplots(figsize=(9, 2.8))
for c in CLASES:
    sub = orden[orden["clase"] == c]
    ax.scatter(sub[COLUMNA_RENDIMIENTO], np.zeros(len(sub)), s=110, color=COLOR[c], marker=MARCA[c],
               edgecolor="white", linewidth=1.2, label=f"{c} ({len(sub)})", zorder=3)
ax.axvline(mediana_rendimiento, color=TINTA, linestyle="--", linewidth=1)
ax.annotate(f"mediana = {mediana_rendimiento:.3f}", (mediana_rendimiento, 0.6), xytext=(5, 0),
            textcoords="offset points", fontsize=9, color=TINTA)
ax.set_yticks([])
ax.set_ylim(-1, 1)
ax.set_xlabel(f"{COLUMNA_RENDIMIENTO} (rendimiento medido)")
ax.set_title("Cada punto es una familia: la mediana deja la mitad de cada lado")
for lado in ["left", "right", "top"]:
    ax.spines[lado].set_visible(False)
ax.legend(loc="upper left", fontsize=8, ncol=2)
plt.tight_layout()
guardar_figura(fig, "29_clase_con_mediana.png")
plt.show()

datos_con_clase = datos.copy()

## Celda 65 (markdown)

## Paso 30. Elegir la prueba, balancear el entrenamiento y confirmar
Antes de entrenar nada, el cuaderno deja por escrito **con qué imágenes se
entrena** y **cuáles son las de prueba**. Las de prueba no se usan para nada hasta
el paso 37: ni para entrenar, ni para normalizar, ni para elegir medidas.

**1. La prueba: al menos 2 y 2.** Una prueba solo dice algo si trae familias de
las dos clases. La celda primero muestra qué familias hay de cada clase, para que
elijas. `FAMILIAS_PRUEBA` trae las mismas cuatro de la sesión 3; puedes cambiarlas
o agregar más, siempre que haya al menos `MINIMO_POR_CLASE` de cada clase. Si no
se cumple, la celda se detiene y te dice cuáles puedes agregar. Con la lista
vacía, `[]`, el cuaderno sortea `MINIMO_POR_CLASE` de cada clase con `SEMILLA`.

**2. El entrenamiento: balanceado.** Al sacar a Grano_05, que era `Alto`, el
entrenamiento quedó con una familia `Bajo` de más. Si una clase tiene más familias,
el modelo se inclina hacia ella. Con `BALANCEAR_ENTRENAMIENTO`, sale del
entrenamiento la familia de la clase que sobra **más cercana a la mediana**: es la
de etiqueta más dudosa, porque rinde casi lo mismo que la frontera entre las
clases. Si prefieres sacar otra, escríbela en `FAMILIAS_PARA_BALANCEAR`.

- `ENTRADAS`: con qué trabajan los pasos 31 a 35. En el paso 36 eliges las
  medidas una por una.
- **Qué metadatos entran:** todas las columnas numéricas de `metadatosTT.xlsx`
  que **no** son amarillas, ni la etiqueta (`Class`), ni datos del archivo (`Row`,
  `filas_origen`, y `ancho` y `alto`, que son el tamaño de la imagen en píxeles).
- **Posibles pistas:** que una columna no sea amarilla no garantiza que no dé
  pistas. La celda calcula la correlación de cada entrada con `Yield` en las
  familias de entrenamiento y marca las que pasan de `UMBRAL_PISTA`. No las
  quita: tú decides en el paso 36 si dejarlas.

**Qué debe aparecer:** las familias de cada clase, la confirmación con el número y
el nombre de las imágenes de entrenamiento y de prueba, la familia que salió para
balancear, la revisión de que la prueba tiene al menos 2 y 2, y las medidas que
entran con sus posibles pistas.

## Celda 66 (code)

#@title ▶ Elegir la prueba, balancear el entrenamiento y confirmar
ENTRADAS = "imagen + metadatos"  #@param ["imagen + metadatos", "solo imagen", "solo metadatos"]
FAMILIAS_PRUEBA = ["Grano_01", "Grano_02", "Grano_04", "Grano_06"]  #@param {type:"raw"}
MINIMO_POR_CLASE = 2  #@param {type:"integer"}
BALANCEAR_ENTRENAMIENTO = True  #@param {type:"boolean"}
FAMILIAS_PARA_BALANCEAR = []  #@param {type:"raw"}
SEMILLA = 42  #@param {type:"integer"}
UMBRAL_PISTA = 0.6  #@param {type:"slider", min:0.3, max:0.9, step:0.05}

requiere("datos_con_clase", "excluidas", "COLUMNAS_AMARILLAS", paso=29)
datos = datos_con_clase.copy()         # siempre parte de la tabla del paso 29
# Columnas que SON la respuesta: nunca deben estar entre las entradas
RESPUESTAS = [COLUMNA_RENDIMIENTO, "Yield", "Yield-media(yield)", "Class", "clase"]
# Columnas que no son medidas de la familia: identificadores y datos del archivo
NO_SON_MEDIDAS = ["Row", "filas_origen", "ancho", "alto", "n_granos", "familia", COLUMNA_FAMILIA]
fuera_de_entradas = set(COLUMNAS_AMARILLAS) | set(RESPUESTAS) | set(NO_SON_MEDIDAS) | set(MEDIDAS)
METADATOS_DE_ENTRADA = [c for c in metadatos_tt.columns if c in datos.columns and c not in fuera_de_entradas
                        and pd.to_numeric(datos[c], errors="coerce").notna().mean() >= 0.8]

ENTRADAS_IMAGEN = [c for c in MEDIDAS if c in datos.columns]
ENTRADAS_METADATOS = list(METADATOS_DE_ENTRADA)
OPCIONES_ENTRADAS = {"imagen + metadatos": ENTRADAS_IMAGEN + ENTRADAS_METADATOS,
                     "solo imagen": ENTRADAS_IMAGEN,
                     "solo metadatos": ENTRADAS_METADATOS}
entradas = OPCIONES_ENTRADAS[ENTRADAS]
if not entradas:
    raise ValueError("No quedó ninguna entrada. Revisa ENTRADAS y METADATOS_DE_ENTRADA.")
numericas = ENTRADAS_IMAGEN + ENTRADAS_METADATOS
datos[numericas] = datos[numericas].apply(pd.to_numeric, errors="coerce")
tramposas = [c for c in entradas if c in RESPUESTAS]
if tramposas:
    print(f"🚫 {tramposas} es la respuesta y está entre las entradas: el modelo copiaría, no predeciría.")
MINIMO_POR_CLASE = max(1, int(MINIMO_POR_CLASE))


def lista(nombres, por_renglon=6):
    nombres = sorted(nombres)
    return "\n".join("   " + ", ".join(nombres[i:i + por_renglon]) for i in range(0, len(nombres), por_renglon))


# ---- 1. Para elegir la prueba: qué familias hay de cada clase ----
por_clase = {c: sorted(datos.loc[datos["clase"] == c, "familia"]) for c in CLASES}
print(f"Familias disponibles (elige al menos {MINIMO_POR_CLASE} de cada clase para la prueba):")
for c in CLASES:
    print(f" {c} ({len(por_clase[c])}):")
    print(lista(por_clase[c]))
print()

if FAMILIAS_PRUEBA:
    nombres_prueba = list(dict.fromkeys(nombre_familia(f) for f in FAMILIAS_PRUEBA))
    fuera = [f for f in nombres_prueba if f in excluidas]
    if fuera:
        raise ValueError(f"{fuera} salieron en el paso 28 y no pueden ser de prueba. Cambia FAMILIAS_PRUEBA.")
    no_existen = [f for f in nombres_prueba if f not in set(datos["familia"])]
    if no_existen:
        raise ValueError(f"Estas familias de prueba no están en la tabla: {no_existen}. "
                         f"Las que hay: {list(datos['familia'])}")
else:
    if (datos["clase"].value_counts().reindex(CLASES, fill_value=0) < MINIMO_POR_CLASE + 2).any():
        raise ValueError("No hay suficientes familias de cada clase para sortear la prueba y entrenar.")
    nombres_prueba = list(datos.groupby("clase").sample(n=MINIMO_POR_CLASE, random_state=SEMILLA)["familia"])
    print(f"Sorteo con semilla {SEMILLA}: {', '.join(sorted(nombres_prueba))}")

es_prueba = datos["familia"].isin(nombres_prueba)
en_prueba = datos.loc[es_prueba, "clase"].value_counts().reindex(CLASES, fill_value=0)
faltan = {c: MINIMO_POR_CLASE - en_prueba[c] for c in CLASES if en_prueba[c] < MINIMO_POR_CLASE}
if faltan:
    sugerencias = "; ".join(f"agrega {n} de {c}: " + ", ".join(f for f in por_clase[c] if f not in nombres_prueba)
                            for c, n in faltan.items())
    raise ValueError(f"La prueba necesita al menos {MINIMO_POR_CLASE} de cada clase y tiene "
                     f"Alto: {en_prueba['Alto']}, Bajo: {en_prueba['Bajo']}. En FAMILIAS_PRUEBA, {sugerencias}.")

# ---- 2. Balancear el entrenamiento ----
entrenamiento = datos[~es_prueba].reset_index(drop=True)
para_balancear = []
cuenta = entrenamiento["clase"].value_counts().reindex(CLASES, fill_value=0)
if BALANCEAR_ENTRENAMIENTO and cuenta.max() > cuenta.min():
    sobra, exceso = cuenta.idxmax(), int(cuenta.max() - cuenta.min())
    if FAMILIAS_PARA_BALANCEAR:
        para_balancear = list(dict.fromkeys(nombre_familia(f) for f in FAMILIAS_PARA_BALANCEAR))
        malas = [f for f in para_balancear if f not in set(entrenamiento.loc[entrenamiento["clase"] == sobra, "familia"])]
        if malas:
            raise ValueError(f"{malas} no son familias '{sobra}' de entrenamiento. Para balancear tiene que salir "
                             f"{'una' if exceso == 1 else exceso} de: {', '.join(sorted(entrenamiento.loc[entrenamiento['clase'] == sobra, 'familia']))}")
        if len(para_balancear) != exceso:
            print(f"⚠️  Para quedar parejos tienen que salir {exceso}; en FAMILIAS_PARA_BALANCEAR hay {len(para_balancear)}.")
    else:
        candidatas = entrenamiento[entrenamiento["clase"] == sobra].copy()
        candidatas["distancia"] = (candidatas[COLUMNA_RENDIMIENTO] - mediana_rendimiento).abs()
        para_balancear = list(candidatas.sort_values("distancia")["familia"].iloc[:exceso])
tabla_balanceo = entrenamiento.loc[entrenamiento["familia"].isin(para_balancear),
                                   ["familia", "clase", COLUMNA_RENDIMIENTO]].reset_index(drop=True)
entrenamiento = entrenamiento[~entrenamiento["familia"].isin(para_balancear)].reset_index(drop=True)
prueba = datos[es_prueba].reset_index(drop=True)
en_entrenamiento = entrenamiento["clase"].value_counts().reindex(CLASES, fill_value=0)
if (en_entrenamiento < 3).any():
    raise ValueError("En entrenamiento deben quedar al menos 3 familias de cada clase. "
                     f"Quedaron: {en_entrenamiento.to_dict()}. Pon menos familias en FAMILIAS_PRUEBA.")

X_ent, y_ent = entrenamiento[entradas], entrenamiento["clase"].to_numpy()
X_pru, y_pru = prueba[entradas], prueba["clase"].to_numpy()

# ---- 3. La confirmación ----
print("CONFIRMACIÓN")
print(f"Familias que entran: {len(datos)}" + (f"   (salieron en el paso 28: {', '.join(excluidas)})" if excluidas else ""))
print()
parejo = en_entrenamiento["Alto"] == en_entrenamiento["Bajo"]
print(f"ENTRENAMIENTO: {len(entrenamiento)} imágenes   (Alto: {en_entrenamiento['Alto']}, Bajo: {en_entrenamiento['Bajo']})"
      + ("   ✅ balanceado" if parejo else "   ⚠️  no está balanceado"))
print(lista(entrenamiento["familia"]))
for _, fila in tabla_balanceo.iterrows():
    print(f"   Sale para balancear: {fila['familia']} ({fila['clase']}, {COLUMNA_RENDIMIENTO} "
          f"{fila[COLUMNA_RENDIMIENTO]:.4f}; mediana {mediana_rendimiento:.4f})")
print()
print(f"PRUEBA: {len(prueba)} imágenes   (Alto: {en_prueba['Alto']}, Bajo: {en_prueba['Bajo']})"
      f"   ✅ al menos {MINIMO_POR_CLASE} y {MINIMO_POR_CLASE}")
for c in CLASES:
    print(f"   {c}: {', '.join(sorted(prueba.loc[prueba['clase'] == c, 'familia']))}")
print("   El modelo no las verá hasta el paso 37.")
print()
print(f"Columnas amarillas, fuera: {', '.join(COLUMNAS_AMARILLAS)}")
print(f"Entradas para los pasos 31 a 35 ({ENTRADAS}): {len(entradas)}")
print("   de la imagen:    ", ", ".join(c for c in entradas if c in ENTRADAS_IMAGEN) or "ninguna")
print("   de los metadatos:", ", ".join(c for c in entradas if c not in ENTRADAS_IMAGEN) or "ninguna")

# ---- 4. Posibles pistas: entradas que se parecen demasiado al rendimiento ----
todas_las_medidas = ENTRADAS_IMAGEN + ENTRADAS_METADATOS
parecido = entrenamiento[todas_las_medidas].corrwith(entrenamiento[COLUMNA_RENDIMIENTO]).dropna()
pistas = parecido[parecido.abs() >= UMBRAL_PISTA].sort_values(key=abs, ascending=False)
print()
if len(pistas):
    print(f"⚠️  Posibles pistas (correlación con {COLUMNA_RENDIMIENTO} de {UMBRAL_PISTA} o más, en entrenamiento):")
    for columna, r in pistas.items():
        print(f"   {columna:<22} r = {r:+.2f}")
    print("   No son amarillas, pero se parecen mucho al rendimiento. Decide en el paso 36 si las dejas.")
else:
    print(f"✅ Ninguna entrada tiene correlación de {UMBRAL_PISTA} o más con {COLUMNA_RENDIMIENTO}.")
if not tramposas and not set(prueba["familia"]) & set(entrenamiento["familia"]):
    print()
    print(f"✅ Confirmado: se entrena con {len(entrenamiento)} imágenes y se prueba con {len(prueba)} que el modelo no verá.")
display(entrenamiento[["familia", COLUMNA_RENDIMIENTO, "clase"]].sort_values("familia").reset_index(drop=True))

## Celda 67 (markdown)

## Paso 31. La idea: el pasillo más ancho
Imagina cada familia como un punto en un plano, con dos medidas normalizadas como
ejes. Las `Alto` quedan, más o menos, de un lado y las `Bajo` del otro. Muchas
rectas las separan. ¿Cuál escoger?

La **máquina de soporte vectorial** escoge la recta que deja el **pasillo más
ancho** entre los dos grupos. La razón: si una familia nueva cae un poco corrida
respecto a las que conoce, un pasillo ancho le da más margen antes de quedar del
lado equivocado.

Tres palabras para el resto de la sesión:

- **Frontera:** la línea a la mitad del pasillo. De un lado dice `Alto`; del
  otro, `Bajo`.
- **Vectores de soporte:** las familias que tocan los bordes del pasillo o se
  meten en él. **Solo ellas definen la frontera.** Puedes mover o borrar cualquier
  otra familia y el pasillo no cambia: se apoya únicamente en ellas, y de ahí el
  nombre.
- **`C`:** cuánto cuesta que una familia se meta en el pasillo o quede del lado
  equivocado. Con `C` grande, el modelo no tolera errores y el pasillo se
  angosta. Con `C` chico, acepta algunos errores a cambio de un pasillo ancho.

Para poder dibujarlo se usan solo dos medidas: las que mejor separan las clases
en entrenamiento (o las que escribas en `EJE_X` y `EJE_Y`). Con más medidas la
idea es la misma, pero el pasillo vive en más dimensiones.

**Qué debe aparecer:** el plano con la frontera (línea continua), los bordes del
pasillo (punteadas) y los vectores de soporte dentro de un círculo. Prueba
`C_PASILLO` en `0.01` y en `100`: ¿qué le pasa al ancho del pasillo y al número
de vectores de soporte?

## Celda 68 (code)

#@title ▶ El pasillo más ancho
C_PASILLO = 1  #@param [0.01, 0.1, 1, 10, 100] {type:"raw"}
EJE_X = ""  #@param {type:"string"}
EJE_Y = ""  #@param {type:"string"}

from sklearn.svm import SVC
from sklearn.feature_selection import f_classif

requiere("X_ent", "y_ent", paso=30)
if len(entradas) < 2:
    raise ValueError("Para dibujar el pasillo hacen falta dos entradas. Elige otra opción de ENTRADAS en el paso 30.")

# Qué tanto separa cada medida las dos clases, solo con entrenamiento (la idea del paso 24)
separacion, _ = f_classif(X_ent.fillna(X_ent.mean()), y_ent)
orden_separacion = pd.Series(np.nan_to_num(separacion), index=entradas).sort_values(ascending=False)
eje_x = EJE_X.strip() or orden_separacion.index[0]
eje_y = EJE_Y.strip() or [c for c in orden_separacion.index if c != eje_x][0]
for eje in (eje_x, eje_y):
    if eje not in entradas:
        raise ValueError(f"'{eje}' no está entre las entradas: {entradas}")
EJES = [eje_x, eje_y]
media_2d = entrenamiento[EJES].mean()
desv_2d = entrenamiento[EJES].std().replace(0, 1)


def en_el_plano(tabla):
    """Las dos medidas de los ejes, normalizadas con la media y la desviación de ENTRENAMIENTO."""
    return ((tabla[EJES] - media_2d) / desv_2d).fillna(0).to_numpy()


def dibujar_frontera(ax, modelo, Z, clases, titulo):
    """Fondo: el lado de cada clase. Línea continua: la frontera. Punteadas: los bordes del
    pasillo. Círculo: vector de soporte."""
    lim = max(3.0, float(np.abs(Z).max()) + 0.6)
    xx, yy = np.meshgrid(np.linspace(-lim, lim, 300), np.linspace(-lim, lim, 300))
    f = modelo.decision_function(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
    negativa, positiva = modelo.classes_            # la frontera es f = 0; positivo = classes_[1]
    ax.contourf(xx, yy, f, levels=[-1e9, 0, 1e9], colors=[COLOR[negativa], COLOR[positiva]], alpha=0.12)
    ax.contour(xx, yy, f, levels=[-1, 0, 1], colors=TINTA, linestyles=["--", "-", "--"],
               linewidths=[1, 2, 1])
    for c in CLASES:
        m = clases == c
        ax.scatter(Z[m, 0], Z[m, 1], s=65, color=COLOR[c], marker=MARCA[c], edgecolor="white",
                   linewidth=1.2, label=c, zorder=3)
    sv = modelo.support_vectors_
    ax.scatter(sv[:, 0], sv[:, 1], s=240, facecolors="none", edgecolors=TINTA, linewidths=1.2,
               label="vector de soporte", zorder=4)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel(EJES[0] + " (normalizada)")
    ax.set_ylabel(EJES[1] + " (normalizada)")
    ax.set_title(titulo, fontsize=10)


Z_ent_2d = en_el_plano(entrenamiento)
pasillo = SVC(kernel="linear", C=C_PASILLO, class_weight="balanced").fit(Z_ent_2d, y_ent)
ancho_pasillo = 2 / np.linalg.norm(pasillo.coef_)
aciertos_2d = int((pasillo.predict(Z_ent_2d) == y_ent).sum())

fig, ax = plt.subplots(figsize=(7.5, 6))
dibujar_frontera(ax, pasillo, Z_ent_2d, y_ent,
                 f"Kernel lineal · C = {C_PASILLO} · pasillo de {ancho_pasillo:.2f} desviaciones")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
plt.tight_layout()
guardar_figura(fig, "31_pasillo.png")
plt.show()

print(f"Ejes: {eje_x} y {eje_y}" + ("" if EJE_X or EJE_Y else "  (las que mejor separan las clases en entrenamiento)"))
print(f"Ancho del pasillo:   {ancho_pasillo:.2f} desviaciones")
print(f"Vectores de soporte: {len(pasillo.support_)} de {len(y_ent)} familias. Solo ellas sostienen la frontera.")
print(f"Aciertos en entrenamiento, con estas dos medidas: {aciertos_2d} de {len(y_ent)}")

## Celda 69 (markdown)

## Paso 32. Cuatro kernels, cuatro formas de frontera
¿Y si ninguna recta separa bien? La SVM tiene un truco: mira las familias en un
espacio con más dimensiones, donde un plano sí podría separarlas, y regresa con
una frontera que aquí se ve curva. Lo notable es que nunca construye ese
espacio: le basta con saber **qué tan parecidas son dos familias**. La fórmula
que mide ese parecido es el **kernel**.

| Kernel | Cómo mide el parecido | Qué frontera permite | Ajustes |
|---|---|---|---|
| **Lineal** | Producto punto: cuánto apuntan dos familias en la misma dirección | Recta (un plano, con más medidas) | `C` |
| **Polinomial** | El producto punto elevado a una potencia, el **grado** | Curvas suaves que combinan medidas, como área × circularidad | `C`, `γ`, grado |
| **Radial (RBF)** | Una campana alrededor de cada familia: el parecido cae con la distancia | Islas y contornos cerrados | `C`, `γ` |
| **Sigmoide** | La tangente hiperbólica del producto punto, como una neurona | Fronteras en forma de S | `C`, `γ` |

`γ` (gamma) controla hasta dónde llega la influencia de cada familia: con `γ`
grande, cada familia es una isla. El sigmoide no siempre cumple las condiciones
matemáticas de un kernel, y por eso a veces se comporta de forma extraña.

**Qué debe aparecer:** el plano del paso 31 resuelto por los cuatro kernels, con
el mismo `C_PASILLO`. Fíjate en la **forma** de cada frontera y en cuántas
familias acierta cada uno.

## Celda 70 (code)

#@title ▶ Los cuatro kernels en el mismo plano
requiere("Z_ent_2d", "dibujar_frontera", paso=31)

fig, ejes_kernel = plt.subplots(1, 4, figsize=(19, 5))
filas_2d = []
for ax, kernel in zip(ejes_kernel, KERNELS):
    modelo_2d = SVC(kernel=kernel, C=C_PASILLO, gamma="scale", degree=3,
                    class_weight="balanced").fit(Z_ent_2d, y_ent)
    aciertos = int((modelo_2d.predict(Z_ent_2d) == y_ent).sum())
    dibujar_frontera(ax, modelo_2d, Z_ent_2d, y_ent,
                     f"{NOMBRE_KERNEL[kernel]}\n{aciertos} de {len(y_ent)} aciertos · "
                     f"{len(modelo_2d.support_)} vectores de soporte")
    filas_2d.append({"kernel": NOMBRE_KERNEL[kernel], "aciertos_en_entrenamiento": aciertos,
                     "vectores_de_soporte": len(modelo_2d.support_)})
ejes_kernel[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
fig.suptitle(f"Las mismas {len(y_ent)} familias y las mismas dos medidas · C = {C_PASILLO}", fontsize=11)
plt.tight_layout()
guardar_figura(fig, "32_cuatro_kernels.png")
plt.show()
display(pd.DataFrame(filas_2d))

## Celda 71 (markdown)

## Paso 33. Comparar los cuatro kernels en entrenamiento
Ahora con todas las entradas del paso 30. Para cada kernel se cuentan dos cosas,
como en el paso 25:

- **Al entrenar:** el modelo aprende de las familias de entrenamiento y se le
  pregunta por esas mismas familias. Es un examen con las respuestas a la vista:
  sirve para ver si el modelo es capaz de separarlas, no si sabe predecir.
- **Dejando una pareja fuera:** se esconden juntas una familia `Alto` y una
  `Bajo`, el modelo aprende de las demás y predice las dos escondidas. Se repite
  con todas las parejas posibles. Ninguna predicción viene de un modelo que haya
  visto a esa familia.

¿Por qué una pareja y no una sola, como en el paso 25? Porque el entrenamiento
está balanceado. Si se escondiera una sola familia, su clase quedaría en minoría
entre las demás, y un modelo que casi no aprendió nada podría acertar siempre
diciendo "la clase que falta". Con una pareja, las dos clases siguen parejas en
cada turno.

Todo lo que el modelo aprende viaja junto en un **`Pipeline`**: rellenar datos
vacíos, normalizar (paso 23), elegir las `N_CARACTERISTICAS` medidas que más
separan las clases (paso 24) y la SVM. En cada turno el `Pipeline` completo se
vuelve a ajustar sin la pareja escondida, para que ni la normalización ni la
elección de medidas la hayan visto.

**La referencia:** quien dice siempre lo mismo acierta exactamente una de cada
pareja, es decir, el 50 %.

El código está a la vista: es la idea nueva de la sesión.

## Celda 72 (code)

# Paso 33. Comparar los cuatro kernels en entrenamiento
N_CARACTERISTICAS = 3     # medidas que elige el modelo (en la sesión 3 era 1)
C_COMPARAR = 1            # el C de los cuatro kernels; 1 es el valor que trae scikit-learn

from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.svm import SVC
from sklearn.model_selection import cross_val_score

requiere("X_ent", "y_ent", paso=30)


def nueva_svm(kernel, C=1.0, gamma="scale", grado=3, n_caracteristicas=None):
    """Todo lo que el modelo aprende, en orden. Se ajusta de nuevo cada vez que se esconde una pareja."""
    pasos = [("rellenar", SimpleImputer(strategy="mean")),          # dato vacío -> la media
             ("normalizar", StandardScaler())]                       # paso 23
    if n_caracteristicas:
        pasos.append(("elegir", SelectKBest(f_classif, k=n_caracteristicas)))   # paso 24
    pasos.append(("svm", SVC(kernel=kernel, C=C, gamma=gamma, degree=grado, class_weight="balanced")))
    return Pipeline(pasos)


def parejas(y):
    """Todas las parejas de una familia Alto y una Bajo: (las que aprenden, las dos que se esconden)."""
    y = np.asarray(y)
    todas = np.arange(len(y))
    for i in np.where(y == "Alto")[0]:
        for j in np.where(y == "Bajo")[0]:
            yield np.setdiff1d(todas, [i, j]), np.array([i, j])


def aciertos_por_parejas(modelo, X, y):
    """Fracción de aciertos sobre las familias escondidas, pareja por pareja."""
    return cross_val_score(modelo, X, np.asarray(y), cv=list(parejas(y)), scoring="accuracy", n_jobs=-1).mean()


k_medidas = min(N_CARACTERISTICAS, len(entradas))
n_parejas = len(list(parejas(y_ent)))
filas_kernels = []
for kernel in KERNELS:
    modelo = nueva_svm(kernel, C_COMPARAR, n_caracteristicas=k_medidas)
    al_entrenar = modelo.fit(X_ent, y_ent).predict(X_ent)
    filas_kernels.append({
        "kernel": NOMBRE_KERNEL[kernel],
        "aciertos_al_entrenar": f"{int((al_entrenar == y_ent).sum())} de {len(y_ent)}",
        "dejando_una_pareja_fuera_%": round(100 * aciertos_por_parejas(modelo, X_ent, y_ent)),
        "vectores_de_soporte": int(modelo[-1].n_support_.sum()),
    })
comparacion_kernels = pd.DataFrame(filas_kernels)
display(comparacion_kernels)
print(f"Parejas escondidas por kernel: {n_parejas}. Referencia: decir siempre lo mismo acierta el 50 %.")
if k_medidas:
    print(f"Con todas las familias de entrenamiento, las {k_medidas} medidas que elige el modelo son: "
          + ", ".join(str(c) for c in np.array(entradas)[modelo.named_steps["elegir"].get_support()]))

## Celda 73 (markdown)

## Paso 34. Experimento: mover `C`, `γ` y el grado
Elige un kernel y mueve **un ajuste a la vez**. Cada vez que ejecutes la celda
verás el pasillo en el plano de los pasos 31 y 32, los aciertos al entrenar y
dejando una pareja fuera, y una bitácora con todas tus pruebas.

| Ajuste | Prueba | Qué observar |
|---|---|---|
| `C_EXPERIMENTO` | de 0.01 a 1000 | ¿Qué pasa con los aciertos al entrenar y qué con los de dejando una pareja fuera? |
| `GAMMA_EXPERIMENTO` (radial, polinomial y sigmoide) | de 0.01 a 10 | ¿Cuándo aparecen las islas? |
| `GRADO_EXPERIMENTO` (polinomial) | de 2 a 5 | ¿Más grado es mejor? |

## Celda 74 (code)

#@title ▶ Experimento: mover C, γ y el grado
KERNEL_EXPERIMENTO = "rbf"  #@param ["linear", "poly", "rbf", "sigmoid"]
C_EXPERIMENTO = 1  #@param [0.01, 0.1, 1, 10, 100, 1000] {type:"raw"}
GAMMA_EXPERIMENTO = "scale"  #@param ["scale", "0.01", "0.1", "1", "10"]
GRADO_EXPERIMENTO = 3  #@param [2, 3, 4, 5] {type:"raw"}

requiere("nueva_svm", "aciertos_por_parejas", "k_medidas", paso=33)
requiere("Z_ent_2d", "dibujar_frontera", paso=31)
gamma = GAMMA_EXPERIMENTO if GAMMA_EXPERIMENTO == "scale" else float(GAMMA_EXPERIMENTO)

modelo_exp = nueva_svm(KERNEL_EXPERIMENTO, C_EXPERIMENTO, gamma, GRADO_EXPERIMENTO, k_medidas)
al_entrenar_exp = int((modelo_exp.fit(X_ent, y_ent).predict(X_ent) == y_ent).sum())
fuera_exp = aciertos_por_parejas(modelo_exp, X_ent, y_ent)

if "bitacora_experimento" not in globals():
    bitacora_experimento = []
bitacora_experimento.append({
    "kernel": NOMBRE_KERNEL[KERNEL_EXPERIMENTO], "C": C_EXPERIMENTO, "gamma": GAMMA_EXPERIMENTO,
    "grado": GRADO_EXPERIMENTO if KERNEL_EXPERIMENTO == "poly" else "",
    "entradas": ENTRADAS,
    "aciertos_al_entrenar": f"{al_entrenar_exp} de {len(y_ent)}",
    "dejando_una_pareja_fuera_%": round(100 * fuera_exp),
})

modelo_exp_2d = SVC(kernel=KERNEL_EXPERIMENTO, C=C_EXPERIMENTO, gamma=gamma, degree=GRADO_EXPERIMENTO,
                    class_weight="balanced").fit(Z_ent_2d, y_ent)
fig, ax = plt.subplots(figsize=(7.5, 6))
dibujar_frontera(ax, modelo_exp_2d, Z_ent_2d, y_ent,
                 f"{NOMBRE_KERNEL[KERNEL_EXPERIMENTO]} · C = {C_EXPERIMENTO} · γ = {GAMMA_EXPERIMENTO}"
                 + (f" · grado {GRADO_EXPERIMENTO}" if KERNEL_EXPERIMENTO == "poly" else ""))
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
plt.tight_layout()
guardar_figura(fig, f"34_experimento_{len(bitacora_experimento):02d}.png")
plt.show()

print(f"Aciertos al entrenar:        {al_entrenar_exp} de {len(y_ent)}")
print(f"Dejando una pareja fuera:     {fuera_exp:.0%}   (decir siempre lo mismo: 50 %)")
print()
print("Bitácora de tus pruebas:")
display(pd.DataFrame(bitacora_experimento))

## Celda 75 (markdown)

## Paso 35. El examen dentro del examen: una sugerencia de kernel
En los pasos 33 y 34 se compararon configuraciones con el mismo examen y se miró
cuál salía mejor. Con pocas familias, la mejor de muchas sale alta en parte por
suerte, como quedarse con la moneda que más águilas dio.

Una forma de elegir sin esa suerte: cada vez que se esconde una pareja, con las
demás familias se hace un **examen interno** que prueba los cuatro kernels con
tres valores de `C` y elige la mejor combinación; esa combinación predice la
pareja escondida, que no participó en la elección. El resultado mide el procedimiento
completo, "elegir y entrenar", y dice cuántas veces se eligió cada kernel.

Con `COMPARAR_ENTRADAS` marcado, repite todo para las tres opciones de entradas:
**¿la imagen aporta algo que los metadatos no traen?** Al final da una sugerencia
de kernel y `C` para probar en el paso 36.

## Celda 76 (code)

#@title ▶ El examen dentro del examen
COMPARAR_ENTRADAS = True  #@param {type:"boolean"}
VALORES_C = [0.1, 1, 10]

from collections import Counter
from sklearn.model_selection import GridSearchCV, StratifiedKFold
requiere("nueva_svm", "parejas", "k_medidas", paso=33)


def procedimiento(y_disponible, n_entradas):
    """Elige kernel y C con un examen interno que solo usa las familias que recibe."""
    clase_menor = int(pd.Series(y_disponible).value_counts().min())
    interno = StratifiedKFold(n_splits=max(2, min(3, clase_menor)), shuffle=True, random_state=SEMILLA)
    return GridSearchCV(nueva_svm("linear", n_caracteristicas=min(N_CARACTERISTICAS, n_entradas)),
                        {"svm__kernel": KERNELS, "svm__C": VALORES_C},
                        cv=interno, scoring="balanced_accuracy")


def evaluar_procedimiento(columnas):
    """Una pareja fuera por fuera; la elección de kernel y C, por dentro."""
    X = entrenamiento[columnas]
    buenos, total, elecciones = 0, 0, Counter()
    for aprende, examina in parejas(y_ent):
        eleccion = procedimiento(y_ent[aprende], len(columnas)).fit(X.iloc[aprende], y_ent[aprende])
        buenos += int((eleccion.predict(X.iloc[examina]) == y_ent[examina]).sum())
        total += len(examina)
        elecciones[f"{NOMBRE_KERNEL[eleccion.best_params_['svm__kernel']]}, C = {eleccion.best_params_['svm__C']}"] += 1
    return buenos / total, elecciones


opciones = list(OPCIONES_ENTRADAS) if COMPARAR_ENTRADAS else [ENTRADAS]
filas_sugerencia = []
for opcion in opciones:
    columnas = OPCIONES_ENTRADAS[opcion]
    if not columnas:
        continue
    acierta, elecciones = evaluar_procedimiento(columnas)
    mas_elegida, veces = elecciones.most_common(1)[0]
    filas_sugerencia.append({
        "entradas": opcion + ("  ← la del paso 30" if opcion == ENTRADAS else ""),
        "dejando_una_pareja_fuera_%": round(100 * acierta),
        "eleccion_mas_frecuente": f"{mas_elegida} ({veces} de {sum(elecciones.values())})",
    })
    print(f"   listo: {opcion}")
sugerencia = pd.DataFrame(filas_sugerencia)
display(sugerencia)

eleccion_final = procedimiento(y_ent, len(entradas)).fit(X_ent, y_ent)
kernel_sugerido = eleccion_final.best_params_["svm__kernel"]
C_sugerido = eleccion_final.best_params_["svm__C"]
print("Decir siempre lo mismo acierta el 50 %.")
print(f"Sugerencia para el paso 36 (entradas: {ENTRADAS}): kernel {NOMBRE_KERNEL[kernel_sugerido]} "
      f"(\"{kernel_sugerido}\"), C = {C_sugerido}")

## Celda 77 (markdown)

## Paso 36. Arma tu modelo
Aquí eliges **todo**: qué medidas entran (marca o desmarca cada una), el kernel y
sus ajustes. La celda entrena el modelo con las familias de entrenamiento y
muestra **su tabla de confusión de entrenamiento**: cuántas acierta de las
familias con las que aprendió. Las filas dicen qué era cada familia y las
columnas qué dijo el modelo; los aciertos están en la diagonal.

Debajo de la tabla aparecen también los aciertos **dejando una pareja fuera**
(paso 33): si al entrenar acierta todas pero dejando una pareja fuera no pasa del
50 %, el modelo memorizó en lugar de aprender.

Cada modelo que armes queda en la **bitácora de modelos** con un número. En el
paso 37 lo enfrentas a la prueba y su resultado se anota en la misma fila. Así
puedes comparar tus modelos en entrenamiento y en prueba y quedarte con el mejor.

Las columnas amarillas no aparecen en la lista: no pueden entrar.

Ideas para probar: solo las medidas de la imagen; solo los metadatos; sin las
posibles pistas del paso 30 (`WEIGHT_EAR`, `LENGTH_EAR`, `DIAMETER_EAR`); las
tres medidas que eligió el paso 33; el kernel y la `C` que sugirió el paso 35.

## Celda 78 (code)

#@title ▶ Arma tu modelo
#@markdown **Medidas de la imagen**
LARGO_MM = True  #@param {type:"boolean"}
ANCHO_MM = True  #@param {type:"boolean"}
AREA_MM2 = True  #@param {type:"boolean"}
PERIMETRO_MM = True  #@param {type:"boolean"}
RAZON_ASPECTO = True  #@param {type:"boolean"}
CIRCULARIDAD = True  #@param {type:"boolean"}
SOLIDEZ = True  #@param {type:"boolean"}
COLOR_L = True  #@param {type:"boolean"}
COLOR_A = True  #@param {type:"boolean"}
COLOR_B = True  #@param {type:"boolean"}
#@markdown **Metadatos de la planta y la mazorca (las columnas amarillas no están)**
DAYS_TO_ANTHESIS = True  #@param {type:"boolean"}
DAYS_TO_SILKING = True  #@param {type:"boolean"}
PLANT_HEIGHT = True  #@param {type:"boolean"}
EAR_HEIGHT = True  #@param {type:"boolean"}
TASSEL_BRANCH_NUMBER = True  #@param {type:"boolean"}
WEIGHT_EAR = True  #@param {type:"boolean"}
LENGTH_EAR = True  #@param {type:"boolean"}
DIAMETER_EAR = True  #@param {type:"boolean"}
NUMBER_ROWS = True  #@param {type:"boolean"}
KERNEL_ROW = True  #@param {type:"boolean"}
DIAMETER_COB = True  #@param {type:"boolean"}
#@markdown **El modelo**
KERNEL = "rbf"  #@param ["linear", "poly", "rbf", "sigmoid"]
C = 1  #@param [0.01, 0.1, 1, 10, 100, 1000] {type:"raw"}
GAMMA = "scale"  #@param ["scale", "0.01", "0.1", "1", "10"]
GRADO = 3  #@param [2, 3, 4, 5] {type:"raw"}

requiere("nueva_svm", "aciertos_por_parejas", paso=33)
if "dibujar_confusion" not in globals():           # la misma del paso 26
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

if "tabla_de_confusion" not in globals():          # la misma del paso 25
    from sklearn.metrics import confusion_matrix

    def tabla_de_confusion(real, predicha):
        """Filas: la clase real. Columnas: lo que dijo el modelo."""
        return pd.DataFrame(confusion_matrix(list(real), list(predicha), labels=CLASES),
                            index=["real " + c for c in CLASES],
                            columns=["predicha " + c for c in CLASES])

# ---- Las medidas que marcaste ----
casillas = {"largo_mm": LARGO_MM, "ancho_mm": ANCHO_MM, "area_mm2": AREA_MM2, "perimetro_mm": PERIMETRO_MM,
            "razon_aspecto": RAZON_ASPECTO, "circularidad": CIRCULARIDAD, "solidez": SOLIDEZ,
            "L": COLOR_L, "a": COLOR_A, "b": COLOR_B,
            "Days_to_anthesis": DAYS_TO_ANTHESIS, "Days_to_silking": DAYS_TO_SILKING,
            "Plant_Height": PLANT_HEIGHT, "Ear_Height": EAR_HEIGHT, "Tassel_branch_number": TASSEL_BRANCH_NUMBER,
            "Weight_Ear": WEIGHT_EAR, "Length_Ear": LENGTH_EAR, "Diameter_Ear": DIAMETER_EAR,
            "Number_Rows": NUMBER_ROWS, "Kernel_Row": KERNEL_ROW, "Diameter_Cob": DIAMETER_COB}
amarillas_marcadas = [c for c, marcada in casillas.items() if marcada and c in COLUMNAS_AMARILLAS]
if amarillas_marcadas:
    raise ValueError(f"{amarillas_marcadas} son columnas amarillas y no pueden entrar al modelo.")
columnas_elegidas = [c for c, marcada in casillas.items() if marcada and c in entrenamiento.columns]
no_estan = [c for c, marcada in casillas.items() if marcada and c not in entrenamiento.columns]
if no_estan:
    print("⚠️  Estas medidas no están en los datos y no entran:", no_estan)
if not columnas_elegidas:
    raise ValueError("Marca al menos una medida.")
gamma_elegida = GAMMA if GAMMA == "scale" else float(GAMMA)

# ---- Entrenar con las familias de entrenamiento ----
def armar_modelo(config):
    return nueva_svm(config["kernel"], config["C"], config["gamma"], config["grado"])

config_modelo = {"columnas": columnas_elegidas, "kernel": KERNEL, "C": C, "gamma": gamma_elegida, "grado": GRADO}
modelo_elegido = armar_modelo(config_modelo).fit(entrenamiento[columnas_elegidas], y_ent)
dijo_entrenamiento = modelo_elegido.predict(entrenamiento[columnas_elegidas])
aciertos_entrenamiento = int((dijo_entrenamiento == y_ent).sum())
aciertos_fuera = aciertos_por_parejas(armar_modelo(config_modelo), entrenamiento[columnas_elegidas], y_ent)
confusion_entrenamiento = tabla_de_confusion(y_ent, dijo_entrenamiento)

# ---- Bitácora de modelos ----
if "bitacora_modelos" not in globals():
    bitacora_modelos, configs_modelos = [], []
de_imagen = [c for c in columnas_elegidas if c in MEDIDAS]
de_metadatos = [c for c in columnas_elegidas if c not in MEDIDAS]
bitacora_modelos.append({
    "modelo": len(bitacora_modelos) + 1,
    "medidas": f"{len(de_imagen)} de imagen + {len(de_metadatos)} de metadatos",
    "cuales": ", ".join(columnas_elegidas),
    "kernel": NOMBRE_KERNEL[KERNEL], "C": C, "gamma": GAMMA, "grado": GRADO if KERNEL == "poly" else "",
    "entrenamiento": f"{aciertos_entrenamiento} de {len(y_ent)}",
    "una_pareja_fuera": f"{aciertos_fuera:.0%}",
    "prueba": "—",
    "armado_despues_de_ver_la_prueba": "sí" if globals().get("sobre_abierto") else "no",
})
configs_modelos.append(config_modelo)

fig, ax = plt.subplots(figsize=(4.8, 4.4))
dibujar_confusion(ax, confusion_entrenamiento,
                  f"ENTRENAMIENTO · modelo {len(bitacora_modelos)}\n"
                  f"{aciertos_entrenamiento} de {len(y_ent)} aciertos")
plt.tight_layout()
guardar_figura(fig, f"36_entrenamiento_modelo_{len(bitacora_modelos):02d}.png")
plt.show()

print(f"Modelo {len(bitacora_modelos)}: {NOMBRE_KERNEL[KERNEL]}, C = {C}, γ = {GAMMA}"
      + (f", grado {GRADO}" if KERNEL == "poly" else "") + f", {len(columnas_elegidas)} medidas")
print(f"   {', '.join(columnas_elegidas)}")
print(f"Aciertos al entrenar:         {aciertos_entrenamiento} de {len(y_ent)}")
print(f"Dejando una pareja fuera:     {aciertos_fuera:.0%}   (decir siempre lo mismo: 50 %)")
print(f"Vectores de soporte:          {int(modelo_elegido[-1].n_support_.sum())} de {len(y_ent)}")
print()
print("Bitácora de modelos (la prueba se llena en el paso 37):")
display(pd.DataFrame(bitacora_modelos).drop(columns=["cuales"]))

## Celda 79 (markdown)

## Paso 37. Abrir el sobre: tu modelo frente a las imágenes de prueba
Ahora sí: el modelo que armaste en el paso 36 ve por primera vez las cuatro
familias de prueba. Para cada una, la celda muestra **su imagen**, lo que dijo el
modelo, lo que era en realidad y su rendimiento.

La SVM da además la **distancia a la frontera**: una familia dentro del pasillo
(distancia menor que 1) es una predicción dudosa; una lejos de él, una predicción
firme.

**Las imágenes.** La celda las busca en este orden: las que ya subiste en esta
sesión (pasos 18 o 19, o una corrida anterior de esta celda), la carpeta que
escribas en `CARPETA_IMAGENES` y, si falta alguna, te pide subirla. Para una
carpeta de tu Drive, la ruta empieza con `/content/drive/MyDrive/`.

**Para elegir el mejor modelo:** regresa al paso 36, cambia medidas o ajustes y
vuelve a ejecutar el 36 y el 37. Cada resultado queda en la bitácora. Una
advertencia honesta: cada vez que eliges mirando la prueba, la prueba se vuelve
un poco menos ciega. La bitácora anota qué modelos armaste después de haberla
visto, para que lo tengas en cuenta al reportar tu resultado.

**Qué debe aparecer:** las cuatro imágenes con su predicción, la tabla de
confusión de la prueba, qué tan seguido el azar igualaría el resultado y la
bitácora actualizada.

## Celda 80 (code)

#@title ▶ Abrir el sobre: las imágenes de prueba
CARPETA_IMAGENES = ""  #@param {type:"string"}

from math import comb
from PIL import Image

requiere("modelo_elegido", "config_modelo", "bitacora_modelos", paso=36)
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")


def buscar_imagenes(buscadas):
    """La ruta de la imagen de cada familia buscada: primero lo que ya está en la sesión, luego la
    carpeta indicada y, si falta alguna, se pide subirla."""
    candidatas = list(globals().get("rutas_lote", []))
    candidatas += [n for n in os.listdir(".") if n.lower().endswith(EXTENSIONES_IMAGEN)]
    if CARPETA_IMAGENES.strip():
        carpeta = CARPETA_IMAGENES.strip()
        if carpeta.startswith("/content/drive") and not os.path.isdir("/content/drive/MyDrive"):
            from google.colab import drive
            drive.mount("/content/drive")
        if not os.path.isdir(carpeta):
            raise FileNotFoundError(f"No existe la carpeta '{carpeta}'. Ábrela en el panel de archivos, "
                                    "clic derecho -> Copiar ruta, y pégala en CARPETA_IMAGENES.")
        candidatas += [os.path.join(carpeta, n) for n in os.listdir(carpeta) if n.lower().endswith(EXTENSIONES_IMAGEN)]
    carpeta_control = globals().get("CARPETA_CONTROL", "control_lote")
    if os.path.isdir(carpeta_control):           # imágenes numeradas del paso 19, por si no está la original
        candidatas += [os.path.join(carpeta_control, n) for n in os.listdir(carpeta_control)]
    encontradas = {}
    for ruta in candidatas:
        familia = nombre_familia(ruta)
        if familia in buscadas and familia not in encontradas and os.path.isfile(ruta):
            encontradas[familia] = ruta
    faltan = [f for f in buscadas if f not in encontradas]
    if faltan:
        print(f"Sube las imágenes de: {', '.join(faltan)} (puedes elegir varias a la vez)")
        for nombre in files.upload().keys():
            if nombre_familia(nombre) in faltan:
                encontradas[nombre_familia(nombre)] = nombre
    return encontradas


def miniatura(ruta, lado=1400):
    """La imagen reducida, para mostrarla rápido aunque sea de escáner."""
    imagen = Image.open(ruta)
    imagen.draft("RGB", (imagen.width // 8, imagen.height // 8))      # lectura rápida de JPEG grandes
    imagen = imagen.convert("RGB")
    imagen.thumbnail((lado, lado))
    return np.asarray(imagen)


# ---- 1. Predecir las familias de prueba con el modelo del paso 36 ----
numero_modelo = len(bitacora_modelos)
columnas_modelo = config_modelo["columnas"]
dijo_prueba = modelo_elegido.predict(prueba[columnas_modelo])
distancia = np.abs(modelo_elegido.decision_function(prueba[columnas_modelo]))
resultado_prueba_svm = pd.DataFrame({
    "familia": prueba["familia"],
    "clase_predicha": dijo_prueba,
    "clase_real": y_pru,                                   # aquí se abre el sobre
    COLUMNA_RENDIMIENTO: prueba[COLUMNA_RENDIMIENTO].round(4),
    "distancia_a_la_frontera": np.round(distancia, 2),
    "dentro_del_pasillo": np.where(distancia < 1, "sí (dudosa)", "no"),
})
resultado_prueba_svm["acierto"] = np.where(resultado_prueba_svm["clase_real"] == resultado_prueba_svm["clase_predicha"], "sí", "no")
aciertos_pru_svm, n_pru = int((resultado_prueba_svm["acierto"] == "sí").sum()), len(resultado_prueba_svm)
sobre_abierto = True

# ---- 2. Las imágenes ----
rutas_prueba = buscar_imagenes(list(prueba["familia"]))
columnas_fig = min(4, n_pru)
filas_fig = int(np.ceil(n_pru / columnas_fig))
fig, ejes = plt.subplots(filas_fig, columnas_fig, figsize=(4.6 * columnas_fig, 4.2 * filas_fig), squeeze=False)
for ax, (_, fila) in zip(ejes.ravel(), resultado_prueba_svm.iterrows()):
    familia = fila["familia"]
    if familia in rutas_prueba:
        ax.imshow(miniatura(rutas_prueba[familia]))
    else:
        ax.text(0.5, 0.5, "imagen no disponible", ha="center", va="center", color=GRIS, transform=ax.transAxes)
    acerto = fila["acierto"] == "sí"
    marca = "✓" if acerto else "✗"
    ax.set_title(f"{familia}  {marca}\ndijo {fila['clase_predicha']} · era {fila['clase_real']} · "
                 f"{COLUMNA_RENDIMIENTO} {fila[COLUMNA_RENDIMIENTO]:.3f}",
                 fontsize=10, color=TINTA if acerto else ERROR)
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_edgecolor(TINTA if acerto else ERROR)
        lado.set_linewidth(1 if acerto else 3)
for ax in ejes.ravel()[n_pru:]:
    ax.axis("off")
fig.suptitle(f"PRUEBA · modelo {numero_modelo}: {aciertos_pru_svm} de {n_pru} aciertos", fontsize=12)
plt.tight_layout()
guardar_figura(fig, f"37_prueba_modelo_{numero_modelo:02d}.png")
plt.show()

# ---- 3. Tabla de confusión de la prueba y lo que haría el azar ----
confusion_prueba_svm = tabla_de_confusion(y_pru, dijo_prueba)
fig, ax = plt.subplots(figsize=(4.8, 4.4))
dibujar_confusion(ax, confusion_prueba_svm, f"PRUEBA · modelo {numero_modelo}\n{aciertos_pru_svm} de {n_pru} aciertos")
plt.tight_layout()
guardar_figura(fig, f"37_confusion_prueba_modelo_{numero_modelo:02d}.png")
plt.show()
display(resultado_prueba_svm)

azar_prueba = sum(comb(n_pru, k) for k in range(aciertos_pru_svm, n_pru + 1)) / 2 ** n_pru
cuantas = f"las {n_pru}" if aciertos_pru_svm == n_pru else f"{aciertos_pru_svm} o más de {n_pru}"
print(f"PRUEBA: {aciertos_pru_svm} de {n_pru}. Adivinando al azar, {cuantas} se aciertan el {azar_prueba:.0%} de las veces.")

# ---- 4. Bitácora ----
bitacora_modelos[-1]["prueba"] = f"{aciertos_pru_svm} de {n_pru}"
print()
print("Bitácora de modelos:")
display(pd.DataFrame(bitacora_modelos).drop(columns=["cuales"]))

## Celda 81 (markdown)

## Paso 38. Clasificar familias nuevas y descargar todo
El cierre de la serie: usar tu clasificador con familias de las que nadie le dio
el rendimiento.

- `MODELO`: el número del modelo de la bitácora que quieres usar. Con `0` se usa
  el último que armaste.
- Como la prueba ya se hizo, el modelo final aprende de las familias de
  entrenamiento **y** de prueba, con las medidas y los ajustes de ese modelo. La
  que salió para balancear se queda fuera, para que el modelo siga parejo. La
  celda dice cuánto acierta dejando una pareja fuera con todas ellas: esa es la
  confiabilidad que viaja con cada predicción.

Para clasificar familias nuevas, procesa sus imágenes con los pasos 17 a 19,
marca `SUBIR_NUEVAS` y sube su Excel 1. Si ese Excel no trae los metadatos, el
modelo se entrena solo con las medidas de la imagen.

**El Excel 3**, `svm_kernels.xlsx`, trae una hoja por paso y se descarga en un
`.zip` junto con todas las figuras de la sesión.

## Celda 82 (code)

#@title ▶ Clasificar familias nuevas y descargar todo
MODELO = 0  #@param {type:"integer"}
SUBIR_NUEVAS = False  #@param {type:"boolean"}
NOMBRE_ENTREGA = "svm_kernels"  #@param {type:"string"}

import time
import zipfile
from openpyxl.styles import Font

requiere("bitacora_modelos", "configs_modelos", paso=36)
numero = MODELO if MODELO > 0 else len(configs_modelos)
if not 1 <= numero <= len(configs_modelos):
    raise ValueError(f"No hay modelo {MODELO} en la bitácora: hay del 1 al {len(configs_modelos)}.")
config_final = configs_modelos[numero - 1]

usables = pd.concat([entrenamiento.assign(conjunto="entrenamiento"), prueba.assign(conjunto="prueba")],
                    ignore_index=True)
y_usables = usables["clase"].to_numpy()


def ajustar_y_confiar(columnas):
    """El modelo con las familias de entrenamiento y prueba, y cuánto acierta dejando una pareja fuera."""
    config = dict(config_final, columnas=columnas)
    acierta = aciertos_por_parejas(armar_modelo(config), usables[columnas], y_usables)
    return armar_modelo(config).fit(usables[columnas], y_usables), acierta


modelo_final, aciertos_final = ajustar_y_confiar(config_final["columnas"])
print(f"Modelo {numero}: {NOMBRE_KERNEL[config_final['kernel']]}, C = {config_final['C']}, "
      f"γ = {config_final['gamma']}, {len(config_final['columnas'])} medidas")
print(f"Con las {len(usables)} familias de entrenamiento y prueba, dejando una pareja fuera acierta "
      f"el {aciertos_final:.0%} (decir siempre lo mismo: 50 %).")

resultado_nuevas = None
if SUBIR_NUEVAS:
    archivo_nuevas = subir_uno("Sube el Excel 1 con las familias nuevas (hoja 'familias', paso 19):")
    try:
        nuevas = pd.read_excel(archivo_nuevas, sheet_name="familias")
    except ValueError:
        raise ValueError(f"'{archivo_nuevas}' no tiene la hoja 'familias'. Sube el Excel del paso 19.") from None
    nuevas["familia"] = nuevas["familia"].map(nombre_familia)
    columnas_nuevas = [c for c in config_final["columnas"] if c in nuevas.columns]
    faltan = [c for c in config_final["columnas"] if c not in nuevas.columns]
    if not columnas_nuevas:
        raise ValueError(f"Las familias nuevas no traen ninguna de las medidas del modelo {numero}: "
                         f"{config_final['columnas']}. Arma en el paso 36 un modelo con medidas de la imagen.")
    nuevas[columnas_nuevas] = nuevas[columnas_nuevas].apply(pd.to_numeric, errors="coerce")
    if faltan:
        print(f"⚠️  Las familias nuevas no traen {faltan}: el modelo se entrena solo con lo que sí traen.")
        modelo_nuevas, aciertos_nuevas = ajustar_y_confiar(columnas_nuevas)
        print(f"   Esa versión, dejando una pareja fuera, acierta el {aciertos_nuevas:.0%}.")
    else:
        modelo_nuevas, aciertos_nuevas = modelo_final, aciertos_final
    ya_conocidas = sorted(set(nuevas["familia"]) & set(usables["familia"]))
    dijo_nuevas = modelo_nuevas.predict(nuevas[columnas_nuevas])
    distancia_nuevas = np.abs(modelo_nuevas.decision_function(nuevas[columnas_nuevas]))
    avisos = pd.Series("", index=nuevas.index)
    if "n_granos" in nuevas.columns and granos_tipicos:
        pocas = pd.to_numeric(nuevas["n_granos"], errors="coerce") < MIN_GRANOS_RELATIVO * granos_tipicos
        avisos[pocas] = "pocos granos: no confiable"
    avisos[nuevas["familia"].isin(ya_conocidas)] = "ya la conocía"
    resultado_nuevas = pd.DataFrame({
        "familia": nuevas["familia"],
        "clase_predicha": dijo_nuevas,
        "distancia_a_la_frontera": np.round(distancia_nuevas, 2),
        "dentro_del_pasillo": np.where(distancia_nuevas < 1, "sí (dudosa)", "no"),
        "aviso": avisos.to_numpy(),
    })
    print(f"Confiabilidad: dejando una pareja fuera acierta el {aciertos_nuevas:.0%} "
          f"(decir siempre lo mismo: 50 %).")
    display(resultado_nuevas)
else:
    print("Sin familias nuevas: se entrega el resultado de la sesión.")
    print("Para clasificar las tuyas, procesa sus imágenes con los pasos 17 a 19 y marca SUBIR_NUEVAS.")

# ---- Excel 3 ----
if not NOMBRE_ENTREGA.strip():
    NOMBRE_ENTREGA = "svm_kernels"
ARCHIVO_SVM = NOMBRE_ENTREGA.strip() + ".xlsx"
columnas_datos = [c for c in dict.fromkeys(["familia", "conjunto", COLUMNA_RENDIMIENTO, "clase", "n_granos"]
                                           + MEDIDAS + list(globals().get("METADATOS_DE_ENTRADA", [])))
                  if c in usables.columns]
hoja_parametros = pd.DataFrame({
    "parametro": ["fecha_utc", "caracteristicas", "metadatos", "familias excluidas", "MIN_GRANOS_RELATIVO",
                  "regla de clase", "mediana", "FAMILIAS_PRUEBA", "fuera para balancear",
                  "familias de entrenamiento",
                  "ENTRADAS (pasos 31 a 35)", "N_CARACTERISTICAS (paso 33)", "modelo final",
                  "medidas del modelo final", "aciertos dejando una pareja fuera (entrenamiento y prueba)"],
    "valor": [time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
              globals().get("ARCHIVO_CARACTERISTICAS", "en memoria"),
              globals().get("ARCHIVO_METADATOS", "en memoria"),
              ", ".join(f"{f} ({m})" for f, m in motivos.items()) or "ninguna", MIN_GRANOS_RELATIVO,
              f"Alto = {COLUMNA_RENDIMIENTO} > mediana", round(mediana_rendimiento, 4),
              ", ".join(sorted(nombres_prueba)), ", ".join(para_balancear) or "ninguna",
              ", ".join(sorted(entrenamiento["familia"])),
              ENTRADAS, N_CARACTERISTICAS,
              f"modelo {numero}: {NOMBRE_KERNEL[config_final['kernel']]}, C = {config_final['C']}, "
              f"gamma = {config_final['gamma']}, grado = {config_final['grado']}",
              ", ".join(config_final["columnas"]), f"{aciertos_final:.0%}"],
})
hojas = {
    "datos": usables[columnas_datos],
    "excluidas": tabla_excluidas,
    "balanceo": globals().get("tabla_balanceo"),
    "kernels": globals().get("comparacion_kernels"),
    "experimento": pd.DataFrame(globals().get("bitacora_experimento", [])),
    "sugerencia": globals().get("sugerencia"),
    "modelos": pd.DataFrame(bitacora_modelos),
    "prueba": globals().get("resultado_prueba_svm"),
    "nuevas": resultado_nuevas,
    "parametros": hoja_parametros,
}
with pd.ExcelWriter(ARCHIVO_SVM, engine="openpyxl") as libro:
    for nombre_hoja, tabla in hojas.items():
        if tabla is None or len(tabla) == 0:
            continue
        tabla.to_excel(libro, sheet_name=nombre_hoja, index=False)
    for hoja in libro.sheets.values():
        hoja.freeze_panes = "B2"
        for celda in hoja[1]:
            celda.font = Font(bold=True)
        for columna in hoja.columns:
            mas_largo = max(len(str(celda.value)) for celda in columna if celda.value is not None)
            hoja.column_dimensions[columna[0].column_letter].width = min(mas_largo + 3, 60)

ARCHIVO_ENTREGA_S4 = NOMBRE_ENTREGA.strip() + ".zip"
with zipfile.ZipFile(ARCHIVO_ENTREGA_S4, "w") as z:
    z.write(ARCHIVO_SVM)
    for nombre in sorted(os.listdir(CARPETA_FIGURAS)):
        z.write(os.path.join(CARPETA_FIGURAS, nombre))
print()
print("Entregable:", ARCHIVO_ENTREGA_S4)
print(f"  · {ARCHIVO_SVM}   (una hoja por paso)")
print(f"  · {len(os.listdir(CARPETA_FIGURAS))} figuras de la sesión")
files.download(ARCHIVO_ENTREGA_S4)

## Celda 83 (markdown)

---

## Cierre de la serie

| Sesión | Qué resolvió | La idea que se queda |
|---|---|---|
| 1 | Contar los granos de una imagen | Un umbral es una decisión, no un dato |
| 2 | Medir cada grano en milímetros | La escala sale de una referencia en la imagen |
| 3 | De granos a familias, y una primera clasificación | Un resultado solo vale frente a una referencia |
| 4 | Armar un clasificador y ponerlo a prueba | Antes de entrenar se limpian los datos; después, se compara entrenamiento con prueba |

## Tarea

### Reto 1: lo que nadie te avisa
Vuelve a ejecutar del paso 28 al 37 con cada uno de estos cambios, uno a la vez,
y regresa al valor original antes del siguiente:

- `FAMILIAS_EXCLUIDAS = []` (Grano_05 regresa);
- `MIN_GRANOS_RELATIVO = 0` (Grano_14 regresa);
- en el paso 36, desmarca las posibles pistas (`WEIGHT_EAR`, `LENGTH_EAR` y
  `DIAMETER_EAR`).

Para cada cambio: ¿cambian las clases del paso 29? ¿Cambia tu mejor modelo? ¿Cuál
de los tres errores habría pasado inadvertido en un proyecto real, donde ninguna
celda avisa?

### Reto 2: ¿cuánto vale acertar en cuatro?
En el paso 30 escribe `FAMILIAS_PRUEBA = []` para que el cuaderno sortee las
familias de prueba. Con tu mejor modelo, ejecuta del paso 30 al 37 con
`SEMILLA` igual a 1, 2, 3, 4 y 5, y anota los aciertos en la prueba y dejando una
pareja fuera.

- ¿Tu mejor modelo sigue siendo el mejor con otro sorteo?
- ¿Qué número cambia más de un sorteo a otro: el de la prueba o el de dejando una
  pareja fuera? ¿Por qué?
- ¿Qué haría falta para que la elección del modelo no dependiera del sorteo?

### Reto 3: tu proyecto final
Clasifica familias tuyas: procesa sus imágenes con los pasos 17 a 19 y llévalas
al paso 38. Escribe un párrafo de conclusión que diga con qué medidas, qué kernel
y qué ajustes, cuánto acertó tu modelo al entrenar, dejando una pareja fuera y en
la prueba, y qué necesitarías para creerle lo suficiente como para decidir qué
familia sembrar.