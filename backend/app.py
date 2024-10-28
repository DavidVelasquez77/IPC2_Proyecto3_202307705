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
    
@app.route('/resumen_fecha', methods=['POST'])
def resumen_fecha():
    try:
        # Obtener los parámetros de la solicitud
        fecha = request.json.get('fecha')
        empresa = request.json.get('empresa')
        
        print(f"Fecha recibida: {fecha}")
        print(f"Empresa recibida: {empresa}")
        
        # Ruta del archivo XML
        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'
        
        # Verificar si el archivo existe
        if not os.path.exists(xml_path):
            print(f"Error: El archivo XML no existe en la ruta: {xml_path}")
            return jsonify({'error': 'Archivo XML no encontrado'}), 404
        
        # Leer y parsear el archivo XML
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Buscar la respuesta para la fecha específica
        respuesta = root.find(f".//respuesta[fecha='{fecha}']")
        
        if respuesta is None:
            return jsonify({
                'total_mensajes': 0,
                'total_positivos': 0,
                'total_negativos': 0,
                'total_neutros': 0
            }), 200
        
        if empresa == 'todas':
            # Inicializar contadores para todas las empresas
            total_mensajes = 0
            total_positivos = 0
            total_negativos = 0
            total_neutros = 0
            
            # Sumar los totales de todas las empresas
            for empresa_element in respuesta.findall(".//empresa"):
                mensajes = empresa_element.find('mensajes')
                if mensajes is not None:
                    total_mensajes += int(mensajes.find('total').text)
                    total_positivos += int(mensajes.find('positivos').text)
                    total_negativos += int(mensajes.find('negativos').text)
                    total_neutros += int(mensajes.find('neutros').text)
            
            return jsonify({
                'total_mensajes': total_mensajes,
                'total_positivos': total_positivos,
                'total_negativos': total_negativos,
                'total_neutros': total_neutros
            }), 200
        else:
            # Buscar la empresa específica
            empresa_element = respuesta.find(f".//empresa[@nombre='{empresa}']")
            if empresa_element is not None:
                mensajes = empresa_element.find('mensajes')
                return jsonify({
                    'total_mensajes': int(mensajes.find('total').text),
                    'total_positivos': int(mensajes.find('positivos').text),
                    'total_negativos': int(mensajes.find('negativos').text),
                    'total_neutros': int(mensajes.find('neutros').text)
                }), 200
            else:
                return jsonify({
                    'total_mensajes': 0,
                    'total_positivos': 0,
                    'total_negativos': 0,
                    'total_neutros': 0
                }), 200
                
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/empresas', methods=['GET'])
def get_empresas():
    try:
        # Ruta del archivo XML
        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'

        # Leer y parsear el archivo XML
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Obtener todas las empresas únicas
        empresas = set()
        for empresa in root.findall(".//empresa"):
            nombre = empresa.get('nombre')
            if nombre:
                empresas.add(nombre)

        return jsonify({'empresas': list(empresas)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fechas', methods=['GET'])
def get_fechas():
    try:
        # Ruta del archivo XML
        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'

        # Leer y parsear el archivo XML
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Obtener todas las fechas
        fechas = []
        for fecha in root.findall(".//fecha"):
            if fecha.text:
                fechas.append(fecha.text)

        return jsonify({'fechas': fechas}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/mensajes_filtrados', methods=['POST'])
def mensajes_filtrados():
    try:
        # Obtener los parámetros de la solicitud
        fecha = request.json.get('fecha')
        empresa = request.json.get('empresa')
        
        # Ruta del archivo XML
        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'
        
        # Leer y parsear el archivo XML
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Buscar la respuesta para la fecha específica
        respuesta = root.find(f".//respuesta[fecha='{fecha}']")
        
        if respuesta is None:
            return jsonify({'mensajes': []}), 200
            
        mensajes_resumen = []
        
        if empresa == 'todas':
            # Obtener todas las empresas para esa fecha
            empresas = respuesta.findall(".//empresa")
        else:
            # Obtener solo la empresa específica
            empresas = respuesta.findall(f".//empresa[@nombre='{empresa}']")
            
        for empresa_element in empresas:
            nombre_empresa = empresa_element.get('nombre')
            servicios = empresa_element.findall(".//servicio")
            
            for servicio in servicios:
                nombre_servicio = servicio.get('nombre')
                mensajes = servicio.find('mensajes')
                
                # Crear un resumen por cada servicio
                mensaje_info = {
                    'empresa': nombre_empresa,
                    'servicio': nombre_servicio,
                    'total': int(mensajes.find('total').text),
                    'positivos': int(mensajes.find('positivos').text),
                    'negativos': int(mensajes.find('negativos').text),
                    'neutros': int(mensajes.find('neutros').text)
                }
                mensajes_resumen.append(mensaje_info)
        
        return jsonify({'mensajes': mensajes_resumen}), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/resumen_rango_fecha', methods=['POST'])
def resumen_rango_fecha():
    try:
        # Obtener los parámetros de la solicitud
        fecha_inicio = request.json.get('fecha_inicio')
        fecha_fin = request.json.get('fecha_fin')
        empresa = request.json.get('empresa')

        # Ruta del archivo XML
        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'

        if not os.path.exists(xml_path):
            return jsonify({'error': 'Archivo XML no encontrado'}), 404

        # Leer y parsear el archivo XML
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Inicializar contadores
        total_mensajes = total_positivos = total_negativos = total_neutros = 0

        # Iterar por cada fecha dentro del rango
        for respuesta in root.findall(".//respuesta"):
            fecha_text = respuesta.find("fecha").text
            if fecha_text >= fecha_inicio and fecha_text <= fecha_fin:
                if empresa == 'todas':
                    for empresa_element in respuesta.findall(".//empresa"):
                        mensajes = empresa_element.find('mensajes')
                        if mensajes is not None:
                            total_mensajes += int(mensajes.find('total').text)
                            total_positivos += int(mensajes.find('positivos').text)
                            total_negativos += int(mensajes.find('negativos').text)
                            total_neutros += int(mensajes.find('neutros').text)
                else:
                    empresa_element = respuesta.find(f".//empresa[@nombre='{empresa}']")
                    if empresa_element:
                        mensajes = empresa_element.find('mensajes')
                        total_mensajes += int(mensajes.find('total').text)
                        total_positivos += int(mensajes.find('positivos').text)
                        total_negativos += int(mensajes.find('negativos').text)
                        total_neutros += int(mensajes.find('neutros').text)

        return jsonify({
            'total_mensajes': total_mensajes,
            'total_positivos': total_positivos,
            'total_negativos': total_negativos,
            'total_neutros': total_neutros
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta adicional para obtener los mensajes filtrados por rango de fechas
@app.route('/mensajes_filtrados_rango', methods=['POST'])
def mensajes_filtrados_rango():
    try:
        fecha_inicio = request.json.get('fecha_inicio')
        fecha_fin = request.json.get('fecha_fin')
        empresa = request.json.get('empresa')

        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'
        tree = ET.parse(xml_path)
        root = tree.getroot()

        mensajes_resumen = []

        for respuesta in root.findall(".//respuesta"):
            fecha_text = respuesta.find("fecha").text
            if fecha_text >= fecha_inicio and fecha_text <= fecha_fin:
                empresas = respuesta.findall(".//empresa") if empresa == 'todas' else respuesta.findall(f".//empresa[@nombre='{empresa}']")
                
                for empresa_element in empresas:
                    nombre_empresa = empresa_element.get('nombre')
                    for servicio in empresa_element.findall(".//servicio"):
                        nombre_servicio = servicio.get('nombre')
                        mensajes = servicio.find('mensajes')

                        mensaje_info = {
                            'empresa': nombre_empresa,
                            'servicio': nombre_servicio,
                            'total': int(mensajes.find('total').text),
                            'positivos': int(mensajes.find('positivos').text),
                            'negativos': int(mensajes.find('negativos').text),
                            'neutros': int(mensajes.find('neutros').text)
                        }
                        mensajes_resumen.append(mensaje_info)

        return jsonify({'mensajes': mensajes_resumen}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True)