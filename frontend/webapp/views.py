from django.shortcuts import render
import requests
from django.http import HttpResponse
import xml.etree.ElementTree as ET
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# Variable global para almacenar los resultados de la última respuesta
last_result = None

# Vista para manejar la carga de archivos y mostrar el contenido
def clasificar(request):
    global last_result  # Asegúrate de que last_result sea accesible
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
        else:
            return HttpResponse(f"Error al clasificar los mensajes: {response.text}", status=response.status_code)

    # Si es un GET o no se ha enviado un archivo
    return render(request, 'index.html', {'resultados': resultados, 'entrada': entrada})


# Vista para consultar datos almacenados en la última respuesta
def consultar_datos(request):
    global last_result
    return render(request, 'peticiones.html', {'resultados': last_result})

# Nueva vista para el resumen de clasificación por fecha
def resumen_por_fecha(request):
    fecha = ''
    empresa = ''
    total_mensajes = 0
    total_positivos = 0
    total_negativos = 0
    total_neutros = 0

    if request.method == 'POST':
        fecha = request.POST.get('fecha')
        empresa = request.POST.get('empresa')

        # Lógica para filtrar resultados de la última respuesta
        if last_result:
            root = ET.fromstring(last_result)
            for mensaje in root.find('lista_mensajes').findall('mensaje'):
                # Extraer la fecha del mensaje
                lugar_y_fecha = mensaje.text.split('Lugar y fecha: ')[1].split('Usuario:')[0].strip()
                mensaje_fecha = datetime.strptime(lugar_y_fecha.split(', ')[1], '%d/%m/%Y %H:%M')

                # Verificar si la fecha coincide
                if mensaje_fecha.date().strftime('%d/%m/%Y') == fecha:
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
        'fecha': fecha,
        'empresa': empresa,
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
    respuesta_xml = ''
    
    if request.method == 'POST':
        # Obtener el mensaje XML del formulario
        mensaje_xml = request.POST.get('mensaje')
        
        # Convertir el mensaje XML a un elemento para su análisis
        try:
            root = ET.fromstring(mensaje_xml)
            mensaje_texto = root.find('mensaje').text.strip()
            
            # Extraer la información necesaria del mensaje
            lugar_fecha = mensaje_texto.split('Lugar y fecha: ')[1].split('Usuario:')[0].strip()
            fecha_str = lugar_fecha.split(', ')[1]
            red_social = mensaje_texto.split('Red social: ')[1].split('Hoy')[0].strip()
            usuario = mensaje_texto.split('Usuario: ')[1].split('Red social:')[0].strip()

            # Clasificación del mensaje
            palabras_positivas = 0
            palabras_negativas = 0
            clasificacion = clasificar_mensaje(root, sentimientos_positivos, sentimientos_negativos)

            # Contar palabras positivas y negativas
            palabras = mensaje_texto.lower().split()
            for palabra in palabras:
                if palabra in sentimientos_positivos:
                    palabras_positivas += 1
                elif palabra in sentimientos_negativos:
                    palabras_negativas += 1

            # Calcular sentimientos porcentuales
            total_palabras = palabras_positivas + palabras_negativas
            sentimiento_positivo = (palabras_positivas / total_palabras * 100) if total_palabras > 0 else 0
            sentimiento_negativo = (palabras_negativas / total_palabras * 100) if total_palabras > 0 else 0

            # Crear la respuesta XML
            respuesta = ET.Element('respuesta')
            ET.SubElement(respuesta, 'fecha').text = fecha_str
            ET.SubElement(respuesta, 'red_social').text = red_social
            ET.SubElement(respuesta, 'usuario').text = usuario
            
            empresas = ET.SubElement(respuesta, 'empresas')
            empresa_element = ET.SubElement(empresas, 'empresa', nombre='USAC')
            ET.SubElement(empresa_element, 'servicio').text = 'inscripción'  # Aquí puedes agregar más servicios según sea necesario

            ET.SubElement(respuesta, 'palabras_positivas').text = str(palabras_positivas)
            ET.SubElement(respuesta, 'palabras_negativas').text = str(palabras_negativas)
            ET.SubElement(respuesta, 'sentimiento_positivo').text = f"{sentimiento_positivo:.2f}%"
            ET.SubElement(respuesta, 'sentimiento_negativo').text = f"{sentimiento_negativo:.2f}%"
            ET.SubElement(respuesta, 'sentimiento_analizado').text = clasificacion

            # Convertir el XML de respuesta a cadena
            respuesta_xml = ET.tostring(respuesta, encoding='utf-8').decode('utf-8')
        
        except Exception as e:
            return HttpResponse(f"Error al procesar el mensaje: {str(e)}", status=400)

    return render(request, 'peticiones.html', {'respuesta_xml': respuesta_xml})

# Vista para resetear la base de datos
def reset_bd(request):
    if request.method == 'POST':
        response = requests.post('http://127.0.0.1:5000/reset')
        if response.status_code == 200:
            return render(request, 'index.html', {'resultados': 'Base de datos reseteada', 'entrada': ''})  # Reiniciar entrada
        else:
            return HttpResponse(f"Error al resetear la base de datos: {response.text}", status=response.status_code)

# Vista para la página de Peticiones
def peticiones(request):
    return render(request, 'peticiones.html', {'resultados': ''})  # Reiniciar entrada y resultados

# Vista para la página de Ayuda
def ayuda(request):
    return render(request, 'ayuda.html', {'entrada': '', 'resultados': ''})  # Reiniciar entrada y resultados
