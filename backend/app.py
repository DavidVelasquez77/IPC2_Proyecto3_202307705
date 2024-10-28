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

# Cargar el archivo de entrada.xml al iniciar la aplicación
ruta_entrada = r'C:\Users\Vela\Desktop\IPC2\Proyecto3\frontend\entrada\entrada.xml'
empresas_servicios = {}
sentimientos_positivos = []
sentimientos_negativos = []


app = Flask(__name__)
CORS(app) 

last_result = {}
def normalizar(texto):
    if texto is None:
        return ""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('utf-8').lower()
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

#EXPRESIONES REGULAR PARA LA FECHA 
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


def cargar_diccionario_y_empresas():
    try:
        tree = ET.parse(ruta_entrada)
        root = tree.getroot()

        # Parsear empresas y servicios
        for empresa in root.find('.//empresas_analizar'):
            nombre_empresa = empresa.find('nombre').text.strip().lower()
            servicios = []
            for servicio in empresa.find('servicios'):
                nombre_servicio = servicio.get('nombre').strip().lower()
                alias = [alias.text.strip().lower() for alias in servicio.findall('alias')]
                servicios.append({'nombre': nombre_servicio, 'alias': alias})
            empresas_servicios[nombre_empresa] = servicios

        # Parsear sentimientos positivos y negativos
        sentimientos_positivos.extend([palabra.text.strip().lower() for palabra in root.find('.//sentimientos_positivos')])
        sentimientos_negativos.extend([palabra.text.strip().lower() for palabra in root.find('.//sentimientos_negativos')])

    except Exception as e:
        print(f"Error al cargar el archivo XML: {e}")

# Llamar a la función al iniciar la aplicación
cargar_diccionario_y_empresas()

# Endpoint para procesar el mensaje individual
@app.route('/prueba_mensaje', methods=['POST'])
def procesar_mensaje_individual():
    try:
        datos = request.get_json()
        mensaje_xml = datos.get('mensaje', '')

        # Parsear el XML del mensaje recibido
        root = ET.fromstring(mensaje_xml)
        mensaje_texto = root.text.strip() if root.text else ''

        # Extraer la fecha, el usuario y la red social
        fecha_match = re.search(r'Lugar y fecha:.*?,\s*(\d{2}/\d{2}/\d{4})', mensaje_texto)
        fecha = fecha_match.group(1) if fecha_match else ''

        usuario_match = re.search(r'Usuario:\s*([^\n]+)', mensaje_texto)
        usuario = usuario_match.group(1).strip() if usuario_match else ''

        red_social_match = re.search(r'Red social:\s*([^\n]+)', mensaje_texto)
        red_social = red_social_match.group(1).strip() if red_social_match else ''

        # Normalización del mensaje para análisis
        mensaje_normalizado = mensaje_texto.lower()
        
        # Identificar empresas y servicios mencionados en el mensaje
        empresas_identificadas = []
        for nombre_empresa, servicios in empresas_servicios.items():
            if nombre_empresa in mensaje_normalizado:
                empresa_info = {'nombre': nombre_empresa, 'servicios': []}
                for servicio in servicios:
                    if any(alias in mensaje_normalizado for alias in servicio['alias']):
                        empresa_info['servicios'].append(servicio['nombre'])
                if empresa_info['servicios']:
                    empresas_identificadas.append(empresa_info)

        # Identificar y contar palabras de sentimientos
        palabras_positivas = sum(1 for palabra in sentimientos_positivos if palabra in mensaje_normalizado)
        palabras_negativas = sum(1 for palabra in sentimientos_negativos if palabra in mensaje_normalizado)
        total_palabras_sentimiento = palabras_positivas + palabras_negativas

        # Calcular porcentajes de sentimientos
        sentimiento_positivo_pct = (palabras_positivas / total_palabras_sentimiento * 100) if total_palabras_sentimiento > 0 else 0
        sentimiento_negativo_pct = (palabras_negativas / total_palabras_sentimiento * 100) if total_palabras_sentimiento > 0 else 0
        sentimiento_analizado = 'positivo' if sentimiento_positivo_pct > sentimiento_negativo_pct else 'negativo' if sentimiento_negativo_pct > 0 else 'neutral'

        # Construir la sección de empresas en XML
        empresas_xml = "<empresas>"
        for empresa in empresas_identificadas:
            servicios_xml = ''.join(f"<servicio>{servicio}</servicio>" for servicio in empresa['servicios'])
            empresas_xml += f"""
        <empresa nombre="{empresa['nombre']}">
            {servicios_xml}
        </empresa>"""
        empresas_xml += "</empresas>"

        # Construir respuesta XML
        respuesta_xml = f'''<respuesta>
    <fecha>{fecha}</fecha>
    <red_social>{red_social}</red_social>
    <usuario>{usuario}</usuario>
    {empresas_xml}
    <palabras_positivas>{palabras_positivas}</palabras_positivas>
    <palabras_negativas>{palabras_negativas}</palabras_negativas>
    <sentimiento_positivo>{sentimiento_positivo_pct:.2f}%</sentimiento_positivo>
    <sentimiento_negativo>{sentimiento_negativo_pct:.2f}%</sentimiento_negativo>
    <sentimiento_analizado>{sentimiento_analizado}</sentimiento_analizado>
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

        # Convertir fechas a objetos datetime
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%d/%m/%Y')
        fecha_fin_dt = datetime.strptime(fecha_fin, '%d/%m/%Y')

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
            fecha_text = respuesta.find("fecha").text.strip()
            fecha_respuesta = datetime.strptime(fecha_text, '%d/%m/%Y')
            
            if fecha_inicio_dt <= fecha_respuesta <= fecha_fin_dt:
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
                    if empresa_element is not None and empresa_element.find('mensajes') is not None:
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

    except ValueError as e:
        return jsonify({'error': f'Error en formato de fecha: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/mensajes_filtrados_rango', methods=['POST'])
def mensajes_filtrados_rango():
    try:
        fecha_inicio = request.json.get('fecha_inicio')
        fecha_fin = request.json.get('fecha_fin')
        empresa = request.json.get('empresa')

        # Convertir fechas a objetos datetime
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%d/%m/%Y')
        fecha_fin_dt = datetime.strptime(fecha_fin, '%d/%m/%Y')

        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'
        tree = ET.parse(xml_path)
        root = tree.getroot()

        mensajes_resumen = []

        for respuesta in root.findall(".//respuesta"):
            fecha_text = respuesta.find("fecha").text.strip()
            fecha_respuesta = datetime.strptime(fecha_text, '%d/%m/%Y')
            
            if fecha_inicio_dt <= fecha_respuesta <= fecha_fin_dt:
                empresas = respuesta.findall(".//empresa") if empresa == 'todas' else respuesta.findall(f".//empresa[@nombre='{empresa}']")
                
                for empresa_element in empresas:
                    nombre_empresa = empresa_element.get('nombre')
                    for servicio in empresa_element.findall(".//servicio"):
                        nombre_servicio = servicio.get('nombre')
                        mensajes = servicio.find('mensajes')

                        mensaje_info = {
                            'fecha': fecha_text,
                            'empresa': nombre_empresa,
                            'servicio': nombre_servicio,
                            'total': int(mensajes.find('total').text),
                            'positivos': int(mensajes.find('positivos').text),
                            'negativos': int(mensajes.find('negativos').text),
                            'neutros': int(mensajes.find('neutros').text)
                        }
                        mensajes_resumen.append(mensaje_info)

        return jsonify({'mensajes': mensajes_resumen}), 200

    except ValueError as e:
        return jsonify({'error': f'Error en formato de fecha: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
@app.route('/reset', methods=['POST'])
def reset():
    try:
        # Ruta del archivo XML
        xml_path = 'C:\\Users\\Vela\\Desktop\\IPC2\\Proyecto3\\frontend\\output_xml\\salida.xml'
        
        # Verificar si el archivo existe
        if not os.path.exists(xml_path):
            return jsonify({'error': 'Archivo XML no encontrado'}), 404

        # Crear la estructura XML vacía con el nodo raíz `<lista_respuestas>`
        root = ET.Element("lista_respuestas")
        tree = ET.ElementTree(root)
        
        # Escribir la estructura vacía en el archivo XML
        with open(xml_path, "wb") as file:
            tree.write(file, encoding='utf-8', xml_declaration=True)
        
        return jsonify({'message': 'Base de datos reseteada correctamente'}), 200

    except Exception as e:
        print(f"Error al resetear la base de datos: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# Endpoint para recibir y actualizar el valor de last_result desde el frontend
@app.route('/update-last-result', methods=['POST'])
def update_last_result():
    global last_result
    data = request.get_json()  # Obtener los datos enviados desde el frontend (como JSON)
    
    if 'last_result' in data:
        last_result = data['last_result']  # Actualizamos el valor de last_result en el backend
        return jsonify({"message": "last_result actualizado correctamente"}), 200
    else:
        return jsonify({"error": "last_result no enviado en el payload"}), 400

# Endpoint para consultar el valor de last_result (el que hicimos antes)
@app.route('/last-result', methods=['GET'])
def get_last_result():
    return jsonify(last_result)

if __name__ == '__main__':
    app.run(debug=True)