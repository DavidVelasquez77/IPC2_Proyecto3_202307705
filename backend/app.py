from flask_cors import CORS
from flask import Flask, request, jsonify
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import unicodedata
import re
import os
from io import StringIO

# Declaramos las variables globales para guardar el diccionario
sentimientos_positivos_global = []
sentimientos_negativos_global = []

app = Flask(__name__)
CORS(app) 
def normalizar(texto):
    if texto is None:
        return ""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('utf-8').lower()
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def extraer_fecha(mensaje):
    patron = r"Lugar y fecha:.*?,\s*(\d{2}/\d{2}/\d{4})"
    match = re.search(patron, mensaje)
    if match:
        return match.group(1)
    return None

def procesar_diccionario(root):
    global sentimientos_positivos_global, sentimientos_negativos_global
    sentimientos_positivos = []
    sentimientos_negativos = []
    
    diccionario = root.find('diccionario')
    if diccionario is not None:
        positivos = diccionario.find('sentimientos_positivos')
        if positivos is not None:
            for palabra in positivos.findall('palabra'):
                if palabra.text:
                    sentimientos_positivos.append(normalizar(palabra.text))
        
        negativos = diccionario.find('sentimientos_negativos')
        if negativos is not None:
            for palabra in negativos.findall('palabra'):
                if palabra.text:
                    sentimientos_negativos.append(normalizar(palabra.text))

    # Guardamos los sentimientos en las variables globales
    sentimientos_positivos_global = sentimientos_positivos
    sentimientos_negativos_global = sentimientos_negativos

    return sentimientos_positivos, sentimientos_negativos

def clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos):
    if mensaje.text is None:
        return "neutro"
    
    contenido = normalizar(mensaje.text)
    palabras = contenido.split()
    
    palabras_positivas = sum(1 for palabra in palabras if palabra in sentimientos_positivos)
    palabras_negativas = sum(1 for palabra in palabras if palabra in sentimientos_negativos)
    
    if palabras_positivas == 0 and palabras_negativas == 0:
        return "neutro"
    
    if palabras_positivas == palabras_negativas:
        return "neutro"
        
    if palabras_positivas > palabras_negativas:
        return "positivo"
    
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
        
        clasificacion_general = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
        mensajes_por_fecha[fecha]['total'] += 1
        mensajes_por_fecha[fecha][clasificacion_general + 's'] += 1
        
        for empresa_data in empresas_data:
            nombre_empresa = normalizar(empresa_data.find('nombre').text)
            empresa_mencionada = False
            
            if nombre_empresa in contenido_normalizado:
                empresa_mencionada = True
            
            servicios = empresa_data.find('servicios')
            if servicios is not None:
                for servicio in servicios.findall('servicio'):
                    nombre_servicio = normalizar(servicio.get('nombre'))
                    servicio_mencionado = False
                    
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
                        
                        clasificacion_servicio = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
                        mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio]['total'] += 1
                        mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['servicios'][nombre_servicio][clasificacion_servicio + 's'] += 1
            
            if empresa_mencionada:
                clasificacion_empresa = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
                mensajes_por_fecha[fecha]['empresas'][nombre_empresa]['total'] += 1
                mensajes_por_fecha[fecha]['empresas'][nombre_empresa][clasificacion_empresa + 's'] += 1
    
    return mensajes_por_fecha

def crear_xml_respuesta(mensajes_por_fecha):
    root = ET.Element('lista_respuestas')
    
    for fecha, datos in mensajes_por_fecha.items():
        respuesta = ET.SubElement(root, 'respuesta')
        
        fecha_elem = ET.SubElement(respuesta, 'fecha')
        fecha_elem.text = f" {fecha} "
        
        mensajes = ET.SubElement(respuesta, 'mensajes')
        ET.SubElement(mensajes, 'total').text = f" {datos['total']} "
        ET.SubElement(mensajes, 'positivos').text = f" {datos['positivos']} "
        ET.SubElement(mensajes, 'negativos').text = f" {datos['negativos']} "
        ET.SubElement(mensajes, 'neutros').text = f" {datos['neutros']} "
        
        analisis = ET.SubElement(respuesta, 'analisis')
        
        empresas_con_menciones = {
            nombre: datos_empresa 
            for nombre, datos_empresa in datos['empresas'].items() 
            if datos_empresa['total'] > 0
        }
        
        for nombre_empresa, datos_empresa in empresas_con_menciones.items():
            nombre_empresa_cap = nombre_empresa.capitalize()
            empresa = ET.SubElement(analisis, 'empresa', nombre=nombre_empresa_cap)
            
            mensajes_empresa = ET.SubElement(empresa, 'mensajes')
            ET.SubElement(mensajes_empresa, 'total').text = f" {datos_empresa['total']} "
            ET.SubElement(mensajes_empresa, 'positivos').text = f" {datos_empresa['positivos']} "
            ET.SubElement(mensajes_empresa, 'negativos').text = f" {datos_empresa['negativos']} "
            ET.SubElement(mensajes_empresa, 'neutros').text = f" {datos_empresa['neutros']} "
            
            servicios = ET.SubElement(empresa, 'servicios')
            for nombre_servicio, datos_servicio in datos_empresa['servicios'].items():
                servicio = ET.SubElement(servicios, 'servicio', nombre=nombre_servicio.title())
                
                mensajes_servicio = ET.SubElement(servicio, 'mensajes')
                ET.SubElement(mensajes_servicio, 'total').text = f" {datos_servicio['total']} "
                ET.SubElement(mensajes_servicio, 'positivos').text = f" {datos_servicio['positivos']} "
                ET.SubElement(mensajes_servicio, 'negativos').text = f" {datos_servicio['negativos']} "
                ET.SubElement(mensajes_servicio, 'neutros').text = f" {datos_servicio['neutros']} "
    
    return root

def format_xml_pretty(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    formatted = reparsed.toprettyxml(indent='    ', newl='\n')
    lines = [line for line in formatted.split('\n') if line.strip()]
    return '\n'.join(lines)

def parse_solicitudes(xml_content):
    """
    Parsea el contenido XML y maneja tanto una única solicitud como múltiples
    """
    try:
        # Primero intentamos parsear directamente (caso de una única solicitud)
        root = ET.fromstring(xml_content)
        if root.tag == 'solicitud_clasificacion':
            return [root]
        
        # Si no es una única solicitud, intentamos parsear múltiples
        # Envolvemos las solicitudes en un elemento raíz temporal
        wrapped_content = f'<root>{xml_content}</root>'
        root = ET.fromstring(wrapped_content)
        solicitudes = root.findall('solicitud_clasificacion')
        if solicitudes:
            return solicitudes
            
        raise ValueError("No se encontraron elementos solicitud_clasificacion válidos")
        
    except ET.ParseError as e:
        raise ValueError(f"Error al parsear el XML: {str(e)}")

# En el endpoint de clasificar, procesamos el archivo XML y almacenamos el diccionario globalmente
@app.route('/clasificar', methods=['POST'])
def clasificar_mensajes():
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400

    archivo = request.files['archivo']
    xml_content = archivo.read().decode('utf-8')
    
    try:
        solicitudes = parse_solicitudes(xml_content)
        if not solicitudes:
            return jsonify({'error': 'No se encontraron solicitudes válidas en el XML'}), 400
        
        respuesta_root = ET.Element('lista_respuestas')
        for solicitud in solicitudes:
            # Procesar el diccionario y guardar en variables globales
            procesar_diccionario(solicitud)

            mensajes = solicitud.find('lista_mensajes').findall('mensaje')
            empresas_data = solicitud.find('diccionario').find('empresas_analizar').findall('empresa')
            mensajes_por_fecha = agrupar_por_fecha(mensajes, empresas_data, sentimientos_positivos_global, sentimientos_negativos_global)
            respuesta_xml = crear_xml_respuesta(mensajes_por_fecha)
            for respuesta in respuesta_xml:
                respuesta_root.append(respuesta)

        output_xml = format_xml_pretty(respuesta_root)
        return output_xml, 200, {'Content-Type': 'application/xml'}
        
    except Exception as e:
        return jsonify({'error': f'Error al procesar el archivo XML: {str(e)}'}), 400


# Endpoint `procesar_mensaje_individual` modificado para usar el diccionario global
@app.route('/prueba_mensaje', methods=['POST'])
def procesar_mensaje_individual():
    try:
        datos = request.get_json()
        mensaje_xml = datos.get('mensaje', '')
        root = ET.fromstring(mensaje_xml)
        mensaje_texto = root.text.strip() if root.text else ''
        
        # Extraer información del mensaje
        fecha_match = re.search(r'Lugar y fecha:.*?,\s*(\d{2}/\d{2}/\d{4})', mensaje_texto)
        fecha = fecha_match.group(1) if fecha_match else ''
        
        usuario_match = re.search(r'Usuario:\s*([^\n]+)', mensaje_texto)
        usuario = usuario_match.group(1).strip() if usuario_match else ''
        
        red_social_match = re.search(r'Red social:\s*([^\n]+)', mensaje_texto)
        red_social = red_social_match.group(1).strip() if red_social_match else ''

        palabras = normalizar(mensaje_texto).split()
        palabras_positivas = sum(1 for palabra in palabras if palabra in sentimientos_positivos_global)
        palabras_negativas = sum(1 for palabra in palabras if palabra in sentimientos_negativos_global)
        
        total_palabras = palabras_positivas + palabras_negativas
        sentimiento_positivo = (palabras_positivas / total_palabras * 100) if total_palabras > 0 else 0
        sentimiento_negativo = (palabras_negativas / total_palabras * 100) if total_palabras > 0 else 0
        
        sentimiento = 'positivo' if palabras_positivas > palabras_negativas else 'negativo' if palabras_negativas > palabras_positivas else 'neutro'
        
        respuesta_xml = f'''<respuesta>
    <fecha> {fecha} </fecha>
    <red_social> {red_social} </red_social>
    <usuario> {usuario} </usuario>
    <palabras_positivas> {palabras_positivas} </palabras_positivas>
    <palabras_negativas> {palabras_negativas} </palabras_negativas>
    <sentimiento_positivo> {sentimiento_positivo:.2f}% </sentimiento_positivo>
    <sentimiento_negativo> {sentimiento_negativo:.2f}% </sentimiento_negativo>
    <sentimiento_analizado> {sentimiento} </sentimiento_analizado>
</respuesta>'''
        
        return jsonify({'respuesta_xml': respuesta_xml})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    


if __name__ == '__main__':
    app.run(debug=True)