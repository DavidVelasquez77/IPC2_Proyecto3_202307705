from flask import Flask, request, jsonify
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import unicodedata
import os

app = Flask(__name__)

# Función para normalizar y quitar tildes
def normalizar(texto):
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8').lower()

# Función para validar la estructura del XML
def validar_xml(root):
    # Verificar que la estructura básica está presente
    if root.tag != 'solicitud_clasificacion':
        return False
    return True

# Función para procesar el diccionario de sentimientos
def procesar_diccionario(root):
    sentimientos_positivos = []
    sentimientos_negativos = []

    # Obtener sentimientos positivos
    for palabra in root.find('diccionario').find('sentimientos_positivos').findall('palabra'):
        sentimientos_positivos.append(normalizar(palabra.text.strip()))

    # Obtener sentimientos negativos
    for palabra in root.find('diccionario').find('sentimientos_negativos').findall('palabra'):
        sentimientos_negativos.append(normalizar(palabra.text.strip()))

    return sentimientos_positivos, sentimientos_negativos

# Función para clasificar un mensaje
def clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos):
    palabras_positivas = 0
    palabras_negativas = 0
    contenido = normalizar(mensaje.text.strip())

    # Separar el contenido en palabras
    palabras = contenido.split()

    # Contar cuántas palabras son positivas o negativas
    for palabra in palabras:
        if palabra in sentimientos_positivos:
            palabras_positivas += 1
        elif palabra in sentimientos_negativos:
            palabras_negativas += 1

    # Clasificar el mensaje según la cantidad de palabras positivas o negativas
    if palabras_positivas > palabras_negativas:
        return "positivo"
    elif palabras_negativas > palabras_positivas:
        return "negativo"
    else:
        return "neutro"

# Función para clasificar mensajes por empresa y servicio
def clasificar_por_empresa_y_servicio(root, sentimientos_positivos, sentimientos_negativos):
    analisis_empresas = {}
    total_mensajes = 0
    total_positivos = 0
    total_negativos = 0
    total_neutros = 0

    # Obtener las empresas a analizar
    for empresa in root.find('diccionario').find('empresas_analizar').findall('empresa'):
        nombre_empresa = normalizar(empresa.find('nombre').text.strip())
        analisis_empresas[nombre_empresa] = {
            'total': 0,
            'positivos': 0,
            'negativos': 0,
            'neutros': 0,
            'servicios': {}
        }

        # Obtener los servicios de cada empresa
        for servicio in empresa.find('servicios').findall('servicio'):
            nombre_servicio = normalizar(servicio.attrib['nombre'])
            analisis_empresas[nombre_empresa]['servicios'][nombre_servicio] = {
                'total': 0,
                'positivos': 0,
                'negativos': 0,
                'neutros': 0
            }

    # Procesar los mensajes
    for mensaje in root.find('lista_mensajes').findall('mensaje'):
        total_mensajes += 1
        clasificacion = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)

        if clasificacion == 'positivo':
            total_positivos += 1
        elif clasificacion == 'negativo':
            total_negativos += 1
        else:
            total_neutros += 1

        # Buscar a qué empresa y servicio corresponde el mensaje
        for empresa in root.find('diccionario').find('empresas_analizar').findall('empresa'):
            nombre_empresa = normalizar(empresa.find('nombre').text.strip())

            for servicio in empresa.find('servicios').findall('servicio'):
                for alias in servicio.findall('alias'):
                    if normalizar(alias.text.strip()) in normalizar(mensaje.text):
                        # Contabilizar el mensaje para el servicio y la empresa correspondiente
                        analisis_empresas[nombre_empresa]['total'] += 1
                        analisis_empresas[nombre_empresa]['servicios'][normalizar(servicio.attrib['nombre'])]['total'] += 1

                        if clasificacion == 'positivo':
                            analisis_empresas[nombre_empresa]['positivos'] += 1
                            analisis_empresas[nombre_empresa]['servicios'][normalizar(servicio.attrib['nombre'])]['positivos'] += 1
                        elif clasificacion == 'negativo':
                            analisis_empresas[nombre_empresa]['negativos'] += 1
                            analisis_empresas[nombre_empresa]['servicios'][normalizar(servicio.attrib['nombre'])]['negativos'] += 1
                        else:
                            analisis_empresas[nombre_empresa]['neutros'] += 1
                            analisis_empresas[nombre_empresa]['servicios'][normalizar(servicio.attrib['nombre'])]['neutros'] += 1

    return analisis_empresas, total_mensajes, total_positivos, total_negativos, total_neutros

# Función para usar minidom y darle formato bonito al XML
def format_xml_pretty(elem):
    """ Convierte un elemento XML en una cadena bien formateada usando minidom """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

# Función para guardar datos en un archivo XML
def guardar_datos_en_xml(data, filename='datos.xml'):
    root = ET.Element('lista_mensajes')
    for mensaje in data:
        mensaje_element = ET.SubElement(root, 'mensaje')
        mensaje_element.text = mensaje  # Asegúrate de que `mensaje` sea un string apropiado

    # Guardar el árbol XML en un archivo
    tree = ET.ElementTree(root)
    with open(filename, 'wb') as xml_file:
        tree.write(xml_file)

# Ruta para procesar los mensajes XML
@app.route('/clasificar', methods=['POST'])
def clasificar_mensajes():
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400

    archivo = request.files['archivo']

    try:
        # Parsear el XML
        tree = ET.parse(archivo)
        root = tree.getroot()

        # Validar la estructura del XML
        if not validar_xml(root):
            return jsonify({'error': 'Estructura del XML no válida'}), 400

        # Procesar el diccionario de sentimientos
        sentimientos_positivos, sentimientos_negativos = procesar_diccionario(root)

        # Clasificar mensajes por empresa y servicio
        analisis_empresas, total_mensajes, total_positivos, total_negativos, total_neutros = clasificar_por_empresa_y_servicio(
            root, sentimientos_positivos, sentimientos_negativos)

        # Crear un XML de salida con los resultados
        lista_respuestas = ET.Element('lista_respuestas')
        respuesta = ET.SubElement(lista_respuestas, 'respuesta')

        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        ET.SubElement(respuesta, 'fecha').text = fecha_actual

        # Crear el bloque de mensajes totales
        mensajes_element = ET.SubElement(respuesta, 'mensajes')
        ET.SubElement(mensajes_element, 'total').text = str(total_mensajes)
        ET.SubElement(mensajes_element, 'positivos').text = str(total_positivos)
        ET.SubElement(mensajes_element, 'negativos').text = str(total_negativos)
        ET.SubElement(mensajes_element, 'neutros').text = str(total_neutros)

        # Crear el análisis de empresas y servicios
        analisis_element = ET.SubElement(respuesta, 'analisis')
        for nombre_empresa, datos_empresa in analisis_empresas.items():
            empresa_element = ET.SubElement(analisis_element, 'empresa', nombre=nombre_empresa)

            # Crear el bloque de mensajes para la empresa
            mensajes_empresa = ET.SubElement(empresa_element, 'mensajes')
            ET.SubElement(mensajes_empresa, 'total').text = str(datos_empresa['total'])
            ET.SubElement(mensajes_empresa, 'positivos').text = str(datos_empresa['positivos'])
            ET.SubElement(mensajes_empresa, 'negativos').text = str(datos_empresa['negativos'])
            ET.SubElement(mensajes_empresa, 'neutros').text = str(datos_empresa['neutros'])

            # Crear el bloque de servicios para la empresa
            servicios_element = ET.SubElement(empresa_element, 'servicios')
            for nombre_servicio, datos_servicio in datos_empresa['servicios'].items():
                servicio_element = ET.SubElement(servicios_element, 'servicio', nombre=nombre_servicio)

                # Crear el bloque de mensajes para cada servicio
                mensajes_servicio = ET.SubElement(servicio_element, 'mensajes')
                ET.SubElement(mensajes_servicio, 'total').text = str(datos_servicio['total'])
                ET.SubElement(mensajes_servicio, 'positivos').text = str(datos_servicio['positivos'])
                ET.SubElement(mensajes_servicio, 'negativos').text = str(datos_servicio['negativos'])
                ET.SubElement(mensajes_servicio, 'neutros').text = str(datos_servicio['neutros'])

        # Formatear el XML de salida y devolverlo
        output_xml = format_xml_pretty(lista_respuestas)

        # Guardar los datos en un archivo XML
        guardar_datos_en_xml([mensaje.text for mensaje in root.find('lista_mensajes').findall('mensaje')], filename='datos.xml')

        return output_xml, 200, {'Content-Type': 'application/xml'}

    except ET.ParseError:
        return jsonify({'error': 'Error al procesar el archivo XML'}), 400

if __name__ == '__main__':
    app.run(debug=True)
