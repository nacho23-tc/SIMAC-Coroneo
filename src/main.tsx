import './pwa';
import { preparePhoto } from './preparePhoto';
import { AgriculturePanel } from './AgriculturePanel';
import { AnalysisProgress } from './AnalysisProgress';
import { colorName, shapeName } from './appearance';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { ArrowRight, Camera, Check, Download, ImagePlus, Leaf, LoaderCircle, ScanLine, Settings2, X } from 'lucide-react';
import './style.css';
import { Portal } from './Portal';
import { ModelAdmin } from './ModelAdmin';
import { SampleSummary } from './SampleSummary';
import { metadataLabel, normalizedSample } from './metadataLabels';
import { ScaleCalibration } from './ScaleCalibration';
import { LocalMetadataForm } from './LocalMetadataForm';
import { WeightPanel, emptyWeight, type WeightData } from './WeightPanel';

type View = 'overlay' | 'original' | 'crop' | 'gray' | 'segmentation' | 'raw_masks' | 'dimensions';
const views: {id: View; label: string; description: string}[] = [
  {id:'original', label:'Original', description:'Fotografía completa que cargaste, antes del recorte.'},
  {id:'crop', label:'Recorte', description:'Zona seleccionada y reducida a la resolución de trabajo.'},
  {id:'gray', label:'Escala de grises', description:'Imagen de intensidad utilizada por el motor para separar los granos del fondo.'},
  {id:'raw_masks', label:'Máscaras del motor', description:'Objetos detectados antes de aplicar los filtros. Cada objeto tiene un color artificial sobre fondo negro.'},
  {id:'segmentation', label:'Segmentación', description:'Cada color artificial distingue un grano aceptado. Estos colores no representan el color real del maíz.'},
  {id:'overlay', label:'Conteo final', description:'Contornos y números de los granos aceptados por los filtros.'},
  {id:'dimensions', label:'Largo y ancho', description:'Azul: eje largo. Naranja: eje ancho. Son los ejes de la elipse equivalente de cada grano; sus valores aparecen en la tabla.'},
];
type Grain = { limites?: number[]; centro_x?: number; centro_y?: number; grano: number; largo: number; ancho: number; area: number; color_hex: string; toca_borde: boolean; perimetro: number; circularidad: number; razon_aspecto: number; solidez: number; L: number; a: number; b: number };
type Result = { editable_masks?: string; quality?: string; processing_seconds?: number; total_seconds?: number; sample: string; method: string; count: number; discarded: number; raw_count: number; unit: string; mean_length: number | null; mean_area: number | null; weight_status: string; warnings: string[]; grains: Grain[]; overlay: string; stages?: Record<string, string>; csv: string; working_size: number[]; diameter_work_px: number | null };
type Health = { cellpose_installed: boolean; analysis_version?: number };

function saveFile(data: string, filename: string, mime: string) {
  const url = URL.createObjectURL(new Blob([data], { type: mime }));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Laboratory() {
  const [section, setSection] = useState<'analysis'|'models'|'agriculture'>('analysis');
  const [modelRevision, setModelRevision] = useState(0);
  const [health, setHealth] = useState<Health | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [sample, setSample] = useState('');
  const [method, setMethod] = useState('cellpose');
  const [photoType, setPhotoType] = useState('grains');
  const [mixedConfirmed, setMixedConfirmed] = useState(false);
  const [roi, setRoi] = useState([0, 0, 100, 100]);
  const [scalePx, setScalePx] = useState('');
  const [scaleMm, setScaleMm] = useState('');
  const [diameter, setDiameter] = useState('');
  const [minArea, setMinArea] = useState('100');
  const [quality, setQuality] = useState('detailed');
  const [originalResult, setOriginalResult] = useState<Result | null>(null);
  const [excluded, setExcluded] = useState<number[]>([]);
  const [reviewed, setReviewed] = useState(false);
  const [mergePartner, setMergePartner] = useState('');
  const [mergeBusy, setMergeBusy] = useState(false);
  const [mergeError, setMergeError] = useState('');
  const [mergeUndo, setMergeUndo] = useState<Result[]>([]);
  function setResult(value: Result | null) {setOriginalResult(value);setMergeUndo([]);setMergePartner('');setMergeError('');setExcluded([]);setReviewed(false);}
  const includedGrains = originalResult?.grains.filter(g => !excluded.includes(g.grano)) || [];
  const result: Result | null = originalResult ? {...originalResult, grains:includedGrains, count:includedGrains.length,
    mean_length:includedGrains.length ? Number((includedGrains.reduce((sum,g) => sum+g.largo,0)/includedGrains.length).toFixed(3)) : null,
    mean_area:includedGrains.length ? Number((includedGrains.reduce((sum,g) => sum+g.area,0)/includedGrains.length).toFixed(3)) : null,
    csv:excluded.length ? (() => {
      const fields = Object.keys(originalResult.grains[0] || {});
      const escape = (value: unknown) => {
        let text = value == null ? '' : typeof value === 'boolean' ? (value ? 'True' : 'False') : String(value);
        if(typeof value === 'string' && /^[\s]*[=+\-@]/.test(text)) text = "'" + text;
        return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g,'""') + '"' : text;
      };
      return [fields.join(','), ...includedGrains.map(grain => fields.map(field => escape((grain as unknown as Record<string,unknown>)[field])).join(','))].join('\r\n');
    })() : originalResult.csv} : null;
  const [busy, setBusy] = useState(false);
  const [photoLoading, setPhotoLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [phase, setPhase] = useState('');
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const started = useRef(0);
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setElapsed(Math.floor((performance.now() - started.current) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);
  const formatTime = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2,'0')}`;
  const [error, setError] = useState('');
  const [view, setView] = useState<View>('overlay');
  const [zoom, setZoom] = useState(1);
  const [selectedGrain, setSelectedGrain] = useState<number | null>(null);
  const [hoveredGrain, setHoveredGrain] = useState<number | null>(null);
  function grainAtPoint(e: React.MouseEvent<HTMLImageElement> | React.PointerEvent<HTMLImageElement>) {
    if (!result || !['overlay','segmentation','dimensions','crop','gray'].includes(view)) return null;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width, y = (e.clientY - rect.top) / rect.height;
    const candidates = result.grains.filter(g => g.centro_x != null && g.centro_y != null && (g.limites ? x >= g.limites[0] && y >= g.limites[1] && x <= g.limites[2] && y <= g.limites[3] : Math.hypot((x-g.centro_x)*result.working_size[0], (y-g.centro_y)*result.working_size[1]) <= 30));
    candidates.sort((a,b) => Math.hypot((x-a.centro_x!)*rect.width,(y-a.centro_y!)*rect.height) - Math.hypot((x-b.centro_x!)*rect.width,(y-b.centro_y!)*rect.height));
    return candidates[0]?.grano ?? null;
  }
  const grainRows = useRef<Map<number, HTMLTableRowElement>>(new Map());
  useEffect(() => {setZoom(1);setSelectedGrain(null);setHoveredGrain(null);}, [originalResult]);
  function selectGrain(number: number) {
    setSelectedGrain(number);
    grainRows.current.get(number)?.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  const [drag, setDrag] = useState(false);
  const cropStart = useRef<{x: number; y: number; previous: number[]} | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [metadata, setMetadata] = useState<{columns: string[]; rows: Record<string,string>[]; filename: string} | null>(null);
  const metadataCatalog = useRef<typeof metadata>(null);
  const [metaKey, setMetaKey] = useState('');
  const [metaId, setMetaId] = useState('');
  const [metaError, setMetaError] = useState('');
  const [metaBusy, setMetaBusy] = useState(false);
  const [metaFile, setMetaFile] = useState<File | null>(null);
  const [metaSaved, setMetaSaved] = useState(false);
  const [history, setHistory] = useState<{id:string; created:string; name:string; count:number}[]>([]);
  const [historyError, setHistoryError] = useState('');
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [savedId, setSavedId] = useState('');
  const [weightData, setWeightData] = useState<WeightData>(emptyWeight);
  const grainSignature = JSON.stringify(includedGrains.map(g=>[g.grano,g.largo,g.ancho,g.area]));
  useEffect(()=>{setWeightData(value=>value.measured&&JSON.stringify(value.grain_signature)!==grainSignature?{...value,measured:false,grain_signature:undefined}:value);},[grainSignature]);
  const [editingId, setEditingId] = useState('');
  const [editName, setEditName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<{id:string;name:string} | null>(null);
  const [lastDeleted, setLastDeleted] = useState<{id:string;name:string} | null>(null);
  async function refreshHistory() {
    setHistoryLoading(true);setHistoryError('');
    try {
      let response: Response | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {response = await fetch('/api/samples', {signal: AbortSignal.timeout(15000)}); if(response.ok) break;} catch { /* Reintento ante fallos temporales de conexión. */ }
        if(attempt < 2) await new Promise(resolve => setTimeout(resolve, 1000));
      }
      if(!response?.ok) throw new Error('No se pudo conectar con el historial. Comprueba tu conexión y pulsa Actualizar historial para intentar de nuevo.');
      setHistory(await response.json());setHistoryLoaded(true);
    } catch {setHistoryError('No se pudo consultar el historial. Revisa la conexión con el servidor y vuelve a intentarlo.');}
    finally {setHistoryLoading(false);}
  }
  useEffect(() => {void refreshHistory();}, []);
  const input = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const check = () => fetch('/api/health', { signal: controller.signal }).then(r => r.ok ? r.json() : Promise.reject()).then(setHealth).catch(() => { if (!controller.signal.aborted) setHealth(null); });
    check();
    const interval = setInterval(check, 10000);
    return () => { controller.abort(); clearInterval(interval); };
  }, []);
  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const photoSelection = useRef(0);
  async function choose(f?: File) {
    if (!f || busy) return;

    if (f.size > 25 * 1024 * 1024) { setError('La imagen debe pesar menos de 25 MB.'); return; }
    const selection = ++photoSelection.current;
    setError('');
    setPhotoLoading(true);
    try {
      const bytes = new Uint8Array(await f.slice(0, 16).arrayBuffer());
      if (selection !== photoSelection.current) return;
      const isJpeg = bytes[0]===255 && bytes[1]===216 && bytes[2]===255;
      const isPng = [137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v);
      const isWebp = String.fromCharCode(...bytes.slice(0,4))==='RIFF' && String.fromCharCode(...bytes.slice(8,12))==='WEBP';
      const mime = isJpeg?'image/jpeg':isPng?'image/png':isWebp?'image/webp':'';
      if (!mime) {
        setError(/heic|heif/i.test(f.type+' '+f.name)?'La cámara guardó la foto en HEIC/HEIF. Configura la cámara en JPEG o “Más compatible”, o exporta la foto como JPG y usa Elegir imagen.':'No se reconoce la fotografía. Selecciona un archivo JPG, PNG o WebP completo.');
        return;
      }
      if (f.type !== mime) f = new File([f], f.name, {type:mime,lastModified:f.lastModified});
      f = await preparePhoto(f);
      const checkUrl = URL.createObjectURL(f);
      try {
        await new Promise<void>((resolve,reject)=>{
          const image = new Image();
          const timer = window.setTimeout(()=>{image.src='';reject(new Error('timeout'));},20000);
          image.onload=()=>{clearTimeout(timer);image.onload=null;image.onerror=null;resolve()};
          image.onerror=()=>{clearTimeout(timer);image.onload=null;image.onerror=null;reject(new Error('decode'))};
          image.src=checkUrl;
        });
      } finally { URL.revokeObjectURL(checkUrl); }
      if (selection !== photoSelection.current) return;
    } catch {
      if (selection === photoSelection.current) setError('La tableta no pudo abrir la fotografía. Prueba tomarla con menor resolución y seleccionarla desde Elegir imagen.');
      return;
    } finally {
      if (selection === photoSelection.current) setPhotoLoading(false);
    }
    setError(''); setResult(null); setSavedId(''); if(metadataCatalog.current){setMetadata(metadataCatalog.current);setMetaKey(metadataCatalog.current.columns.find(c=>/nombre_imagen|nombre_nuevo|muestra|imagen|familia/i.test(c))||metadataCatalog.current.columns[0]);} setWeightData(emptyWeight); setFile(f); setSample(f.name.replace(/\.[^.]+$/, ''));
    setRoi([0, 0, 100, 100]); setScalePx(''); setScaleMm(''); setMetaId(f.name); setMixedConfirmed(false);
  }

  function point(e: React.PointerEvent<HTMLDivElement>) {
    const box = e.currentTarget.getBoundingClientRect();
    return {x: Math.max(0, Math.min(100, (e.clientX-box.left)/box.width*100)), y: Math.max(0, Math.min(100, (e.clientY-box.top)/box.height*100))};
  }
  function beginCrop(e: React.PointerEvent<HTMLDivElement>) {
    if (busy || !e.isPrimary || e.button !== 0 || (e.target as HTMLElement).closest('button')) return;
    e.preventDefault();
    cropStart.current = {...point(e), previous: [...roi]};
    e.currentTarget.setPointerCapture(e.pointerId); setDrawing(true);
  }
  function moveCrop(e: React.PointerEvent<HTMLDivElement>) {
    const start = cropStart.current; if (!start || !e.currentTarget.hasPointerCapture(e.pointerId)) return;
    const end = point(e);
    if (Math.abs(end.x-start.x)<1 || Math.abs(end.y-start.y)<1) return;
    setRoi([Math.min(start.x,end.x),Math.min(start.y,end.y),Math.max(start.x,end.x),Math.max(start.y,end.y)].map(v => Math.round(v*100)/100));
  }
  function endCrop(e: React.PointerEvent<HTMLDivElement>, cancel = false) {
    const start = cropStart.current; if (!start) return;
    const end = point(e);
    if (cancel || Math.abs(end.x-start.x)<1 || Math.abs(end.y-start.y)<1) setRoi(start.previous);
    else { moveCrop(e); setResult(null); }
    cropStart.current=null; setDrawing(false);
    if(e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  }

  async function run() {
    if (!file) return;
    if (photoType === 'ear' || photoType === 'unsuitable' || (photoType === 'mixed' && (!mixedConfirmed || (roi[0] === 0 && roi[1] === 0 && roi[2] === 100 && roi[3] === 100)))) { setError('Selecciona una zona con granos sueltos o utiliza una fotografía adecuada.'); return; }
    if (health?.analysis_version !== 2) { setError('El servicio de análisis se está actualizando. Intenta nuevamente en unos momentos.'); return; }
    if (!(roi[0] < roi[2] && roi[1] < roi[3])) { setError('El límite izquierdo debe ser menor que el derecho, y el superior menor que el inferior.'); return; }
    if (Boolean(Number(scalePx)) !== Boolean(Number(scaleMm))) { setError('Completa las dos medidas de calibración, o deja ambas vacías.'); return; }
    started.current = performance.now(); setElapsed(0); setUploadPercent(null); setPhase('Enviando fotografía');
    setBusy(true); setError(''); setResult(null);
    requestAnimationFrame(()=>resultRef.current?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'}));
    const body = new FormData();
    body.append('file', file); body.append('sample', sample); body.append('method', method);
    ['left', 'top', 'right', 'bottom'].forEach((key, i) => body.append(key, String(roi[i] / 100)));
    body.append('scale_pixels', scalePx || '0'); body.append('scale_mm', scaleMm || '0');
    body.append('quality', quality);
    body.append('diameter', diameter || '0'); body.append('min_area', minArea || '100');
    try {
      const data = await new Promise<Result>((resolve, reject) => {
        const request = new XMLHttpRequest();
        request.open('POST', '/api/analyze');
        request.responseType = 'json';
        request.timeout = 10 * 60 * 1000;
        request.upload.onprogress = e => {if (e.lengthComputable) setUploadPercent(Math.round(e.loaded / e.total * 100));};
        request.upload.onload = () => {setUploadPercent(100); setPhase('Fotografía enviada · Solicitud en procesamiento');};
        request.onprogress = () => setPhase('Recibiendo resultados');
        request.onload = () => {
          if (request.status >= 200 && request.status < 300 && request.response) resolve(request.response);
          else reject(new Error(typeof request.response?.detail === 'string' ? request.response.detail : 'No se pudo completar el análisis.'));
        };
        request.onerror = () => reject(new Error('Se perdió la conexión con el servidor. Revisa tu conexión e intenta nuevamente cuando el servicio esté disponible.'));
        request.ontimeout = () => reject(new Error('No se recibió una respuesta en 10 minutos. El servidor podría seguir procesando; comprueba su estado antes de repetir el análisis.'));
        request.send(body);
      });
      data.total_seconds = (performance.now() - started.current) / 1000;
      setResult(data); setWeightData(v=>({...v,measured:false,grain_signature:undefined})); setView('overlay');
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo conectar con el servidor.'); }
    finally { setBusy(false); }
  }

  useEffect(() => {void loadSavedMetadata();}, []);
  async function loadSavedMetadata() {
    setMetaBusy(true); setMetaError('');
    try {
      const response = await fetch('/api/metadata/saved');
      const data = await response.json();
      if (!response.ok) throw new Error('No se pudieron consultar los metadatos guardados.');
      if (!data.available) {setMetaError('Todavía no hay un archivo guardado. Selecciona uno y pulsa Guardar para futuras consultas.'); return;}
      metadataCatalog.current=data; setMetadata(data); setMetaFile(null); setMetaSaved(true);
      setMetaKey(data.columns.find((c: string) => /nombre_imagen|nombre_nuevo|muestra|imagen|familia/i.test(c)) || data.columns[0]);
      setMetaId(current=>current || file?.name || result?.sample || '');
    } catch(e) {setMetaError(e instanceof Error ? e.message : 'No se pudo conectar con el servicio.');}
    finally {setMetaBusy(false);}
  }
  async function uploadMetadata(f?: File, persist = false) {
    if (!f) return;
    setMetaBusy(true); setMetaError(''); setMetadata(null); setMetaFile(f); setMetaSaved(false);
    const body = new FormData(); body.append('file', f);
    try {
      const response = await fetch(persist ? '/api/metadata/saved' : '/api/metadata', {method:'POST', body});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se pudieron leer los metadatos.');
      metadataCatalog.current={...data,filename:f.name}; setMetadata(metadataCatalog.current); setMetaSaved(persist);
      setMetaKey(data.columns.find((c: string) => /nombre_imagen|nombre_nuevo|muestra|imagen|familia/i.test(c)) || data.columns[0]);
      setMetaId(file?.name || result?.sample || '');
    } catch(e) {setMetaError(e instanceof Error ? e.message : 'No se pudo conectar con el servidor.');}
    finally {setMetaBusy(false);}
  }
  const normalizeKey = normalizedSample;
  const matches = metadata?.rows.filter(row => normalizeKey(row[metaKey] || '') === normalizeKey(metaId)) || [];
  async function saveSample() {
    if (!file || !result) return;
    setHistoryBusy(true); setHistoryError('');
    try {
    const body = new FormData(); body.append('file', file);
    body.append('identifier', savedId);
    const payloadBlob = new Blob([JSON.stringify({result, metadata_selection:metadata?'explicit':'auto', weight_inputs:weightData, original_result:originalResult, review:{excluded, reviewed}, merge_history:mergeUndo, parameters:{roi, scalePx, scaleMm, diameter, minArea, method, quality, photoType}, metadata:matches.length === 1 ? {columns:metadata!.columns, rows:[matches[0]], filename:metadata!.filename, key:metaKey, identifier:metaId} : null})], {type:'application/json'});
    const savedPayload = typeof CompressionStream !== 'undefined' ? await new Response(payloadBlob.stream().pipeThrough(new CompressionStream('gzip'))).blob() : payloadBlob;
    body.append('payload', savedPayload, savedPayload === payloadBlob ? 'resultado.json' : 'resultado.json.gz');
    const response = await fetch('/api/samples',{method:'POST',body}); const data = await response.json(); if(!response.ok) throw new Error(data.detail || 'No se pudo guardar.');setSavedId(data.id);await refreshHistory();}
    catch(e) {setHistoryError(e instanceof TypeError ? 'No se pudo conectar para guardar. Revisa la conexión e intenta nuevamente.' : e instanceof Error ? e.message : 'No se pudo guardar.');}
    finally {setHistoryBusy(false);}
  }
  async function openSample(id: string) {
    setHistoryBusy(true);setHistoryError('');
    try {
      const response = await fetch(`/api/samples/${id}`);const data = await response.json();if(!response.ok) throw new Error(data.detail || 'No se pudo abrir.');
      const bytes = Uint8Array.from(atob(data.image_base64),(c:string) => c.charCodeAt(0));
      const name = data.filename || 'muestra.png';const mime = /\.webp$/i.test(name) ? 'image/webp' : /\.png$/i.test(name) ? 'image/png' : 'image/jpeg';
      setFile(new File([bytes],name,{type:mime}));setResult(data.original_result || data.result);setMergeUndo(data.merge_history || []);setExcluded(data.review?.excluded || []);setReviewed(data.review?.reviewed || false);setSample(data.result.sample);setSavedId(id);setView('overlay');setError('');
      const p = data.parameters;setRoi(p.roi);setScalePx(p.scalePx);setScaleMm(p.scaleMm);setDiameter(p.diameter);setMinArea(p.minArea);setMethod(p.method);setQuality(p.quality);setPhotoType(p.photoType);setMixedConfirmed(p.photoType === 'mixed');
      setMetadata(data.metadata || metadata);setMetaKey(data.metadata?.key || metaKey);setMetaId(data.metadata?.identifier || name);setMetaFile(null);setMetaSaved(Boolean(metadataCatalog.current&&(!data.metadata||metadataCatalog.current.filename===data.metadata.filename)));setMetaError('');
      setWeightData(data.weight_inputs || emptyWeight);
      setTimeout(() => resultRef.current?.scrollIntoView({behavior:'smooth',block:'start'}),100);
    } catch(e) {setHistoryError(e instanceof TypeError ? 'No se pudo conectar para abrir la muestra. Intenta nuevamente.' : e instanceof Error ? e.message : 'No se pudo abrir la muestra.');}
    finally {setHistoryBusy(false);}
  }
  async function mergeSelected() {
    if (!file || !originalResult || selectedGrain == null || !mergePartner) return;
    setMergeBusy(true);setMergeError('');
    const body = new FormData();body.append('file',file);
    body.append('payload',new Blob([JSON.stringify({result:originalResult,pair:[selectedGrain,Number(mergePartner)],parameters:{roi,scalePx,scaleMm,method}})],{type:'application/json'}),'union.json');
    try {
      const response = await fetch('/api/samples/merge',{method:'POST',body});const data = await response.json();if(!response.ok) throw new Error(data.detail || 'No se pudo unir.');
      setMergeUndo([...mergeUndo,originalResult]);setOriginalResult(data);setReviewed(false);setMergePartner('');setWeightData(v=>({...v,measured:false,grain_signature:undefined}));
    } catch(e) {setMergeError(e instanceof Error ? e.message : 'No se pudo conectar.');}
    finally {setMergeBusy(false);}
  }
  async function changeHistory(id: string, action: 'rename' | 'delete' | 'restore') {
    setHistoryBusy(true);setHistoryError('');
    try {
      const body = new FormData();body.append('name',editName.trim());
      const response = await fetch(`/api/samples/${id}${action === 'restore' ? '/restore' : ''}`,{method:action === 'rename' ? 'PATCH' : action === 'delete' ? 'DELETE' : 'POST', ...(action === 'rename' ? {body} : {})});
      const data = await response.json();if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se pudo actualizar la muestra.');
      if(action === 'rename') {setEditingId('');if(savedId === id) await openSample(id);}
      if(action === 'delete') {setLastDeleted(deleteTarget);setDeleteTarget(null);if(savedId === id) setSavedId('');}
      if(action === 'restore') setLastDeleted(null);
      await refreshHistory();
    } catch(e) {setHistoryError(e instanceof TypeError ? 'No se pudo conectar con el servidor.' : e instanceof Error ? e.message : 'No se pudo actualizar.');}
    finally {setHistoryBusy(false);}
  }
  const detailGrain = result?.grains.find(g => g.grano === (hoveredGrain ?? selectedGrain));
  const safeName = (result?.sample || 'muestra').replace(/[^\p{L}\p{N}_-]/gu, '_');
  return <>
    <main>
      <div className="lab-tabs" role="navigation" aria-label="Secciones del laboratorio"><button aria-pressed={section==='analysis'} onClick={()=>setSection('analysis')}>Analizar muestras</button><button aria-pressed={section==='agriculture'} onClick={()=>setSection('agriculture')}>Registro agrícola</button><button aria-pressed={section==='models'} onClick={()=>setSection('models')}>Administración de modelos</button></div>
      <div hidden={section!=='analysis'}>
      <div className="section-heading" id="analisis"><div><span className="eyebrow">TU MUESTRA, EN DETALLE</span><h2>Laboratorio de semillas</h2></div><span className={`server ${health ? 'online' : ''}`}><span/>{health ? 'Servicio disponible' : 'Servicio no disponible'}</span></div>
      <ol className="lab-progress" aria-label="Progreso del análisis">{[{label:'Cargar',done:!!preview},{label:'Calibrar',done:!!result&&result.unit==='mm'},{label:'Analizar',done:!!result},{label:'Revisar',done:!!result&&reviewed},{label:'Resultados',done:!!result&&reviewed}].map((step,i)=><li key={step.label} className={step.done?'is-done':''}><span aria-hidden="true">{step.done?'✓':i+1}</span><div>{step.label}<small>{step.done?'Completado':i===1?'Opcional · medidas en mm':i===2&&busy?'En proceso':'Pendiente'}</small></div></li>)}</ol><p className="laboratory-intro">Captura una fotografía, prepara tu muestra y explora sus características. Revisa los contornos antes de utilizar las mediciones.</p><div className="workspace"><section className="panel upload-panel"><div className="panel-title"><span className="step">01</span><h3>Prepara tu muestra</h3></div>
        <fieldset disabled={busy || photoLoading}>
          <input ref={input} className="file-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={e => {choose(e.target.files?.[0]); e.target.value = '';}}/>
          <input ref={cameraInput} className="file-input" type="file" accept="image/*" capture="environment" onChange={e => {choose(e.target.files?.[0]); e.target.value = '';}}/>
          <div className="capture-actions"><button type="button" onClick={() => cameraInput.current?.click()}><Camera size={20}/>{file ? 'Tomar otra fotografía' : 'Tomar fotografía'}</button><button type="button" onClick={() => input.current?.click()}><ImagePlus size={20}/>{file ? 'Elegir otra imagen' : 'Elegir imagen'}</button></div><p className="help">En celular o tablet, “Tomar fotografía” abre la cámara del dispositivo. Confirma la captura con la marca de verificación para regresar al recorte. Las fotos grandes se adaptan a un máximo de 2560 px; calibra sobre la imagen cargada. Si tu dispositivo no abre la cámara, toma la foto con su aplicación de cámara y usa “Elegir imagen”.</p>
          {photoLoading && <p className="notice" role="status"><LoaderCircle className="spin" size={18}/> Preparando fotografía para el recorte…</p>}
          {!file ? <button className={`dropzone ${drag ? 'drag' : ''}`} onClick={() => input.current?.click()} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); choose(e.dataTransfer.files[0]); }}><span className="upload-icon"><ImagePlus size={32} strokeWidth={1.5}/></span><strong>Tu análisis comienza con una foto</strong><span>Arrastra una imagen o selecciona desde tu dispositivo</span><span className="select-file">Elegir imagen <ArrowRight size={16}/></span><small>JPG, PNG o WebP · Hasta 25 MB</small></button> : <><div className={`source-preview crop-editor ${drawing ? 'drawing' : ''}`} onPointerDown={beginCrop} onPointerMove={moveCrop} onPointerUp={e => endCrop(e)} onPointerCancel={e => endCrop(e, true)} onLostPointerCapture={() => {const start=cropStart.current;if(start){setRoi(start.previous);cropStart.current=null;setDrawing(false);}}}><img draggable={false} src={preview || undefined} alt="Fotografía original de la muestra" onError={()=>setError('No se pudo mostrar la foto. Vuelve a elegirla o toma una fotografía de menor resolución en formato JPEG.')}/><div className="crop-box" style={{ left: `${roi[0]}%`, top: `${roi[1]}%`, width: `${Math.max(0, roi[2]-roi[0])}%`, height: `${Math.max(0, roi[3]-roi[1])}%` }}/></div><button type="button" className="text-button remove-photo-action" onClick={() => { photoSelection.current++; cropStart.current=null; setDrawing(false); setFile(null); setResult(null); if (input.current) input.current.value = ''; }}>Quitar fotografía</button><p className="help">Arrastra sobre la foto para encerrar los granos. Deja la regla fuera del recuadro. Puedes dibujar de nuevo para corregirlo.</p><button className="text-button" onClick={() => {setRoi([0,0,100,100]); setResult(null);}}>Restablecer imagen completa</button><div className="file-caption"><span>{file.name}</span><button onClick={() => input.current?.click()}>Cambiar</button></div></>}
          <label>Tipo de fotografía<select value={photoType} onChange={e => {setPhotoType(e.target.value);setResult(null);setError('');setMixedConfirmed(false);}}><option value="grains">Granos sueltos</option><option value="ear">Mazorca</option><option value="mixed">Mixta · Granos y mazorca</option><option value="unsuitable">Imagen no adecuada</option></select></label><p className="help">Selecciona el contenido de la foto. Esta selección es manual.</p>{photoType === 'ear' && <div className="notice"><strong>Fotografía de mazorca</strong><p>El análisis de mazorcas está en preparación. Conserva fotos de ambos lados con una regla y luz uniforme. El análisis actual corresponde a granos sueltos.</p></div>}{photoType === 'unsuitable' && <div className="notice"><strong>Prepara una nueva fotografía</strong><p>Evita desenfoque, sombras fuertes y granos superpuestos. Usa fondo oscuro, luz uniforme y una regla visible.</p></div>}{photoType === 'mixed' && <div className="notice"><p>Recorta únicamente los granos sueltos, dejando fuera la mazorca y otros objetos.</p><label className="check-label"><input type="checkbox" checked={mixedConfirmed} onChange={e => setMixedConfirmed(e.target.checked)}/> Confirmo que el recorte contiene solo granos sueltos</label></div>}<label>Nombre de la muestra<input value={sample} onChange={e => setSample(e.target.value)} placeholder="Ej. Maíz pinto · Lote 01" maxLength={120}/></label>
          <div className="photo-tip"><Leaf size={19}/><p>Usa fondo oscuro, luz uniforme y granos separados. Incluye una regla para calibrar y exclúyela del recorte.</p></div>
          <details open={!!file}><summary><Settings2 size={16}/> Zona de análisis y escala</summary><p className="help">Dibuja el recorte sobre la foto. Si necesitas precisión adicional, puedes ajustar los límites aquí.</p><details><summary>Ajustar límites numéricos (opcional)</summary><div className="roi-fields">{['Izquierda %','Arriba %','Derecha %','Abajo %'].map((label, i) => <label key={label}>{label}<input type="number" min="0" max="100" step="0.1" value={roi[i]} onChange={e => setRoi(roi.map((v, j) => i === j ? Number(e.target.value) : v))}/></label>)}</div></details>{preview&&<details><summary>Calibrar con dos puntos de la regla</summary><ScaleCalibration key={preview} src={preview} onPixels={setScalePx}/></details>}<div className="calibration"><label>Distancia en la imagen original (px)<input type="number" min="0" step="any" placeholder="Sin calibrar" value={scalePx} onChange={e => setScalePx(e.target.value)}/></label><label>Distancia real de ese tramo (mm)<input type="number" min="0" step="any" placeholder="Ej. 10" value={scaleMm} onChange={e => setScaleMm(e.target.value)}/></label></div><p className="help">Introduce dos medidas del mismo tramo de la regla. Sin ellas, reportaremos píxeles. La regla debe estar en el mismo plano que los granos. Ejemplo: si 10 mm ocupan 200 px, cada píxel equivale a 0.05 mm. Vuelve a analizar después de cambiar la escala.</p></details>
          <label>Motor de análisis<select value={method} onChange={e => setMethod(e.target.value)}><option value="cellpose">Segmentación inteligente · Cellpose</option><option value="classical">Método clásico · Umbral automático</option></select></label>
          {health && !health.cellpose_installed && method === 'cellpose' && <p className="notice">La segmentación inteligente no está disponible en este momento. Selecciona el método clásico para continuar.</p>}
          <label>Nivel de análisis<select value={quality} onChange={e => {setQuality(e.target.value);setResult(null);}}><option value="quick">Rápido · Hasta 1000 px</option><option value="detailed">Detallado · Hasta 1800 px</option></select></label><p className="help">{quality === 'quick' ? 'Reduce la resolución para una revisión inicial. Puede perder detalles y granos pequeños.' : 'Conserva más detalle para revisar contornos y medidas. Puede tardar más.'} Las medidas siguen expresadas en la escala original o en milímetros si calibras.</p>
          <details><summary>Parámetros avanzados</summary><div className="calibration"><label>Diámetro en imagen de trabajo (px)<input type="number" min="0" max="1000" placeholder="Automático" value={diameter} onChange={e => setDiameter(e.target.value)}/></label><label>Área mínima de trabajo (px²)<input type="number" min="1" max="100000" value={minArea} onChange={e => setMinArea(e.target.value)}/></label></div><p className="help">Estos parámetros se expresan en la resolución de referencia de hasta 1800 px. En modo Rápido se ajustan proporcionalmente. El diámetro solo aplica a Cellpose.</p></details>
        </fieldset>
        {error && <div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={!file || busy || drawing || photoType === 'ear' || photoType === 'unsuitable' || (photoType === 'mixed' && (!mixedConfirmed || (roi[0] === 0 && roi[1] === 0 && roi[2] === 100 && roi[3] === 100)))} onClick={run}>{busy ? <LoaderCircle className="spin" size={19}/> : <ScanLine size={19}/>} {busy ? 'Analizando la muestra…' : 'Analizar semillas'}{!busy && <ArrowRight size={18}/>}</button>

      </section>
      <section className="panel result-panel" ref={resultRef}><div className="panel-title"><span className="step">02</span><h3>Conoce tus resultados</h3>{result && !busy && <span className="done"><Check size={14}/> Completado</span>}</div>
        {busy ? <AnalysisProgress phase={phase} elapsed={elapsed} uploadPercent={uploadPercent}/> : !result ? <div className="empty-state"><div className="seed-art" aria-hidden="true">{Array.from({length: 9}, (_,i) => <span key={i}/>)}</div><h3>{busy ? 'Cada grano cuenta' : 'Aquí comienza una nueva mirada'}</h3><p>{busy ? 'Estamos identificando los objetos y calculando sus características.' : 'Carga una fotografía para descubrir el conteo, las dimensiones y el color de tus granos.'}</p><div className="empty-features"><span>Conteo</span><span>Dimensiones</span><span>Color</span></div></div> : <>
          <p className="result-timing">Tiempo total: {formatTime(result.total_seconds ?? 0)}{result.processing_seconds != null && ` · Procesamiento del servidor: ${result.processing_seconds.toFixed(1)} s`}</p><div className="result-subtitle"><strong>{result.sample}</strong><span>{result.method}</span></div>
          <div className="metrics"><div><span>Granos detectados</span><strong>{result.count}</strong></div><div><span>Largo promedio</span><strong>{result.mean_length ?? '—'} <small>{result.unit}</small></strong></div><div><span>Área promedio</span><strong>{result.mean_area ?? '—'} <small>{result.unit}²</small></strong></div></div>
          <h3 className="process-title">Así se analizó tu muestra</h3>{!result.stages && <p className="notice">Las vistas de este resultado no están disponibles. Realiza un nuevo análisis.</p>}<div className="image-tabs process-tabs" aria-label="Etapas del análisis">{views.filter(v => v.id === 'original' || v.id === 'overlay' || result.stages?.[v.id]).map((v, i) => <button key={v.id} aria-pressed={view === v.id} className={view === v.id ? 'selected' : ''} onClick={() => setView(v.id)}><img src={(v.id === 'original' ? preview : v.id === 'overlay' ? result.overlay : result.stages?.[v.id]) || undefined} alt=""/><span>Imagen {i + 1} · {v.label}</span></button>)}</div>
          <p className="stage-description">{views.find(v => v.id === view)?.description}</p>
          <div className="review-tools"><label>Ampliación<select value={zoom} onChange={e => setZoom(Number(e.target.value))}><option value={1}>100% · Ajustar</option><option value={1.5}>150%</option><option value={2}>200%</option><option value={3}>300%</option></select></label><label>Consultar grano<select value={selectedGrain ?? ''} onChange={e => {if(e.target.value) selectGrain(Number(e.target.value));else setSelectedGrain(null);}}><option value="">Selecciona un grano</option>{result.grains.map(g => <option key={g.grano} value={g.grano}>Grano #{g.grano}</option>)}</select></label></div><p className="help">Amplía y desplázate por la imagen. En Conteo final, Segmentación o Largo y ancho, toca directamente un grano para consultar sus parámetros. En computadora, también puedes pasar el mouse sobre él.</p>
          <div className="result-image review-viewport"><div className="review-canvas" style={{width:`${zoom*100}%`}}><img src={(view === 'original' ? preview : view === 'overlay' ? result.overlay : result.stages?.[view]) || undefined} alt={views.find(v => v.id === view)?.label} onPointerMove={e => {if(e.pointerType === 'mouse') setHoveredGrain(grainAtPoint(e));}} onPointerLeave={() => setHoveredGrain(null)} onClick={e => {const grain = grainAtPoint(e);setSelectedGrain(grain);setHoveredGrain(null);}}/>{['overlay','segmentation','dimensions'].includes(view) && result.grains.filter(g => g.centro_x != null && g.centro_y != null).map(g => <button key={g.grano} type="button" className={`grain-marker ${selectedGrain === g.grano ? 'selected' : ''}`} style={{left:`${g.centro_x!*100}%`,top:`${g.centro_y!*100}%`}} aria-label={`Seleccionar grano ${g.grano}`} aria-pressed={selectedGrain === g.grano} title={`Grano #${g.grano} · Largo: ${g.largo} ${result.unit} · Ancho: ${g.ancho} ${result.unit} · Área: ${g.area} ${result.unit}² · Circularidad: ${g.circularidad ?? '—'}`} onMouseEnter={() => setHoveredGrain(g.grano)} onMouseLeave={() => setHoveredGrain(null)} onFocus={() => setHoveredGrain(g.grano)} onBlur={() => setHoveredGrain(null)} onClick={() => setSelectedGrain(g.grano)}>{g.grano}</button>)}</div></div>
          {detailGrain && <section className="grain-details" aria-label="Características del grano"><div className="grain-details-heading"><strong>Grano #{detailGrain.grano}</strong><span><span className="swatch" style={{backgroundColor:detailGrain.color_hex}}/>{detailGrain.color_hex}</span></div><p className="appearance-caption">{colorName(detailGrain.color_hex)} · Forma {shapeName(detailGrain).toLowerCase()}</p><dl>{[['Largo',`${detailGrain.largo} ${result.unit}`],['Ancho',`${detailGrain.ancho} ${result.unit}`],['Área',`${detailGrain.area} ${result.unit}²`],['Perímetro',detailGrain.perimetro != null ? `${detailGrain.perimetro} ${result.unit}` : '—'],['Circularidad',detailGrain.circularidad ?? '—'],['Solidez',detailGrain.solidez]].map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{detailGrain.toca_borde && <p>Este grano toca el borde del recorte; sus medidas pueden estar incompletas.</p>}</section>}
          <section className="review-corrections"><h3>Revisión de detecciones</h3><details><summary>Cómo revisar y confirmar los granos</summary><ol><li>En Conteo final, amplía la imagen y comprueba que cada grano tenga un solo contorno y un número.</li><li>Si hay polvo o un objeto extra, selecciónalo y pulsa Excluir detección seleccionada.</li><li>Si un grano quedó dividido, selecciona una parte y usa Unir como un solo grano con la otra parte.</li><li>Si faltan granos o varios quedaron pegados, ajusta el recorte o los parámetros y vuelve a analizar.</li><li>Cuando el conteo y los contornos coincidan con la foto, marca He revisado las detecciones y guarda.</li></ol></details><label>Unir el grano seleccionado con<select value={mergePartner} disabled={mergeBusy} onChange={e => setMergePartner(e.target.value)}><option value="">Selecciona la otra parte</option>{result.grains.filter(g => g.grano !== selectedGrain).map(g => <option key={g.grano} value={g.grano}>Grano #{g.grano}</option>)}</select></label><div className="exports"><button disabled={mergeBusy || !originalResult?.editable_masks || selectedGrain == null || !mergePartner || excluded.length > 0} onClick={mergeSelected}>{mergeBusy ? 'Uniendo…' : 'Unir como un solo grano'}</button><button disabled={mergeBusy || !mergeUndo.length || excluded.length > 0} onClick={() => {setOriginalResult(mergeUndo[mergeUndo.length-1]);setMergeUndo(mergeUndo.slice(0,-1));setReviewed(false);setWeightData(v=>({...v,measured:false,grain_signature:undefined}));}}>Deshacer unión</button></div>{!originalResult?.editable_masks && <p className="notice">Realiza un nuevo análisis para habilitar la unión de segmentos.</p>}{excluded.length > 0 && <p className="help">Deshaz las exclusiones antes de unir segmentos, porque la unión reasigna sus números.</p>}{mergeError && <p className="error" role="alert">{mergeError}</p>}<p className="help">Excluye únicamente objetos incorrectos. Si un grano aparece dividido en dos, excluir una parte no reconstruye su contorno ni sus medidas.</p><div className="exports"><button disabled={selectedGrain == null || excluded.includes(selectedGrain)} onClick={() => {if(selectedGrain != null){setExcluded([...excluded,selectedGrain]);setReviewed(false);setSelectedGrain(null);setHoveredGrain(null);}}}>Excluir detección seleccionada</button><button disabled={!excluded.length} onClick={() => {setExcluded(excluded.slice(0,-1));setReviewed(false);}}>Deshacer última exclusión</button></div>{excluded.length > 0 && <p className="notice">{excluded.length} detecciones excluidas: {excluded.map(id => `#${id}`).join(', ')}. Las imágenes muestran la segmentación original; la tabla, el CSV y los promedios reflejan las exclusiones.</p>}<label className="check-label"><input type="checkbox" checked={reviewed} onChange={e => {setReviewed(e.target.checked);}}/> He revisado las detecciones</label></section>
          {selectedGrain != null && <p className="selection-info" role="status">Grano #{selectedGrain} seleccionado. Su fila está resaltada en la tabla.</p>}

          <div className="result-meta"><span>{result.raw_count ?? result.count + result.discarded} objetos del motor · {result.discarded} descartados</span><span>{result.quality === 'quick' ? 'Rápido' : 'Detallado'} · Trabajo: {result.working_size.join(' × ')} px</span></div>
          <p className="help">Diámetro usado: {result.diameter_work_px == null ? 'No aplica al método clásico' : `${result.diameter_work_px.toFixed(1)} px de trabajo`}</p><SampleSummary payload={{metadata_selection:metadata?'explicit':'auto',_model_revision:modelRevision,result:{sample:result.sample,unit:result.unit,grains:result.grains},review:{reviewed},parameters:{photoType},weight_inputs:weightData,metadata:matches.length===1?{filename:metadata!.filename,key:metaKey,identifier:metaId,rows:[matches[0]]}:null}}/><details className="weight-settings"><summary>Referencia de peso y registro de báscula</summary><WeightPanel count={result.count} unit={result.unit} reviewed={reviewed} signature={result.grains.map(g=>[g.grano,g.largo,g.ancho,g.area])} value={weightData} onChange={setWeightData}/></details>
          <div className="table-scroll"><table><thead><tr><th>Grano</th><th>Largo ({result.unit})</th><th>Ancho ({result.unit})</th><th>Área ({result.unit}²)</th><th>Perímetro ({result.unit})</th><th>Razón de aspecto</th><th>Circularidad</th><th>Solidez</th><th>L*</th><th>a*</th><th>b*</th><th>Color</th></tr></thead><tbody>{result.grains.map(g => <tr key={g.grano} ref={element => {if(element) grainRows.current.set(g.grano,element);else grainRows.current.delete(g.grano);}} className={selectedGrain === g.grano ? 'selected-grain-row' : ''}><td><button className="text-button" aria-pressed={selectedGrain === g.grano} onClick={() => setSelectedGrain(g.grano)}>#{g.grano}</button>{g.toca_borde && ' *'}</td><td>{g.largo}</td><td>{g.ancho}</td><td>{g.area}</td><td>{g.perimetro ?? '—'}</td><td>{g.razon_aspecto}</td><td>{g.circularidad ?? '—'}</td><td>{g.solidez}</td><td>{g.L}</td><td>{g.a}</td><td>{g.b}</td><td><span className="swatch" style={{backgroundColor:g.color_hex}}/>{g.color_hex} · {colorName(g.color_hex)}</td></tr>)}</tbody></table></div>
          <div className="exports"><button disabled={historyBusy} onClick={saveSample}>{historyBusy ? 'Guardando…' : savedId ? 'Guardar cambios de la muestra' : 'Guardar muestra'}</button><button onClick={() => saveFile('\ufeff'+result.csv, `${safeName}_granos.csv`, 'text/csv;charset=utf-8')}><Download size={16}/> Descargar CSV</button><a href={view === 'original' ? preview : view === 'overlay' ? result.overlay : result.stages?.[view]} download={view === 'original' ? file?.name : `${safeName}_${view}.png`}><Download size={16}/> Guardar esta vista</a></div>
          <details className="warnings" open><summary>Observaciones del análisis</summary>{result.count > 0 ? <div className="analysis-summary"><p>Se identificaron <strong>{result.count} granos</strong> en la muestra <strong>{result.sample}</strong>.</p><p>El largo promedio es <strong>{result.mean_length} {result.unit}</strong>, el ancho promedio <strong>{(result.grains.reduce((total,g) => total + g.ancho,0) / result.count).toFixed(3)} {result.unit}</strong> y el área promedio <strong>{result.mean_area} {result.unit}²</strong>.</p><p>Los largos van de {Math.min(...result.grains.map(g => g.largo)).toFixed(3)} a {Math.max(...result.grains.map(g => g.largo)).toFixed(3)} {result.unit}; los anchos, de {Math.min(...result.grains.map(g => g.ancho)).toFixed(3)} a {Math.max(...result.grains.map(g => g.ancho)).toFixed(3)} {result.unit}.</p><p>{result.discarded ? `${result.discarded} objetos quedaron fuera por los filtros de tamaño o elongación. Revisa la segmentación para comprobar que no sean granos válidos.` : 'Todos los objetos detectados cumplieron los filtros de tamaño y elongación.'} {result.grains.filter(g => g.toca_borde).length > 0 && `${result.grains.filter(g => g.toca_borde).length} granos tocan el borde; amplía el recorte para medirlos completos.`}</p><p>Estas medidas permiten describir el tamaño y la variación dentro de esta muestra. Para comparar tamaños entre fotografías, calibra cada imagen con una referencia de longitud.</p></div> : <p className="stage-description">No se identificaron granos que cumplan los filtros. Revisa la fotografía, el recorte y los parámetros antes de repetir el análisis.</p>}<ul>{result.warnings.map(w => <li key={w}>{w}</li>)}</ul></details>

        </>}
      </section></div>
      <LocalMetadataForm sample={file?.name||sample} onSaved={data=>{metadataCatalog.current=data;setMetadata(data);setMetaSaved(true);setMetaKey('nombre_nuevo');setMetaId(file?.name||sample);}}/><section className="panel metadata-panel"><div className="panel-title"><span className="step">03</span><h3>Datos registrados de la muestra</h3></div><p className="stage-description">Reutiliza el archivo guardado: cada fila describe una muestra completa, identificada por su fotografía. Consulta los registros de la planta, mazorca, peso y rendimiento de cada muestra.</p><div className="exports"><button disabled={metaBusy} onClick={loadSavedMetadata}>Recuperar archivo de muestras guardado</button></div><label>Seleccionar un archivo nuevo · CSV o Excel (.xlsx)<input type="file" accept=".csv,.xlsx" disabled={metaBusy} onChange={e => uploadMetadata(e.target.files?.[0])}/></label>{metaBusy && <p role="status">Leyendo metadatos…</p>}{metaError && <p className="error" role="alert">{metaError}</p>}{metadata && <>{metaFile && <div className="exports"><button disabled={metaBusy || metaSaved} onClick={() => uploadMetadata(metaFile, true)}>{metaSaved ? 'Guardado para futuras consultas' : 'Guardar para futuras consultas'}</button></div>}<div className="help"><p>{metadata.rows.length} muestras registradas · {metadata.columns.length} campos</p><details><summary>Archivo de origen</summary>{metadata.filename}</details></div><div className="calibration"><label>Columna que identifica la muestra<select value={metaKey} onChange={e => setMetaKey(e.target.value)}>{metadata.columns.map(c => <option key={c} value={c}>{metadataLabel(c)}</option>)}</select></label><label>Identificador de la muestra<input value={metaId} onChange={e => setMetaId(e.target.value)}/></label></div><p className="help">La asociación busca el identificador de la fotografía. Grano_05.jpg se asocia con la fila de esa muestra; estos datos describen la muestra completa, no el grano número 5 de la tabla.</p>{matches.length === 1 ? <><h3>Datos registrados de la muestra {metaId}</h3><div className="metadata-values">{metadata.columns.map(c => <div key={c}><span title={c}>{metadataLabel(c)}</span><strong>{matches[0][c] || '—'}</strong></div>)}</div></> : <p className="notice">{matches.length ? 'Hay identificadores duplicados. Corrige el archivo para asociar una sola fila.' : 'No hay coincidencia. Revisa la columna y el identificador.'}</p>}<details><summary>Vista previa del archivo (primeras 5 muestras)</summary><div className="table-scroll"><table><thead><tr>{metadata.columns.map(c => <th key={c} title={c}>{metadataLabel(c)}</th>)}</tr></thead><tbody>{metadata.rows.slice(0,5).map((row,i) => <tr key={i}>{metadata.columns.map(c => <td key={c}>{row[c]}</td>)}</tr>)}</tbody></table></div></details><p className="help">{metaSaved ? 'El archivo está guardado en SIMAC y puede reutilizarse en futuras consultas.' : 'Puedes guardar este archivo para reutilizarlo en futuras consultas.'}</p></>}</section>
      <section className="panel metadata-panel"><div className="panel-title"><h3>Historial de muestras</h3></div><p className="stage-description">Fotografías y resultados guardados en SIMAC.</p><div className="exports"><button disabled={busy || historyBusy || historyLoading} onClick={refreshHistory}>{historyLoading ? 'Consultando…' : 'Actualizar historial'}</button></div>{deleteTarget && <div className="notice"><p>¿Eliminar la muestra “{deleteTarget.name}” del historial?</p><div className="exports"><button disabled={historyBusy} onClick={() => changeHistory(deleteTarget.id,'delete')}>Confirmar eliminación</button><button disabled={historyBusy} onClick={() => setDeleteTarget(null)}>Cancelar</button></div></div>}{lastDeleted && <div className="notice">Muestra “{lastDeleted.name}” eliminada del historial. <button className="text-button" disabled={historyBusy} onClick={() => changeHistory(lastDeleted.id,'restore')}>Deshacer eliminación</button></div>}{historyError && <p className="error" role="alert">{historyError}</p>}{!history.length ? historyLoaded && !historyError && !historyLoading ? <p className="help">Todavía no hay muestras guardadas. Después de analizar una foto, pulsa “Guardar muestra”.</p> : null : <div className="table-scroll"><table><thead><tr><th>Muestra</th><th>Fecha</th><th>Granos</th><th>Acciones</th></tr></thead><tbody>{history.map(item => <tr key={item.id}><td>{editingId === item.id ? <form onSubmit={e => {e.preventDefault();void changeHistory(item.id,'rename');}}><input aria-label="Nuevo nombre de muestra" maxLength={120} required value={editName} onChange={e => setEditName(e.target.value)}/><button className="text-button" disabled={historyBusy || !editName.trim()} type="submit">Guardar nombre</button><button className="text-button" type="button" onClick={() => setEditingId('')}>Cancelar</button></form> : item.name}</td><td>{new Date(item.created).toLocaleString('es-MX')}</td><td>{item.count}</td><td><button className="text-button" disabled={busy || historyBusy} onClick={() => openSample(item.id)}>Ver resultados</button><button className="text-button history-action" disabled={busy || historyBusy} onClick={() => {setEditingId(item.id);setEditName(item.name);}}>Modificar nombre</button><button className="text-button history-action danger" disabled={busy || historyBusy} onClick={() => setDeleteTarget(item)}>Eliminar</button></td></tr>)}</tbody></table></div>}</section>
      </div>
      {section==='agriculture'&&<AgriculturePanel/>}
      {section==='models'&&<ModelAdmin onUpdated={()=>setModelRevision(v=>v+1)}/>}
    </main>
  </>;
}

const rootElement=document.getElementById('root')! as HTMLElement & {simacRoot?:Root};
const applicationRoot=rootElement.simacRoot??(rootElement.simacRoot=createRoot(rootElement));
applicationRoot.render(<React.StrictMode><Portal laboratory={<Laboratory/>}/></React.StrictMode>);
