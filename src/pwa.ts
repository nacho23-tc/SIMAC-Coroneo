// La caché de la PWA contiene únicamente la página de aviso sin conexión.
if ((import.meta as ImportMeta & {env:{PROD:boolean}}).env.PROD && window.isSecureContext && 'serviceWorker' in navigator) {
 window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js').catch(()=>{/* La web continúa disponible aunque la instalación no lo esté. */})});
}

