type AppearanceGrain = {color_hex?:string;razon_aspecto?:number;largo?:number;ancho?:number};
export function colorName(hex?:string):string {
  if(!/^#[0-9a-f]{6}$/i.test(hex||''))return 'Color no disponible';
  const [r,g,b]=[1,3,5].map(i=>parseInt(hex!.slice(i,i+2),16)/255);
  const max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;
  const s=max?d/max:0;
  const h=d?((max===r?(g-b)/d+(g<b?6:0):max===g?(b-r)/d+2:(r-g)/d+4)*60):0;
  if(max<.2)return 'Negro';
  if(s<.13)return max>.85?'Blanquecino':max>.55?'Gris claro':'Gris oscuro';
  if(h<20||h>=345)return max<.65?'Marrón rojizo':'Rojo ladrillo';
  if(h<48)return max<.65?'Marrón':s<.35?'Crema':'Ocre anaranjado';
  if(h<75)return s<.35?'Crema amarillento':'Amarillo';
  if(h<170)return 'Verdoso';
  if(h<260)return 'Azulado';
  return 'Morado';
}
export function shapeName(g:AppearanceGrain):string {
  const ratio=g.razon_aspecto??(g.ancho?Number(g.largo)/g.ancho:NaN);
  if(!Number.isFinite(ratio)||ratio<1)return 'Forma no disponible';
  return ratio<=1.2?'Redondeada':ratio<=1.65?'Ovalada':'Alargada';
}
export function sampleAppearance(grains:AppearanceGrain[]){
  const describe=(names:string[])=>Object.entries(names.reduce<Record<string,number>>((a,n)=>{a[n]=(a[n]||0)+1;return a;},{})).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([name,count])=>`${name.toLocaleLowerCase('es')} (${Math.round(count/names.length*100)} %)`).join(', ');
  return {color:describe(grains.map(g=>colorName(g.color_hex)))||'Sin granos',shape:describe(grains.map(shapeName))||'Sin granos'};
}
