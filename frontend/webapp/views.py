from django.shortcuts import render
import requests
from django.http import HttpResponse
import xml.etree.ElementTree as ET
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import json
import os
from django.conf import settings
from xml.dom import minidom

# Variable global para almacenar los resultados de la última respuesta
last_result = None

def save_xml_file(xml_content, filename):
    """
    Guarda el contenido XML en un archivo con formato correcto y limpio.
    """
    try:
        # Crear directorio de salida si no existe
        output_dir = os.path.join(settings.BASE_DIR, 'output_xml')
        os.makedirs(output_dir, exist_ok=True)
        
        # Parsear el XML
        xml_parsed = minidom.parseString(xml_content)
        
        # Personalizar el formato XML
        pretty_xml = '<?xml version="1.0" ?>\n'
        
        # Obtener el nodo raíz y sus hijos
        root = xml_parsed.documentElement
        
        # Función recursiva para formatear nodos
        def format_node(node, level=0):
            result = ''
            indent = '  ' * level
            
            # Manejar nodos de elemento
            if node.nodeType == node.ELEMENT_NODE:
                # Abrir etiqueta con atributos
                result += f'{indent}<{node.tagName}'
                if node.attributes:
                    for attr in node.attributes.items():
                        result += f' {attr[0]}="{attr[1]}"'
                
                # Verificar si tiene contenido o hijos
                if not node.childNodes or (len(node.childNodes) == 1 and node.firstChild.nodeType == node.TEXT_NODE):
                    text_content = node.firstChild.data.strip() if node.firstChild else ''
                    if text_content:
                        result += f'>{text_content}</{node.tagName}>\n'
                    else:
                        result += '/>\n'
                else:
                    result += '>\n'
                    # Procesar nodos hijos
                    for child in node.childNodes:
                        if child.nodeType != child.TEXT_NODE or child.data.strip():
                            result += format_node(child, level + 1)
                    result += f'{indent}</{node.tagName}>\n'
            
            return result
        
        # Formatear el documento completo
        pretty_xml += format_node(root)
        
        # Guardar el archivo
        file_path = os.path.join(output_dir, filename )
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)
        
        return file_path
    except Exception as e:
        print(f"Error al guardar el archivo XML: {str(e)}")
        return None

def clasificar(request):
    global last_result
    entrada = ''
    resultados = ''

    if request.method == 'POST' and request.FILES.get('archivo'):
        # Obtener el archivo XML desde el formulario
        archivo = request.FILES['archivo']
        
        # Leer el contenido del archivo para mostrarlo en la caja de entrada
        entrada = archivo.read().decode('utf-8')

        # Resetear el puntero del archivo para poder reenviarlo a la API
        archivo.seek(0)

        # Enviar el archivo a la API de Flask
        files = {'archivo': archivo}
        response = requests.post('http://127.0.0.1:5000/clasificar', files=files)

        # Verificar si la API devuelve un resultado válido
        if response.status_code == 200:
            # Mostrar el resultado de la API
            resultados = response.text
            last_result = resultados  # Guardar el resultado de la última clasificación
            
            # Generar nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'clasificacion_{timestamp}.xml'
            
            # Guardar el archivo XML
            saved_path = save_xml_file(resultados, filename)
            if saved_path:
                resultados += f"\n\nArchivo XML guardado en: {saved_path}"
            else:
                resultados += "\n\nError al guardar el archivo XML"
        else:
            return HttpResponse(f"Error al clasificar los mensajes: {response.text}", status=response.status_code)

    return render(request, 'index.html', {'resultados': resultados, 'entrada': entrada})



# Vista para consultar datos almacenados en la última respuesta
def consultar_datos(request):
    global last_result
    print("Contenido de last_result:")
    print(repr(last_result[:500]))  # Usar repr para ver caracteres especiales
    return render(request, 'peticiones.html', {'resultados': last_result})


# Nueva vista para el resumen de clasificación por fecha
def resumen_por_fecha(request):
    fecha = ''
    empresa = ''
    resultados = {
        'total_mensajes': 0,
        'total_positivos': 0,
        'total_negativos': 0,
        'total_neutros': 0,
        'empresas_disponibles': []
    }

    if request.method == 'POST':
        fecha = request.POST.get('fecha')
        empresa = request.POST.get('empresa', '')

        if last_result:
            try:
                # Limpiamos el XML antes de parsearlo
                xml_content = last_result.strip()
                # Si el XML comienza con BOM o espacios, los removemos
                if xml_content.startswith('<?xml'):
                    root = ET.fromstring(xml_content)
                else:
                    # Buscamos el inicio real del XML
                    xml_start = xml_content.find('<?xml')
                    if xml_start != -1:
                        xml_content = xml_content[xml_start:]
                    root = ET.fromstring(xml_content)

                # Debugging
                print("Fecha recibida:", fecha)
                print("Empresa recibida:", empresa)

                # Obtener lista de empresas disponibles
                empresas_element = root.find('.//empresas_analizar')
                if empresas_element is not None:
                    resultados['empresas_disponibles'] = [
                        emp.find('nombre').text.strip() 
                        for emp in empresas_element.findall('empresa')
                        if emp.find('nombre') is not None
                    ]
                    print("Empresas disponibles:", resultados['empresas_disponibles'])

                # Procesar mensajes
                mensajes_element = root.find('.//lista_mensajes')
                if mensajes_element is not None:
                    for mensaje in mensajes_element.findall('mensaje'):
                        try:
                            # Extraer y parsear la fecha del mensaje
                            texto_mensaje = mensaje.text if mensaje.text else ""
                            if 'Lugar y fecha: ' in texto_mensaje:
                                lugar_y_fecha = texto_mensaje.split('Lugar y fecha: ')[1].split('Usuario:')[0].strip()
                                mensaje_fecha = datetime.strptime(lugar_y_fecha.split(', ')[1], '%d/%m/%Y %H:%M')
                                mensaje_fecha_str = mensaje_fecha.strftime('%Y-%m-%d')
                                
                                print(f"Comparando fechas - Mensaje: {mensaje_fecha_str}, Filtro: {fecha}")

                                # Verificar si el mensaje corresponde a la empresa seleccionada
                                es_empresa_correcta = True
                                if empresa:
                                    es_empresa_correcta = empresa.lower() in texto_mensaje.lower()
                                    print(f"Verificando empresa - Buscando: {empresa}, Encontrada: {es_empresa_correcta}")

                                # Si la fecha coincide y es la empresa correcta (o no se seleccionó empresa)
                                if mensaje_fecha_str == fecha and es_empresa_correcta:
                                    resultados['total_mensajes'] += 1
                                    
                                    # Obtener el sentimiento
                                    sentimiento = mensaje.get('sentimiento', 'neutro').lower()
                                    if sentimiento == 'positivo':
                                        resultados['total_positivos'] += 1
                                    elif sentimiento == 'negativo':
                                        resultados['total_negativos'] += 1
                                    else:
                                        resultados['total_neutros'] += 1
                                    
                                    print(f"Mensaje contabilizado - Sentimiento: {sentimiento}")

                        except (ValueError, IndexError) as e:
                            print(f"Error procesando mensaje individual: {e}")
                            continue

            except ET.ParseError as e:
                print(f"Error al parsear XML: {e}")
                print("Contenido XML problemático:", last_result[:200])  # Primeros 200 caracteres para debug

    # Imprimir resultados finales para debugging
    print("Resultados finales:", resultados)

    return render(request, 'peticiones.html', {
        'fecha': fecha,
        'empresa': empresa,
        'total_mensajes': resultados['total_mensajes'],
        'total_positivos': resultados['total_positivos'],
        'total_negativos': resultados['total_negativos'],
        'total_neutros': resultados['total_neutros'],
        'empresas_disponibles': resultados['empresas_disponibles']
    })
    
# Nueva vista para el resumen por rango de fechas
def resumen_por_rango(request):
    start_date = ''
    end_date = ''
    empresa = ''
    total_mensajes = 0
    total_positivos = 0
    total_negativos = 0
    total_neutros = 0

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        empresa = request.POST.get('empresa')

        # Lógica para filtrar resultados de la última respuesta
        if last_result:
            root = ET.fromstring(last_result)
            for mensaje in root.find('lista_mensajes').findall('mensaje'):
                # Extraer la fecha del mensaje
                lugar_y_fecha = mensaje.text.split('Lugar y fecha: ')[1].split('Usuario:')[0].strip()
                mensaje_fecha = datetime.strptime(lugar_y_fecha.split(', ')[1], '%d/%m/%Y %H:%M')

                # Verificar si la fecha está dentro del rango
                if start_date and end_date and start_date <= mensaje_fecha.date().strftime('%d/%m/%Y') <= end_date:
                    # Aquí puedes implementar la lógica para verificar la empresa
                    # Por simplicidad, supongamos que todos los mensajes son relevantes
                    total_mensajes += 1
                    clasificacion = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)

                    if clasificacion == 'positivo':
                        total_positivos += 1
                    elif clasificacion == 'negativo':
                        total_negativos += 1
                    else:
                        total_neutros += 1

    return render(request, 'peticiones.html', {
        'total_mensajes': total_mensajes,
        'total_positivos': total_positivos,
        'total_negativos': total_negativos,
        'total_neutros': total_neutros,
        'start_date': start_date,
        'end_date': end_date,
        'empresa': empresa,
    })

# Nueva vista para generar el reporte en PDF
def generar_reporte_pdf(request):
    global last_result
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_mensajes.pdf"'

    # Crear un objeto canvas para el PDF
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    if last_result:
        root = ET.fromstring(last_result)
        # Inicia la posición del texto
        y = height - 50

        # Títulos del reporte
        p.drawString(100, y, "Reporte de Clasificación de Mensajes")
        y -= 20
        p.drawString(100, y, "Datos de Mensajes Totales:")
        y -= 20

        # Inicializar contadores
        total_mensajes = 0
        total_positivos = 0
        total_negativos = 0
        total_neutros = 0

        # Recorrer los mensajes para sumar las estadísticas
        for mensaje in root.find('lista_mensajes').findall('mensaje'):
            clasificacion = clasificar_mensaje(mensaje, sentimientos_positivos, sentimientos_negativos)
            total_mensajes += 1
            
            if clasificacion == 'positivo':
                total_positivos += 1
            elif clasificacion == 'negativo':
                total_negativos += 1
            else:
                total_neutros += 1
        
        # Añadir la información al PDF
        p.drawString(100, y, f"Total Mensajes: {total_mensajes}")
        y -= 20
        p.drawString(100, y, f"Total Positivos: {total_positivos}")
        y -= 20
        p.drawString(100, y, f"Total Negativos: {total_negativos}")
        y -= 20
        p.drawString(100, y, f"Total Neutros: {total_neutros}")
        
        # Añadir información detallada por empresa y servicio
        p.drawString(100, y, "Detalle por Empresa y Servicio:")
        y -= 20

        for empresa in root.find('diccionario').find('empresas_analizar').findall('empresa'):
            nombre_empresa = empresa.find('nombre').text.strip()
            p.drawString(100, y, f"Empresa: {nombre_empresa}")
            y -= 20
            
            for servicio in empresa.find('servicios').findall('servicio'):
                nombre_servicio = servicio.attrib['nombre']
                # Simular algún conteo aquí, podrías hacer algo más detallado
                p.drawString(120, y, f"Servicio: {nombre_servicio}")
                y -= 20

        # Finalizar el PDF
        p.showPage()
        p.save()
    else:
        p.drawString(100, height / 2, "No hay datos disponibles para generar el reporte.")
        p.showPage()
        p.save()

    return response

def prueba_mensaje(request):
    respuesta_xml = None  # Cambiado de '' a None para mejor control
    mensaje_enviado = False
    
    if request.method == 'POST':
        mensaje_xml = request.POST.get('archivo_xml', '')
        print("Mensaje XML enviado:", mensaje_xml)  # Debug
        
        try:
            # Enviar el mensaje XML al backend Flask
            response = requests.post(
                'http://localhost:5000/prueba_mensaje',
                json={'mensaje': mensaje_xml}
            )
            print("Respuesta del servidor:", response.text)  # Debug
            
            if response.status_code == 200:
                data = response.json()
                respuesta_xml = data.get('respuesta_xml')
                if respuesta_xml:
                    mensaje_enviado = True
                print("Respuesta XML procesada:", respuesta_xml)  # Debug
            else:
                print(f"Error del servidor: {response.status_code}")  # Debug
                
        except requests.exceptions.RequestException as e:
            print(f"Error de conexión: {str(e)}")  # Debug
            return HttpResponse(f"Error al conectar con el servidor: {str(e)}", status=500)
    
    context = {
        'respuesta_xml': respuesta_xml,
        'mensaje_enviado': mensaje_enviado
    }
    return render(request, 'peticiones.html', context)

# Vista para resetear la base de datos
def reset_bd(request):
    if request.method == 'POST':
        response = requests.post('http://127.0.0.1:5000/reset')
        if response.status_code == 200:
            return render(request, 'index.html', {'resultados': 'Base de datos reseteada', 'entrada': ''})  # Reiniciar entrada
        else:
            return HttpResponse(f"Error al resetear la base de datos: {response.text}", status=response.status_code)


def resumen_fecha(request):
    empresas = []
    fechas = []
    data = None
    fecha = None
    empresa = None

    # Obtener la lista de empresas
    try:
        response = requests.get('http://127.0.0.1:5000/empresas')
        response.raise_for_status()
        empresas = response.json().get('empresas', [])
    except requests.exceptions.RequestException as e:
        return HttpResponse(f"Error al obtener la lista de empresas: {str(e)}", status=400)

    # Obtener la lista de fechas
    try:
        response = requests.get('http://127.0.0.1:5000/fechas')
        response.raise_for_status()
        fechas = response.json().get('fechas', [])
    except requests.exceptions.RequestException as e:
        return HttpResponse(f"Error al obtener la lista de fechas: {str(e)}", status=400)

    if request.method == 'POST':
        fecha = request.POST.get('fecha')
        empresa = request.POST.get('empresa')

        # Enviar solicitud al backend Flask
        try:
            response = requests.post('http://127.0.0.1:5000/resumen_fecha', json={'fecha': fecha, 'empresa': empresa})
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            return HttpResponse(f"Error al obtener el resumen: {str(e)}", status=400)

    return render(request, 'resumen_fecha.html', {'data': data, 'fecha': fecha, 'empresa': empresa, 'empresas': empresas, 'fechas': fechas})


# Vista para la página de Peticiones
def peticiones(request):
    return render(request, 'peticiones.html', {'resultados': ''})  # Reiniciar entrada y resultados

# Vista para la página de Ayuda
def ayuda(request):
    return render(request, 'ayuda.html', {'entrada': '', 'resultados': ''})  # Reiniciar entrada y resultados
