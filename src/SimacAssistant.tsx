import {useEffect,useRef,useState} from 'react';
import {X,Send,LoaderCircle} from 'lucide-react';
const topics=[
 {title:'Analizar una muestra',keys:['analiz','foto','imagen','contar'],answer:'Abre el laboratorio, carga una fotografía nítida con los granos separados sobre un fondo de contraste y analiza la muestra. Después revisa los contornos: corrige las detecciones antes de confirmar y guardar los resultados.',link:'#laboratorio'},
 {title:'Calibrar milímetros',keys:['calibr','milimet','milímet','regla','escala'],answer:'Incluye una regla en el mismo plano que los granos. En la calibración del análisis, marca una distancia de la imagen e indica su longitud real en milímetros. Vuelve a analizar para obtener dimensiones físicas. Una foto sin referencia solo permite medir en píxeles.',link:'#laboratorio'},
 {title:'Registrar materiales y familias',keys:['registr','familia','material','parcela','csv'],answer:'En Laboratorio → Registro agrícola puedes registrar materiales y su procedencia, asociar fotografías y documentar familias, parcelas, observaciones y cruzamientos. Crea primero la familia si conoces su parentesco; el color por sí solo no lo demuestra. También puedes importar una plantilla CSV.',link:'#laboratorio'},
 {title:'Peso y rendimiento',keys:['peso','rendimiento','svm','predic','alto','bajo'],answer:'El peso mostrado es una estimación según su referencia, no una pesada de báscula. El SVM clasifica Alto/Bajo de forma experimental: no equivale a toneladas por hectárea validadas. El registro agrícola calcula t/ha cuando aportas cosecha y superficie medidas. Para mejorar modelos se necesitan datos de campo y evaluación independiente.',link:'#laboratorio'},
 {title:'Participar en SIMAC',keys:['particip','contact','equipo','colabor'],answer:'Puedes aportar semillas documentadas, fotografías o mediciones de campo. Conserva la clave del lote y su procedencia. Escríbenos a simaccoroneo@gmail.com o consulta Cómo participar.',link:'#participar'}
];
const connectionNotes:Record<string,string>={
 invalid_request:'Groq no aceptó la configuración o la consulta. Revisa la clave y el modelo del servidor.',
 invalid_model:'Configura el ID del modelo: ese campo no admite una clave API.',
 authentication:'La clave API no fue aceptada. Revisa la configuración del servidor.',
 access_denied:'La cuenta API no tiene acceso a esta consulta.',
 model_unavailable:'El modelo configurado no está disponible para esta cuenta.',
 provider_limit:'Se alcanzó un límite de uso o saldo del proveedor. Continúa la guía local.',
 sensitive:'No se enviaron claves. No compartas credenciales en el chat.'
};
function Corn(){return <img className="elotin-mascot" src="/elotin-mascota.png" alt="" aria-hidden="true"/>}
export function SimacAssistant(){
 const [compact,setCompact]=useState(false);
 const [connectionReason,setConnectionReason]=useState('');
 const [available,setAvailable]=useState(false),[useAI,setUseAI]=useState(false),[busy,setBusy]=useState(false);
 const pending=useRef(false),requestController=useRef<AbortController|null>(null);
 useEffect(()=>()=>requestController.current?.abort(),[]);
 const [open,setOpen]=useState(false),[input,setInput]=useState('');
 const [messages,setMessages]=useState<{text:string;user?:boolean;link?:string;mode?:'ai'|'local';note?:string}[]>([{text:'¡Hola! Soy Elotín, la guía de SIMAC. Te ayudo a encontrar funciones y entender los resultados. ¿Por dónde empezamos?'}]);
 const launcher=useRef<HTMLButtonElement>(null),field=useRef<HTMLInputElement>(null),feed=useRef<HTMLDivElement>(null);
 useEffect(()=>{if(open)field.current?.focus()},[open]);
 useEffect(()=>{if(feed.current)feed.current.scrollTop=feed.current.scrollHeight},[messages]);
 function close(){setOpen(false);launcher.current?.focus()}
 useEffect(()=>{if(!open)return;const controller=new AbortController();fetch('/api/assistant/status',{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error();return r.json()}).then(data=>{if(!controller.signal.aborted){setAvailable(data.available===true);setConnectionReason(data.reason||'')}}).catch(()=>{if(!controller.signal.aborted)setAvailable(false)});return()=>controller.abort()},[open]);
 async function ask(text:string,localOnly=false){
  const question=text.trim();if(!question||pending.current)return;
  const normalized=question.toLocaleLowerCase('es');const topic=topics.find(t=>t.title===question)||[...topics.slice(1),topics[0]].find(t=>t.keys.some(k=>normalized.includes(k)));
  const fallback=topic?.answer||'Puedo ayudarte con análisis, calibración, registro agrícola, peso, rendimiento y participación. Elige un tema o pregunta indicando el campo que necesitas entender. No consulto fotografías ni registros privados desde este chat.';
  const history=messages.slice(1).slice(-6).map(m=>({role:m.user?'user':'assistant',content:m.text.slice(0,1200)}));
  setMessages(m=>[...m.slice(-19),{text:question,user:true}]);setInput('');
  if(!useAI||!available||localOnly){setMessages(m=>[...m,{text:fallback,link:topic?.link,mode:'local'}]);return;}
  pending.current=true;setBusy(true);const controller=new AbortController();requestController.current=controller;
  const timeout=window.setTimeout(()=>controller.abort(),16000);
  try{
   const response=await fetch('/api/assistant/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:question,history,use_ai:true}),signal:controller.signal});
   if(!response.ok)throw new Error('fallback');const data=await response.json();
   if(data.mode==='ai'&&typeof data.answer==='string'&&data.answer.trim()){setMessages(m=>[...m,{text:data.answer,mode:'ai'}]);}
   else {setMessages(m=>[...m,{text:fallback,link:topic?.link,mode:'local',note:connectionNotes[data.reason]||'IA no disponible para esta consulta; responde la guía local.'}]);}
  }catch{setMessages(m=>[...m,{text:fallback,link:topic?.link,mode:'local',note:'No se pudo consultar la IA; responde la guía local.'}]);}
  finally{window.clearTimeout(timeout);pending.current=false;setBusy(false);requestController.current=null;}
 }
 return <aside className={`simac-assistant ${compact?'is-compact':''} ${open?'is-open':''}`} aria-label="Asistente de SIMAC">{open&&<section className="assistant-panel" role="region" aria-label="Conversación con Elotín" onKeyDown={e=>{if(e.key==='Escape')close()}}><header><Corn/><div><strong>Elotín</strong><span>Tu guía de SIMAC</span></div><button onClick={close} aria-label="Cerrar asistente"><X size={20}/></button></header><div className="assistant-disclosure"><label className="assistant-ai-toggle"><input type="checkbox" checked={useAI} disabled={!available||busy} onChange={e=>setUseAI(e.target.checked)}/> Usar IA cuando esté disponible</label><p>{available?'Con IA activada, tu pregunta y hasta 6 mensajes recientes se envían a Groq. No incluyas datos personales.':(connectionNotes[connectionReason]||'Guía local disponible. La conexión de IA aún no está configurada o no responde.')} Los accesos rápidos usan respuestas locales.</p></div><div className="assistant-feed" ref={feed} role="log" aria-live="polite" aria-relevant="additions">{messages.map((m,i)=><div key={i} className={m.user?'assistant-message user':'assistant-message'}><p>{m.text}</p>{m.mode&&<small className="assistant-answer-source">{m.mode==='ai'?'Respuesta con IA · Puede contener errores':'Guía local'}</small>}{m.note&&<small className="assistant-fallback-note">{m.note}</small>}{m.link&&<a href={m.link} onClick={close}>Ir a esta sección →</a>}</div>)}</div>{busy&&<p className="assistant-thinking" role="status"><LoaderCircle size={14} className="spin"/> Elotín está consultando…</p>}<div className="assistant-topics">{topics.map(t=><button key={t.title} disabled={busy} onClick={()=>void ask(t.title,true)}>{t.title}</button>)}</div><form onSubmit={e=>{e.preventDefault();ask(input)}}><input ref={field} aria-label="Tu pregunta para Elotín" placeholder="¿Cómo calibro mi muestra?" value={input} maxLength={800} disabled={busy} onChange={e=>setInput(e.target.value)}/><button aria-label="Enviar pregunta" disabled={busy||!input.trim()}><Send size={18}/></button></form></section>}<button className="assistant-launcher" ref={launcher} onClick={()=>open?close():setOpen(true)} aria-expanded={open} aria-label={open?'Cerrar guía Elotín':'Abrir guía Elotín'}><Corn/><span>¿Te ayudo?<small>Elotín</small></span></button>{!open&&<button className="assistant-minimize" aria-label={compact?'Ampliar botón de Elotín':'Minimizar botón de Elotín'} onClick={()=>setCompact(v=>!v)}>{compact?'+':'−'}</button>}</aside>
}
