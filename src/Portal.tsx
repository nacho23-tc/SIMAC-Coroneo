import { FooterAddress } from './ConnectionPanel';
import { useEffect, useState, type ReactNode } from 'react';
import { ArrowRight, ScanLine, Leaf, BookOpen } from 'lucide-react';
import {SimacAssistant} from './SimacAssistant';
import { PublicHome } from './PublicHome';

const sections = [['inicio','Inicio'],['proyecto','El proyecto'],['maiz','Maíz criollo'],['galeria','Galería'],['acerca','Acerca de'],['participar','Cómo participar'],['contacto','Contacto']];

export function Portal({laboratory}: {laboratory: ReactNode}) {
  const [route, setRoute] = useState(window.location.hash.slice(1) || 'inicio');
  const [signedIn, setSignedIn] = useState(sessionStorage.getItem('simac-demo-session') === 'active');
  const [user, setUser] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {const change = () => {setRoute(window.location.hash.slice(1) || 'inicio'); setError('');}; window.addEventListener('hashchange',change); return () => window.removeEventListener('hashchange',change);}, []);
  function login(e: React.FormEvent) {
    e.preventDefault();
    if (user.trim() !== 'usuario' || password !== 'Simac2026') {setError('Revisa el usuario y la contraseña.');return;}
    sessionStorage.setItem('simac-demo-session','active'); setSignedIn(true);setPassword('');setError('');
  }
  function logout() {sessionStorage.removeItem('simac-demo-session');setSignedIn(false);window.location.hash='inicio';}
  const inLab = route === 'laboratorio';
  useEffect(()=>{document.title=route==='laboratorio'?'SIMAC Coroneo · Laboratorio de semillas':'SIMAC Coroneo · Tecnología con origen';if(route==='laboratorio')return;const frame=requestAnimationFrame(()=>{const behavior=window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';if(route==='inicio')window.scrollTo({top:0,behavior});else document.getElementById(route)?.scrollIntoView({block:'start',behavior});});return()=>cancelAnimationFrame(frame);},[route]);
  return <>
    <header className="site-header"><a className="brand" href="#inicio"><img className="brand-logo" src="/simac.png" alt="SIMAC Coroneo"/><span>SIMAC Coroneo<small>TECNOLOGÍA CON ORIGEN</small></span></a><a className="site-lab-link" href="#laboratorio"><ScanLine size={16}/> Laboratorio <ArrowRight size={15}/></a></header>
    <nav className="site-nav" aria-label="Navegación principal">{sections.map(([id,label]) => <a key={id} href={`#${id}`} aria-current={!inLab && route===id?'location':undefined} className={!inLab && route === id ? 'active' : ''}>{label}</a>)}{signedIn && <button onClick={logout}>Cerrar sesión</button>}</nav>
    {inLab ? signedIn ? <><div className="lab-session"><span>Laboratorio de semillas · Usuario general</span><a href="#inicio">Volver al sitio</a></div>{laboratory}</> : <main className="login-page"><section className="login-intro"><span className="eyebrow">LABORATORIO DE SEMILLAS</span><h1>Una cuenta.<br/><em>Cada muestra, en detalle.</em></h1><p>Accede para cargar fotografías, revisar las etapas del análisis y consultar las características de tus granos.</p><div className="login-benefits"><span><ScanLine/> Conteo y dimensiones</span><span><Leaf/> Forma y color</span><span><BookOpen/> Metadatos y exportación</span></div></section><section className="panel login-card"><h2>Iniciar sesión</h2><p className="stage-description">Accede con la cuenta general de demostración.</p><form onSubmit={login}><label>Usuario<input autoComplete="username" required value={user} onChange={e => setUser(e.target.value)}/></label><label>Contraseña<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)}/></label>{error && <p className="error" role="alert">{error}</p>}<button className="primary" type="submit">Entrar al laboratorio <ArrowRight size={18}/></button></form><div className="demo-account"><strong>Cuenta de demostración</strong><p>Usuario: <code>usuario</code><br/>Contraseña: <code>Simac2026</code></p><small>Acceso de demostración. Las cuentas personales se habilitarán en una siguiente etapa.</small></div><a className="text-button" href="#inicio">Volver al inicio</a></section></main> : <PublicHome/>}
    <footer className="institutional-footer"><div className="footer-brand"><img src="/simac.png" alt="SIMAC Coroneo"/><div><strong>SIMAC Coroneo</strong><p>Conocer la semilla.<br/>Conservar nuestras raíces.</p></div></div><div className="footer-institution"><img src="/cecyte-guanajuato.png" alt="CECyTE Guanajuato"/><div><strong>CECyTE Guanajuato</strong><p>Unidad Académica Coroneo<br/>Proyecto educativo · Coroneo, Guanajuato</p></div></div><div className="footer-partner footer-itesi"><img src="/itesi.png" alt="Instituto Tecnológico Superior de Irapuato" loading="lazy"/></div><div className="footer-partner footer-uaaan"><img src="/uaaan.png" alt="Universidad Autónoma Agraria Antonio Narro" loading="lazy"/><span>Universidad Autónoma Agraria<br/>Antonio Narro</span></div><div className="footer-links"><a href="#proyecto">El proyecto</a><a href="#participar">Cómo participar</a><a href="mailto:simaccoroneo@gmail.com">simaccoroneo@gmail.com</a><a href="#creditos">Créditos y reconocimientos</a><a href="#inicio">Volver al inicio ↑</a></div><FooterAddress/></footer>
    <SimacAssistant/>
  </>;
}
