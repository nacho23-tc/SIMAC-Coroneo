import {useState} from 'react';
import {ArrowLeft,ArrowRight,MapPin,Camera,Sprout,ScanLine} from 'lucide-react';
import photos from './collectionPhotos.json';

export function ProjectCollection(){
 const [selected,setSelected]=useState(0);
 const photo=photos[selected];
 function move(offset:number){setSelected(value=>(value+offset+photos.length)%photos.length)}
 return <section id="desarrollo" className="public-section collection-section" aria-labelledby="collection-title">
  <div className="section-topline"><span className="eyebrow">TRABAJO DE CAMPO Y DESARROLLO</span><span>De la comunidad al registro</span></div>
  <div className="editorial-heading"><h2 id="collection-title">Cada muestra tiene<br/><em>un lugar de origen.</em></h2><p className="section-lead">Reunimos, identificamos y fotografiamos maíces de Coroneo y sus alrededores. Esta colección conecta el trabajo de las comunidades con el estudio de las semillas en SIMAC.</p></div>
  <div className="collection-layout"><div className="collection-viewer">
   <figure><img key={photo.src} src={photo.src} alt={photo.caption} width={photo.width} height={photo.height} loading="lazy" decoding="async"/><figcaption aria-live="polite"><span>{String(selected+1).padStart(2,'0')} / {photos.length}</span>{photo.caption}</figcaption></figure>
   <div className="collection-controls"><button type="button" onClick={()=>move(-1)} aria-label="Fotografía anterior de la colecta"><ArrowLeft size={18}/></button><span>Archivo fotográfico del equipo</span><button type="button" onClick={()=>move(1)} aria-label="Siguiente fotografía de la colecta"><ArrowRight size={18}/></button></div>
   <div className="collection-thumbnails" aria-label="Fotografías de la colecta">{photos.map((item,index)=><button type="button" key={item.src} aria-label={`Ver fotografía ${index+1}: ${item.caption}`} aria-pressed={selected===index} onClick={()=>setSelected(index)}><img src={item.src} alt="" loading="lazy" decoding="async"/></button>)}</div>
  </div><aside className="collection-facts"><span className="eyebrow">FICHA DE LA COLECTA</span><h3>Una colección regional,<br/>muchas historias.</h3><div className="collection-numbers"><div><strong>80</strong><span>muestras reunidas</span></div><div><strong>≈42</strong><span>localidades de colecta</span></div></div><p className="collection-date">Avance reportado por el equipo · Octubre de 2026</p><dl><dt>Territorio</dt><dd>Coroneo y Jerécuaro, Guanajuato; Huimilpan, Querétaro; Epitacio Huerta, Michoacán.</dd><dt>Identificación</dt><dd>Cada muestra conserva su propio código y lote, con la procedencia aportada por el equipo.</dd><dt>Objetivo</dt><dd>Documentar la diversidad de los maíces de la región y construir una base de imágenes y mediciones para su estudio.</dd></dl><a className="download-link" href="#participar">Ser parte de la colecta <ArrowRight size={16}/></a></aside></div>
  <div className="collection-process">{[
   {icon:MapPin,title:'Recolectar',text:'Reunir materiales de distintas personas productoras y localidades, conservando su procedencia.'},
   {icon:Sprout,title:'Identificar',text:'Asignar una clave por muestra y mantener los lotes separados con su ficha de registro.'},
   {icon:Camera,title:'Preparar y fotografiar',text:'Organizar los granos sobre fondo oscuro, con una regla y su identificación visible.'},
   {icon:ScanLine,title:'Analizar y documentar',text:'Usar SIMAC para revisar el conteo, medir características y vincular resultados con cada material.'}
  ].map(({icon:Icon,title,text},index)=><article key={title}><span className="collection-step"><Icon size={21}/><span>0{index+1}</span></span><h3>{title}</h3><p>{text}</p></article>)}</div>
  <p className="collection-outlook">El siguiente paso es vincular esta colección con pesajes y observaciones de campo para evaluar modelos de rendimiento, altura, floración y adaptación regional.</p>
  <a className="download-link" href="/Visual/">Ver archivo de fotografías · 80 muestras <ArrowRight size={16}/></a>
 </section>;
}
