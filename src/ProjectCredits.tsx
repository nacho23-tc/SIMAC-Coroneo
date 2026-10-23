import {Download,ExternalLink} from 'lucide-react';

export const researchAcknowledgement = 'Los cultivos de maíz, la obtención de variables, las imágenes y el código fuente inicial que sirven como base de este trabajo fueron desarrollados en un proyecto de investigación del Instituto Tecnológico Superior de Irapuato (ITESI) y la Universidad Autónoma Agraria Antonio Narro (UAAAN). SIMAC Coroneo da continuidad a esa base mediante su adaptación a una aplicación web y la integración de una colección regional de muestras.';

export const teamResponsibilities = [
 {name:'Guadalupe Lizeth Garduño Muñoz',role:'Capitana del equipo; coordinación de actividades, seguimiento de avances y organización de entregables.'},
 {name:'Ximena Carrillo Pérez',role:'Apoyo en el desarrollo e integración de la plataforma, revisión de funcionalidades y pruebas.'},
 {name:'Leslie Licea García',role:'Organización de muestras, identificación, registro de procedencia y documentación fotográfica.'},
 {name:'Alonso Pérez Gómez',role:'Apoyo en programación, procesamiento de imágenes, pruebas y revisión de resultados.'}
];
export const sharedResponsibility = 'Investigación, capacitaciones, documentación, actividades de recolección y preparación de la presentación final.';

const resources = [
 {title:'Material de formación y datos iniciales',text:'TrackTalents ITESI 2026: sesiones 3 y 4, “De medir granos a predecir el rendimiento”. Cuadernos de referencia para la extracción de características y la clasificación. Las imágenes y variables iniciales proceden del proyecto de investigación ITESI–UAAAN; se distinguen de la colecta regional del equipo.',links:[]},
 {title:'Modelos y análisis de imágenes',text:'Cellpose 3.1.1.2, modelo cyto3 preentrenado, de Carsen Stringer, Marius Pachitariu y colaboradores; PyTorch, scikit-image y Pillow para el procesamiento. scikit-learn para SVM, regresión Ridge, selección de variables y evaluación.',links:[['Cellpose y cyto3','https://cellpose.readthedocs.io/en/v3.1.1.1/models.html'],['PyTorch','https://pytorch.org/'],['scikit-image','https://scikit-image.org/'],['Pillow','https://pillow.readthedocs.io/'],['scikit-learn','https://scikit-learn.org/stable/']]},
 {title:'Fuentes de información',text:'CONABIO: información sobre la diversidad de los maíces. “Studies on Physical Properties of Different Corn (Zea mays L.) Verities”, DOI 10.18805/ajdfr.DR-1991: referencia publicada de peso, diferenciada de los pesajes locales.',links:[['Maíces · CONABIO','https://biodiversidad.gob.mx/diversidad/alimentos/maices'],['Estudio de propiedades físicas','https://arccjournals.com/journal/asian-journal-of-dairy-and-food-research/DR-1991']]},
 {title:'Desarrollo de la aplicación',text:'Python, FastAPI y Uvicorn para el servidor; SQLite para los registros; NumPy y openpyxl para cálculos y archivos. React, TypeScript, Vite y Lucide para la interfaz web y sus iconos. OpenAI Codex como herramienta de asistencia en programación, revisión y documentación.',links:[['Python','https://www.python.org/'],['FastAPI','https://fastapi.tiangolo.com/'],['Uvicorn','https://www.uvicorn.org/'],['SQLite','https://www.sqlite.org/'],['NumPy','https://numpy.org/'],['openpyxl','https://openpyxl.readthedocs.io/'],['React','https://react.dev/'],['TypeScript','https://www.typescriptlang.org/'],['Vite','https://vite.dev/'],['Lucide','https://lucide.dev/']]},
 {title:'Asistente Elotín',text:'Groq como proveedor de inferencia del modelo de lenguaje openai/gpt-oss-20b, de OpenAI, y una guía local de respaldo. El asistente orienta sobre el uso de SIMAC; no realiza las mediciones ni valida los modelos agrícolas.',links:[['Groq','https://console.groq.com/docs/overview'],['Modelo gpt-oss-20b','https://huggingface.co/openai/gpt-oss-20b']]},
 {title:'Fotografías y aportaciones comunitarias',text:'El equipo proporcionó las fotografías de la colecta, del montaje de muestras y de sus integrantes, así como los recursos gráficos de identidad. Se agradece a las personas productoras y donantes de Coroneo y localidades cercanas por las semillas y la información de procedencia. Las imágenes de las 80 muestras documentan el avance de la colecta; no representan por sí solas ensayos de rendimiento.',links:[]}
];

const creditsText = `SIMAC CORONEO — CRÉDITOS Y RECONOCIMIENTOS

ORIGEN DE LA INVESTIGACIÓN
${researchAcknowledgement}

Instituto Tecnológico Superior de Irapuato (ITESI)
Dr. Jorge Noé García Chávez
Dr. Juan Pablo Serrano Rubio
Ing. Sergio Ismael Torres Sánchez

Universidad Autónoma Agraria Antonio Narro (UAAAN)
Dra. Ana Laura Alonso Nieves

CONTINUIDAD Y ADAPTACIÓN DEL PROYECTO
CECyTE Guanajuato, Unidad Académica Coroneo
Alumnado participante: Ximena Carrillo Pérez, Guadalupe Lizeth Garduño Muñoz, Leslie Licea García y Alonso Pérez Gómez.
DISTRIBUCIÓN PROPUESTA DE RESPONSABILIDADES
${teamResponsibilities.map(member=>member.name+': '+member.role).join('\n')}
Todo el equipo: ${sharedResponsibility}

Colaboradores de apoyo: Anyi Sherlin Ruiz Loyola y Cristian Uriel Rubio García.
Asesor: Ignacio Tinajero Camacho.
Colecta regional, organización de materiales, registro fotográfico y adaptación de la base de investigación al flujo de SIMAC.

FORMACIÓN
TrackTalents ITESI 2026 y las personas asesoras y docentes participantes.

FUENTES, HERRAMIENTAS Y RECURSOS
${resources.map(item=>item.title+'\n'+item.text+'\n'+item.links.map(([label,url])=>label+': '+url).join('\n')).join('\n\n')}
`;

export function ProjectCredits(){
 function download(){
  const url=URL.createObjectURL(new Blob(['\ufeff'+creditsText],{type:'text/plain;charset=utf-8'}));
  const anchor=document.createElement('a');anchor.href=url;anchor.download='SIMAC_creditos_y_reconocimientos.txt';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 return <div id="creditos" className="project-credits"><div className="credits-heading"><div><span className="eyebrow">CRÉDITOS Y RECONOCIMIENTOS</span><h3>Las contribuciones que hacen posible SIMAC.</h3></div><button type="button" onClick={download}><Download size={17}/> Descargar créditos</button></div><p>Agradecemos a TrackTalents ITESI 2026 por el espacio de formación, y a las instituciones, personas investigadoras, asesoras, docentes y comunidades que contribuyen al proyecto.</p><div className="credits-resources">{resources.map(resource=><details key={resource.title}><summary>{resource.title}</summary><p>{resource.text}</p>{resource.links.length>0&&<ul>{resource.links.map(([label,url])=><li key={url}><a href={url} target="_blank" rel="noreferrer">{label} <ExternalLink size={12} aria-hidden="true"/></a></li>)}</ul>}</details>)}</div></div>;
}
