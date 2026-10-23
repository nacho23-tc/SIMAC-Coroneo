import {useEffect,useState} from 'react';

export function FooterAddress(){
 const [address,setAddress]=useState(''),[notice,setNotice]=useState('');
 useEffect(()=>{
  let controller:AbortController|null=null;
  async function refresh(){
   controller?.abort();controller=new AbortController();const current=controller;
   try{
    const response=await fetch('/api/network',{signal:current.signal,cache:'no-store'});
    if(!response.ok)throw new Error();const data=await response.json();
    const ips:string[]=(data.addresses||[]).filter((v:unknown)=>typeof v==='string'&&/^\d+\.\d+\.\d+\.\d+$/.test(v));
    const host=ips.includes(location.hostname)?location.hostname:ips[0];
    if(!current.signal.aborted)setAddress(host?`${location.protocol}//${host}${location.port?':'+location.port:''}/`:'');
   }catch{if(!current.signal.aborted)setAddress('');}
  }
  void refresh();const timer=setInterval(()=>{if(!document.hidden)void refresh()},30000);
  const focus=()=>void refresh();window.addEventListener('focus',focus);
  return()=>{controller?.abort();clearInterval(timer);window.removeEventListener('focus',focus)};
 },[]);
 useEffect(()=>{if(!notice)return;const timer=setTimeout(()=>setNotice(''),3500);return()=>clearTimeout(timer)},[notice]);
 async function copy(){
  let success=false;
  try{if(navigator.clipboard){await navigator.clipboard.writeText(address);success=true;}}catch{/* Copia compatible con acceso por HTTP local. */}
  if(!success){
   const field=document.createElement('textarea');field.value=address;field.readOnly=true;
   field.style.cssText='position:fixed;left:-9999px;top:0';document.body.appendChild(field);
   const previous=document.activeElement;
   try{field.select();field.setSelectionRange(0,address.length);success=document.execCommand('copy');}catch{success=false;}
   finally{field.remove();if(previous instanceof HTMLElement)previous.focus();}
  }
  setNotice(success?'Dirección copiada':'Mantén pulsada la dirección para copiarla');
 }
 if(!address)return null;
 return <div className="footer-address"><button type="button" onClick={()=>void copy()} aria-label={`Copiar dirección ${address}`} title="Copiar dirección">{address}</button><span role="status" aria-live="polite">{notice}</span></div>;
}
