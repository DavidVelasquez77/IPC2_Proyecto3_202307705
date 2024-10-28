from django.urls import path
from . import views

urlpatterns = [
    path('', views.clasificar, name='clasificar'),
    path('reset/', views.reset_bd, name='reset_bd'),
    path('peticiones/', views.peticiones, name='peticiones'),
    path('ayuda/', views.ayuda, name='ayuda'),
    path('consultar_datos/', views.consultar_datos, name='consultar_datos'),
    path('resumen_por_fecha/', views.resumen_por_fecha, name='resumen_por_fecha'),
    path('resumen_por_rango/', views.resumen_por_rango, name='resumen_por_rango'),
    path('reporte_pdf/', views.generar_reporte_pdf, name='generar_reporte_pdf'),  # Ruta para generar PDF
    path('prueba_mensaje/', views.prueba_mensaje, name='prueba_mensaje'),  # Ruta para prueba de mensaje
    path('resumen_fecha/', views.resumen_fecha, name='resumen_fecha'),  # Ruta para prueba de mensaje
    path('resumen_rango_fecha/', views.resumen_rango_fecha, name='resumen_rango_fecha'),  # Ruta para prueba de mensaje
]
