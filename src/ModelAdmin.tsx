import { useEffect, useState } from 'react';
import { YieldExperiment } from './SvmPanel';
type Version={id:string;created:string;active:boolean;mode:string;experimental:boolean;parameters:{kernel:string;feature:string};test_metrics:{correct:number;total:number}};
export function ModelAdmin({onUpdated}:{onUpdated?:()=>void}){
  const [versions,setVersions]=useState<Version[]>([]);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const [warnings,setWarnings]=useState<string[]>([]);
  async function refresh(){try{const r=await fetch('/api/models');if(!r.ok)throw new Error('No se pudieron consultar los modelos.');const data=await r.json();setVersions(data.models);setWarnings(data.warnings||[]);setError('');onUpdated?.();}catch(e){setError(e instanceof Error?e.message:'Sin conexión.');}}
  useEffect(()=>{void refresh();},[]);
  async function activate(id:string){setBusy(true);try{const r=await fetch(`/api/models/${id}/activate`,{method:'POST'});if(!r.ok)throw new Error((await r.json()).detail||'No se pudo activar.');await refresh();}catch(e){setError(e instanceof Error?e.message:'Error de conexión.');}finally{setBusy(false);}}
  return <><section className="panel metadata-panel"><div className="panel-title"><h2>Administración de modelos</h2></div><p>Entrena y revisa versiones aquí. En el análisis de muestras se utiliza la versión activa sin repetir el entrenamiento. La activación conserva su condición experimental.</p>
    {error&&<p className="error" role="alert">{error}</p>}
    {warnings.map(message=><p className="notice" key={message}>{message}</p>)}
    <div className="exports"><button disabled={busy} onClick={refresh}>Actualizar versiones</button></div>
    {!versions.length?<p className="notice">Aún no hay un modelo entrenado de rendimiento. Reúne muestras con mediciones y rendimiento real; después entrena y activa una versión.</p>:<div className="table-scroll"><table><thead><tr><th>Versión</th><th>Modelo</th><th>Prueba reservada</th><th>Estado</th><th>Uso</th></tr></thead><tbody>{versions.map(v=><tr key={v.id}><td>{v.id.slice(0,8)}<br/>{new Date(v.created).toLocaleString('es-MX')}</td><td>{v.parameters.kernel} · {v.mode}</td><td>{v.test_metrics.correct}/{v.test_metrics.total}</td><td>{v.active?'Activa · experimental':'Disponible · experimental'}</td><td><button disabled={busy||v.active} onClick={()=>activate(v.id)}>{v.active?'En uso':'Usar esta versión'}</button></td></tr>)}</tbody></table></div>}
    <p className="help">Los modelos anteriores se conservan para volver a ellos. Activar una versión no la convierte en una validación agronómica.</p></section>
    <details className="panel training-details"><summary>Preparar datos y entrenar modelos</summary><YieldExperiment onTrained={refresh}/></details></>;
}
