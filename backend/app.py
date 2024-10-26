from flask import Flask, request, jsonify
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import unicodedata
import re
import os

app = Flask(__name__)

def normalizar(texto):
    if texto is None:
        return ""
    # Convertir a minúsculas y eliminar tildes
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('utf-8').lower()
    # Eliminar espacios extras
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def extraer_fecha(mensaje):
    # Buscar el patrón de fecha en el mensaje
    patron = r"Lugar y fecha:.*?,\s*(\d{2}/\d{2}/\d{4})"
    match = re.search(patron, mensaje)
    if match:
        return match.group(1)
    return None

def validar_xml(root):
    return root.tag == 'solicitud_clasificacion'

def procesar_diccionario(root):
    sentimientos_positivos = []
    sentimientos_negativos = []
    
    diccionario = root.find('diccionario')
    if diccionario is not None:
        # Procesar sentimientos positivos
        positivos = diccionario.find('sentimientos_positivos')
        if positivos is not None:
            for palabra in positivos.findall('palabra'):
                if palabra.text:
                    sentimientos_positivos.append(normalizar(palabra.text))
        
        # Procesar sentimientos negativos
        negativos = diccionario.find('sentimientos_negativos')
        if negativos is not None:
            for palabra in negativos.findall('palabra'):
                if palabra.text:
                    sentimientos_negativos.append(normalizar(palabra.text))

    return sentimientos_positivos, sentimientos_negativos

def clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos):
    if mensaje.text is None:
        return "neutro"
    
    contenido = normalizar(mensaje.text)
    palabras = contenido.split()
    
    palabras_positivas = sum(1 for palabra in palabras if palabra in sentimientos_positivos)
    palabras_negativas = sum(1 for palabra in palabras if palabra in sentimientos_negativos)
    
    if palabras_positivas > palabras_negativas:
        return "positivo"
    elif palabras_negativas > palabras_positivas:
        return "negativo"
    return "neutro"

def agrupar_por_fecha(mensajes, empresas_data, sentimientos_positivos, sentimientos_negativos):
    mensajes_por_fecha = {}
    
    for mensaje in mensajes:
        fecha = extraer_fecha(mensaje.text)
        if fecha not in mensajes_por_fecha:
            mensajes_por_fecha[fecha] = {
                'total': 0,
                'positivos': 0,
                'negativos': 0,
                'neutros': 0,
                'empresas': {}
            }
            
        # Incrementar contadores generales
        clasificacion = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
        mensajes_por_fecha[fecha]['total'] += 1
        mensajes_por_fecha[fecha][clasificacion + 's'] += 1
        
        # Analizar empresas y servicios mencionados
        contenido_normalizado = normalizar(mensaje.text)
        for empresa_data in empresas_data:
            nombre_empresa = normalizar(empresa_data.find('nombre').text)
            if nombre_empresa not in mensajes_por_fecha[fecha]['empresas']:
                mensajes_por_fecha[fecha]['empresas'][nombre_empresa] = {
                    'total': 0,
                    'positivos': 0,
                    'negativos': 0,
                    'neutros': 0,
                    'servicios': {}
                }
            
            empresa_mencionada = False
            servicios = empresa_data.find('servicios')
            if servicios is not None:
                for servicio in servicios.findall('servicio'):
                    nombre_servicio = normalizar(servicio.get('nombre'))
                    servicio_mencionado = False
                    
                    # Verificar menciones del servicio a través de sus alias
                    for alias in servicio.findall('alias'):
                        if alias.text and normalizar(alias.text) in contenido_normalizado:
                            servicio_mencionado = True
                            empresa_mencionada = True
                            break
                    
                    if servicio_mencionado:
                        if nombre_servicio not in mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios']:
                            mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio] = {
                                'total': 0,
                                'positivos': 0,
                                'negativos': 0,
                                'neutros': 0
                            }
                        
                        mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio]['total'] += 1
                        mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio][clasificacion + 's'] += 1
            
            if empresa_mencionada:
                mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['total'] += 1
                mensajes_por_fecha[fecha]['empresas'][nombre_empresa][clasificacion + 's'] += 1
    
    return mensajes_por_fecha

def crear_xml_respuesta(mensajes_por_fecha):
    root = ET.Element('lista_respuestas')
    
    for fecha, datos in mensajes_por_fecha.items():
        respuesta = ET.SubElement(root, 'respuesta')
        
        # Agregar fecha
        fecha_elem = ET.SubElement(respuesta, 'fecha')
        fecha_elem.text = f" {fecha} "
        
        # Agregar resumen de mensajes
        mensajes = ET.SubElement(respuesta, 'mensajes')
        ET.SubElement(mensajes, 'total').text = f" {datos['total']} "
        ET.SubElement(mensajes, 'positivos').text = f" {datos['positivos']} "
        ET.SubElement(mensajes, 'negativos').text = f" {datos['negativos']} "
        ET.SubElement(mensajes, 'neutros').text = f" {datos['neutros']} "
        
        # Agregar análisis por empresa
        analisis = ET.SubElement(respuesta, 'analisis')
        for nombre_empresa, datos_empresa in datos['empresas'].items():
            empresa = ET.SubElement(analisis, 'empresa', nombre=nombre_empresa)
            
            # Agregar mensajes de la empresa
            mensajes_empresa = ET.SubElement(empresa, 'mensajes')
            ET.SubElement(mensajes_empresa, 'total').text = f" {datos_empresa['total']} "
            ET.SubElement(mensajes_empresa, 'positivos').text = f" {datos_empresa['positivos']} "
            ET.SubElement(mensajes_empresa, 'negativos').text = f" {datos_empresa['negativos']} "
            ET.SubElement(mensajes_empresa, 'neutros').text = f" {datos_empresa['neutros']} "
            
            # Agregar servicios de la empresa
            servicios = ET.SubElement(empresa, 'servicios')
            for nombre_servicio, datos_servicio in datos_empresa['servicios'].items():
                servicio = ET.SubElement(servicios, 'servicio', nombre=nombre_servicio)
                
                # Agregar mensajes del servicio
                mensajes_servicio = ET.SubElement(servicio, 'mensajes')
                ET.SubElement(mensajes_servicio, 'total').text = f" {datos_servicio['total']} "
                ET.SubElement(mensajes_servicio, 'positivos').text = f" {datos_servicio['positivos']} "
                ET.SubElement(mensajes_servicio, 'negativos').text = f" {datos_servicio['negativos']} "
                ET.SubElement(mensajes_servicio, 'neutros').text = f" {datos_servicio['neutros']} "
    
    return root

def format_xml_pretty(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

@app.route('/clasificar', methods=['POST'])
def clasificar_mensajes():
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400

    archivo = request.files['archivo']
    
    try:
        tree = ET.parse(archivo)
        root = tree.getroot()
        
        if not validar_xml(root):
            return jsonify({'error': 'Estructura del XML no válida'}), 400
        
        # Procesar el diccionario y obtener los sentimientos
        sentimientos_positivos, sentimientos_negativos = procesar_diccionario(root)
        
        # Obtener la lista de mensajes y empresas
        mensajes = root.find('lista_mensajes').findall('mensaje')
        empresas_data = root.find('diccionario').find('empresas_analizar').findall('empresa')
        
        # Agrupar y analizar mensajes por fecha
        mensajes_por_fecha = agrupar_por_fecha(mensajes, empresas_data, sentimientos_positivos, sentimientos_negativos)
        
        # Crear el XML de respuesta
        respuesta_xml = crear_xml_respuesta(mensajes_por_fecha)
        
        # Formatear y devolver la respuesta
        output_xml = format_xml_pretty(respuesta_xml)
        return output_xml, 200, {'Content-Type': 'application/xml'}
        
    except ET.ParseError:
        return jsonify({'error': 'Error al procesar el archivo XML'}), 400

if __name__ == '__main__':
    app.run(debug=True)