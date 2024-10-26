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
    
    # Contamos las palabras con sentimientos positivos y negativos
    palabras_positivas = sum(1 for palabra in palabras if palabra in sentimientos_positivos)
    palabras_negativas = sum(1 for palabra in palabras if palabra in sentimientos_negativos)
    
    # Si no hay palabras del diccionario, el mensaje es neutro
    if palabras_positivas == 0 and palabras_negativas == 0:
        return "neutro"
    
    # Si hay igual cantidad de palabras positivas y negativas, el mensaje es neutro
    if palabras_positivas == palabras_negativas:
        return "neutro"
        
    # Si hay más palabras positivas, el mensaje es positivo
    if palabras_positivas > palabras_negativas:
        return "positivo"
    
    # Si hay más palabras negativas, el mensaje es negativo
    return "negativo"

def agrupar_por_fecha(mensajes, empresas_data, sentimientos_positivos, sentimientos_negativos):
    mensajes_por_fecha = {}
    
    for mensaje in mensajes:
        fecha = extraer_fecha(mensaje.text)
        if not fecha:
            continue
            
        if fecha not in mensajes_por_fecha:
            mensajes_por_fecha[fecha] = {
                'total': 0,
                'positivos': 0,
                'negativos': 0,
                'neutros': 0,
                'empresas': {}
            }
        
        # Inicializar empresas si no existen
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
        
        # Clasificar mensaje general
        clasificacion_general = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
        mensajes_por_fecha[fecha]['total'] += 1
        mensajes_por_fecha[fecha][clasificacion_general + 's'] += 1
        
        # Analizar empresas y servicios mencionados
        for empresa_data in empresas_data:
            nombre_empresa = normalizar(empresa_data.find('nombre').text)
            empresa_mencionada = False
            
            # Verificar mención directa de la empresa
            if nombre_empresa in contenido_normalizado:
                empresa_mencionada = True
            
            servicios = empresa_data.find('servicios')
            if servicios is not None:
                for servicio in servicios.findall('servicio'):
                    nombre_servicio = normalizar(servicio.get('nombre'))
                    servicio_mencionado = False
                    
                    # Verificar menciones del servicio
                    for alias in servicio.findall('alias'):
                        if alias.text and normalizar(alias.text) in contenido_normalizado:
                            servicio_mencionado = True
                            empresa_mencionada = True
                            break
                    
                    # Si el servicio fue mencionado, actualizar sus contadores
                    if servicio_mencionado:
                        if nombre_servicio not in mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios']:
                            mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio] = {
                                'total': 0,
                                'positivos': 0,
                                'negativos': 0,
                                'neutros': 0
                            }
                        
                        # Clasificar el sentimiento específico para el servicio
                        clasificacion_servicio = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
                        mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio]['total'] += 1
                        mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio][clasificacion_servicio + 's'] += 1
            
            # Si la empresa fue mencionada (directamente o a través de servicios), actualizar sus contadores
            if empresa_mencionada:
                # Clasificar el sentimiento específico para la empresa
                clasificacion_empresa = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
                mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['total'] += 1
                mensajes_por_fecha[fecha]['empresas'][nombre_empresa][clasificacion_empresa + 's'] += 1
    
    return mensajes_por_fecha

def crear_xml_respuesta(mensajes_por_fecha):
    root = ET.Element('lista_respuestas')
    
    for fecha, datos in mensajes_por_fecha.items():
        # Crear elemento respuesta
        respuesta = ET.SubElement(root, 'respuesta')
        
        # Agregar fecha
        fecha_elem = ET.SubElement(respuesta, 'fecha')
        fecha_elem.text = f" {fecha} "
        
        # Agregar resumen de mensajes con indentación
        mensajes = ET.SubElement(respuesta, 'mensajes')
        ET.SubElement(mensajes, 'total').text = f" {datos['total']} "
        ET.SubElement(mensajes, 'positivos').text = f" {datos['positivos']} "
        ET.SubElement(mensajes, 'negativos').text = f" {datos['negativos']} "
        ET.SubElement(mensajes, 'neutros').text = f" {datos['neutros']} "
        
        # Agregar análisis
        analisis = ET.SubElement(respuesta, 'analisis')
        
        # Filtrar y ordenar empresas que tienen menciones
        empresas_con_menciones = {
            nombre: datos_empresa 
            for nombre, datos_empresa in datos['empresas'].items() 
            if datos_empresa['total'] > 0
        }
        
        # Iterar sobre empresas que tienen menciones
        for nombre_empresa, datos_empresa in empresas_con_menciones.items():
            # Capitalizar el nombre de la empresa
            nombre_empresa_cap = nombre_empresa.capitalize()
            empresa = ET.SubElement(analisis, 'empresa', nombre=nombre_empresa_cap)
            
            # Agregar mensajes de la empresa
            mensajes_empresa = ET.SubElement(empresa, 'mensajes')
            ET.SubElement(mensajes_empresa, 'total').text = f" {datos_empresa['total']} "
            ET.SubElement(mensajes_empresa, 'positivos').text = f" {datos_empresa['positivos']} "
            ET.SubElement(mensajes_empresa, 'negativos').text = f" {datos_empresa['negativos']} "
            ET.SubElement(mensajes_empresa, 'neutros').text = f" {datos_empresa['neutros']} "
            
            # Agregar servicios si existen
            servicios = ET.SubElement(empresa, 'servicios')
            for nombre_servicio, datos_servicio in datos_empresa['servicios'].items():
                # Mantener el formato original del nombre del servicio
                servicio = ET.SubElement(servicios, 'servicio', nombre=nombre_servicio.title())
                
                # Agregar mensajes del servicio
                mensajes_servicio = ET.SubElement(servicio, 'mensajes')
                ET.SubElement(mensajes_servicio, 'total').text = f" {datos_servicio['total']} "
                ET.SubElement(mensajes_servicio, 'positivos').text = f" {datos_servicio['positivos']} "
                ET.SubElement(mensajes_servicio, 'negativos').text = f" {datos_servicio['negativos']} "
                ET.SubElement(mensajes_servicio, 'neutros').text = f" {datos_servicio['neutros']} "
    
    return root

def format_xml_pretty(elem):
    """
    Función personalizada para formatear el XML con la indentación deseada
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    # Usar 4 espacios para la indentación y preservar los espacios en blanco
    formatted = reparsed.toprettyxml(indent='    ', newl='\n')
    
    # Eliminar líneas vacías extra pero mantener el espaciado dentro de los elementos
    lines = [line for line in formatted.split('\n') if line.strip()]
    return '\n'.join(lines)

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
        
        # Formatear la respuesta con el formato específico
        output_xml = '<?xml version="1.0"?>\n' + format_xml_pretty(respuesta_xml)
        
        return output_xml, 200, {'Content-Type': 'application/xml'}
        
    except ET.ParseError:
        return jsonify({'error': 'Error al procesar el archivo XML'}), 400

if __name__ == '__main__':
    app.run(debug=True)