"""Validación compartida para resultados recibidos del laboratorio."""
import json
from .yield_experiment import number


def validate_payload(data):
    if not isinstance(data,dict) or not isinstance(data.get('result'),dict):
        raise ValueError('El resultado de la muestra debe ser un objeto válido.')
    result=data['result']
    if not isinstance(result.get('sample'),str) or not 1 <= len(result['sample'].strip()) <= 120:
        raise ValueError('El nombre de muestra debe tener entre 1 y 120 caracteres.')
    grains=result.get('grains')
    if not isinstance(grains,list) or len(grains)>100000 or any(not isinstance(g,dict) for g in grains):
        raise ValueError('La lista de granos no es válida.')
    if result.get('unit') not in ('px','mm'):
        raise ValueError('La unidad del resultado debe ser px o mm.')
    for key in ['review','parameters','weight_inputs']:
        if key in data and not isinstance(data[key],dict):
            raise ValueError('El campo '+key+' no es válido.')
    for key, flag in [('review','reviewed'),('weight_inputs','measured')]:
        if flag in data.get(key,{}) and not isinstance(data[key][flag],bool):
            raise ValueError('El campo '+flag+' debe ser verdadero o falso.')
    metadata=data.get('metadata')
    if metadata is not None:
        if not isinstance(metadata,dict) or not isinstance(metadata.get('rows'),list) or any(not isinstance(r,dict) for r in metadata['rows']):
            raise ValueError('Los datos asociados no son válidos.')
        if 'key' in metadata and not isinstance(metadata['key'],str):
            raise ValueError('La columna identificadora no es válida.')
    identifiers=[]
    for grain in grains:
        identifier=grain.get('grano')
        if not isinstance(identifier,int) or isinstance(identifier,bool) or identifier<1:
            raise ValueError('Cada grano debe tener un número entero positivo.')
        identifiers.append(identifier)
        for key in ['largo','ancho','area','perimetro','circularidad','razon_aspecto','solidez','L','a','b']:
            if key in grain and grain[key] is not None and number(grain[key]) is None:
                raise ValueError('Hay una medida de grano que no es finita: '+key)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Los números de grano no deben estar duplicados.')
    try:
        json.dumps(data,allow_nan=False)
    except (ValueError,TypeError):
        raise ValueError('Los datos contienen valores no válidos o no finitos.')
    return data
