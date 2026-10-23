// La vista previa y el análisis usan la misma imagen para conservar la escala.
// La adaptación de tamaño conserva el archivo original en el dispositivo.
export async function preparePhoto(file: File): Promise<File> {
  if (typeof createImageBitmap !== 'function') return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch {
    return file; // Compatibilidad con navegadores que utilizan el decodificador de imágenes.
  }
  try {
    const ratio = Math.min(1, 2560 / Math.max(bitmap.width, bitmap.height));
    if (ratio === 1) return file;
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * ratio));
    canvas.height = Math.max(1, Math.round(bitmap.height * ratio));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('canvas');
    context.fillStyle = '#fff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(value => value ? resolve(value) : reject(new Error('encode')), 'image/jpeg', 0.95));
    canvas.width = canvas.height = 1;
    return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', {type:'image/jpeg', lastModified:file.lastModified});
  } finally {
    bitmap.close();
  }
}
