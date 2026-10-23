# SIMAC: SVM y peso aproximado

## Qué entrega esta versión

La sesión 4 está integrada como experimento de clasificación de familias Alto/Bajo. Se elige SVM lineal, polinomial, RBF o sigmoide; también se puede comparar con regresión logística. No se introduce una clase Medio: el notebook es binario y no hay umbrales ni ejemplos validados para una tercera clase. Estas etiquetas no son dictámenes de germinación o calidad para siembra.

En los resultados de cada fotografía hay tres bases de cálculo de peso:

1. **Escenario bibliográfico:** conteo aceptado × 0.283491–0.301028 g por grano. El rango procede de los pesos de mil granos publicados en *Studies on Physical Properties of Different Corn (Zea mays L.) Verities*, DOI 10.18805/ajdfr.DR-1991. El estudio incluye cinco variedades cultivadas en Maharashtra durante 2020–2021. No son datos de Coroneo ni un rango universal; tampoco es un intervalo de confianza. El estudio tiene diferencias entre cifras del resumen y discusión; usamos explícitamente el rango del resumen, sin inferir una distribución o un promedio medido. [Fuente primaria](https://arccjournals.com/journal/asian-journal-of-dairy-and-food-research/DR-1991).
2. **Referencia del lote:** el usuario pesa un número conocido de granos; SIMAC extrapola su promedio al conteo de la foto. Ejemplo ilustrativo: 50 granos pesan 15 g; una foto de 40 granos da 12 g aproximados. La incertidumbre depende de la representatividad de la referencia y no está cuantificada. No se estima peso individual a partir de tamaño en esta modalidad.
3. **Modelo propio:** una regresión Ridge predice peso medio por grano con largo, ancho y área medios calibrados. Se habilita cuando el usuario reúne pesajes reales, ejecuta el entrenamiento y guarda un modelo. Muestra el error de validación agrupada por lote; ese error no es un intervalo individual. La aproximación puede fallar fuera del rango de entrenamiento.

Hay investigaciones sobre estimación de peso con imágenes de maíz, pero sus ecuaciones no se trasladan sin validación a fotografías de granos de SIMAC. Referencia adicional: [Makanza et al., 2018, Plant Methods](https://link.springer.com/article/10.1186/s13007-018-0317-4).

## Reunir datos propios: procedimiento propuesto

Este es un protocolo piloto del proyecto, no una norma de certificación:

1. Separar muestras identificables por familia, lote y campaña. Evitar fotografiar el mismo grupo con nombres distintos para inflar la muestra.
2. Tarar el recipiente y pesar exactamente los granos que aparecerán en la foto. Usar una báscula con resolución adecuada; para grupos de unos 50 granos, procurar 0.01 g y anotar su resolución. Verificarla con una referencia conocida.
3. Fotografiar los granos separados y completos, con una referencia de longitud en el mismo plano. Mantener iluminación, distancia y fondo. Calibrar SIMAC en mm y revisar conteos/contornos.
4. En Peso, elegir Referencia pesada de mi lote, introducir peso en gramos, número pesado, lote/campaña y humedad medida si existe. No inventar humedad. Mantener condiciones de humedad comparables entre muestras; este modelo no corrige por humedad.
5. Confirmar la revisión y marcar que se pesaron exactamente los granos aceptados. Guardar. Si se excluyen o unen detecciones, comprobar de nuevo el conjunto y volver a confirmar el pesaje. Se conserva una firma de granos para rechazar pesajes asociados a un conjunto distinto.
6. El mínimo operativo del entrenamiento es 12 muestras de tres lotes distintos, una por familia activa. Como piloto conviene reunir 30–50 muestras variadas y después reservar nuevos lotes/campañas para confirmación; no se promete precisión por alcanzar ese número.
7. Ejecutar Evaluar datos y entrenar peso. Comparar su error absoluto medio con la referencia de peso medio sin medidas. Si no mejora, seguir usando la referencia pesada de lote y ampliar los datos.

El modelo nunca se entrena con pesos aproximados de publicaciones. Solo admite mediciones declaradas de báscula del conjunto exacto. No puede verificar físicamente que el usuario pesó el grupo correcto.

## SVM: diferencias deliberadas frente al notebook

- Se promedian las diez medidas ya calculadas por SIMAC, después de la revisión. El modo imagen no necesita metadatos de planta para las entradas, pero requiere una fila asociada que identifique la familia y contenga Yield para entrenar.
- Los metadatos permitidos son Days_to_anthesis, Days_to_silking, Plant_Height, Ear_Height, Tassel_branch_number, Weight_Ear, Length_Ear, Diameter_Ear, Number_Rows, Kernel_Row y Diameter_Cob. El modo metadatos/combinado requiere todas las entradas de su lista; no se imputan faltantes. Se prefiere bloquearlos y explicarlos.
- Se excluyen siempre Yield, Yield-media(yield), Class, clase, Weight_50K, Weight_AllK y All_Kernels. No se confía en el color de las celdas para detectar fugas.
- Class se ignora porque el notebook S4 advierte una inversión en la etiqueta S3. Las clases se definen con Yield y un umbral: Alto si es estrictamente mayor; Bajo en caso contrario.
- Se reservan cuatro IDs de familia con semilla 42 **antes** de calcular la mediana del entrenamiento. Alternativamente puede fijarse una referencia externa en las mismas unidades de Yield. No se calcula la mediana con los valores de prueba. Esto no reproduce exactamente las clases o la partición del notebook.
- No se eliminan familias para igualar clases según proximidad al objetivo; se usa class_weight=balanced. La partición reservada puede no contener ambas clases: se informa y se requiere confirmación externa, sin cambiar la semilla buscando mejores resultados.
- Se exige revisión, foto de granos de una sola familia y calibración para el modo de imagen. Se bloquean familias duplicadas. Conteo mínimo configurable (25 por defecto) y exclusiones por familia; no se excluye automáticamente Grano_05 o Grano_14 de cualquier lote nuevo. El mínimo debe corresponder al protocolo de captura.
- StandardScaler y SelectKBest(f_classif, hasta tres variables) se ajustan dentro de cada pliegue. Se evalúan parejas Alto/Bajo; hasta 100 parejas deterministas para limitar el tiempo interactivo. Una familia aparece en varias parejas: no son ensayos independientes.
- La comparación simple de kernels es exploratoria. La opción anidada usa GridSearchCV de cuatro kernels y C=0.1,1,10 dentro del pliegue externo; gamma y grado quedan en sus valores configurados. Se informa el rendimiento del procedimiento completo.
- La validación usa etiquetas fijadas por la referencia del entrenamiento; no se presenta como validación externa del proceso agronómico de definición de clases.
- La distancia SVM no se transforma en probabilidad. Cercanía a la frontera y medidas fuera del rango de entrenamiento se muestran como avisos.
- Las ejecuciones que vuelven a usar familias cuya prueba ya se vio quedan marcadas como exploratorias. Cambiar las entradas después de mirar la prueba no produce evidencia independiente.

Mínimo operativo: 12 familias con Yield real y al menos tres familias por clase en entrenamiento. Máximo de este experimento interactivo: 60 familias. Un mínimo operativo no certifica calidad estadística.

## Persistencia y uso

En el historial, Guardar cambios de la muestra actualiza su registro; la referencia de peso y el registro real de báscula viajan en el JSON de la muestra. No se sobrescriben fotografías históricas automáticamente.

Los reportes SVM se guardan en `data/yield_experiments/<uuid>.json` y se descargan como JSON o Excel. Incluyen entradas, configuración, exclusiones, partición, umbral, matrices y predicciones. Cada entrenamiento genera también una versión persistida que puede activarse desde Administración de modelos. Las predicciones de muestras usan esa versión sin entrenar de nuevo.

Los experimentos de peso se guardan en `data/weight_experiments/<uuid>.json`. Incluyen parámetros numéricos de Ridge, rango entrenado, IDs de muestras, huella de datos, error y predicciones de validación agrupada por lote. Modelo propio usa el último y rechaza su uso si los registros de pesaje cambiaron o se eliminaron. Es un modelo experimental sin aprobación automática por umbral de error.

Instalación de dependencias: `.\.venv-cellpose\Scripts\python.exe -m pip install -r backend/requirements.txt`. Reiniciar el backend si no está ejecutándose con recarga y actualizar el navegador.

Los cuatro registros actuales no proporcionan pesajes reales ni datos de Yield asociados y están en px: se puede mostrar el escenario bibliográfico por conteo, pero no presentar un modelo entrenado real con ellos.


## Flujo de aplicación y modelos persistidos

La pantalla Analizar muestras conserva conteo, dimensiones, revisión, fotografías, recomendaciones e historial. El resumen agrega automáticamente peso y su base, clasificación de rendimiento y estado del modelo. La referencia de peso y los pesajes se editan en un apartado plegable. Las variables de entrenamiento están en Administración de modelos, dentro de Preparar datos y entrenar modelos.

Cada entrenamiento completo de rendimiento guarda el Pipeline ajustado con normalización, selección y clasificador, más una ficha con columnas, umbral, rango, versión de biblioteca, métricas y familias de entrenamiento. Se conserva en data/yield_models con UUID y huella de integridad. La activación es explícita: Usar esta versión. Se puede volver a una versión anterior. Los reportes previos sin artefacto no se convierten automáticamente en modelos: se requiere entrenar una versión nueva.

El resumen usa exclusivamente la versión activa sin volver a ajustar parámetros. Cambiar de versión actualiza el resumen; las muestras guardadas conservan además una instantánea de los resultados al guardarse. Un modelo pendiente o una muestra sin entradas suficientes se muestra como clasificación pendiente. Las familias conocidas y las medidas fuera del rango se identifican en las recomendaciones. La clasificación sigue siendo experimental.

Administración es una separación de interfaz dentro de la cuenta de demostración existente; no introduce control de acceso por roles. Los modelos y reportes se generan localmente, no se importan artefactos binarios del usuario.


## Entrenamiento inicial con archivos reales del curso

Se importaron las tablas originales de Downloads y se copiaron a data/training_sources sin modificarlas: caracteristicas_por_familia.xlsx (hoja familias) y metadatosTT.xlsx (Sheet1). Se unieron por identificador; se descartaron Grano_05 y Grano_14 por los defectos documentados en S4. Quedaron 17 familias. Los agregados de Excel se usan como agregados reales; no se fabrican máscaras, granos ni pesajes.

Se entrenaron versiones de imagen y metadatos con selección anidada. Ambas acertaron 2 de 4 en prueba. Se activó la versión de metadatos para poder consultar el modelo con los datos de planta asociados, incluso antes de recalibrar una foto. La revisión del conteo sigue siendo una acción humana. El informe data/course_training.json conserva resultados, fuentes y sus huellas. Estos modelos no acreditan buena capacidad predictiva ni validación local; no se deben presentar como una clasificación confiable de Coroneo.

La regresión inicial de peso usa largo, ancho y área medios y el peso registrado de 50 granos dividido entre 50. Al dejar una familia fuera, el error medio para 50 granos es 1.348 g frente a 1.457 g de usar el promedio. No se conocen lotes independientes de esos archivos: no se presenta ese resultado como validación por lote local. La versión se conserva en data/course_weight.json. Las muestras deben estar en mm para aplicar la regresión.

En modo automático, un peso Weight_50K asociado a la muestra tiene prioridad como referencia empírica: conteo de la foto × Weight_50K / 50. Se muestra como extrapolación del registro, nunca como peso medido de los granos exactos de la foto. En ausencia de referencia asociada, se usa el modelo disponible en una muestra calibrada y revisada; si no es posible, queda el escenario de referencia general.

El archivo de metadatos guardado se recupera al abrir el laboratorio. Los nombres se muestran en español sin modificar las claves internas. Grano_05.jpg identifica la muestra completa: no el quinto grano detectado. Para nuevos datos locales existe un formulario que guarda identificador, localidad, campaña, lote, peso real de 50 granos y rendimiento de campo con su unidad. No reemplaza registros existentes ni inventa mediciones faltantes.

El resumen se descarga como HTML con las mediciones de todos los granos y los datos externos asociados. Se puede abrir sin conexión en un navegador y usar Imprimir / guardar como PDF. Los valores se escapan para no interpretar nombres o registros como código HTML.

La calibración admite marcar dos puntos en la regla de la imagen original. La distancia se calcula usando sus dimensiones naturales, independientemente del tamaño mostrado o ampliación. El usuario debe indicar la longitud física del tramo y volver a analizar. El programa no deduce una escala física de una fotografía sin referencia.
