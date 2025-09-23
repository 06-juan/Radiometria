Control de Mesa XY con Lock-in Amplifier (SR830)
================================================

1. Descripción general
----------------------

Este sistema integra una mesa XY motorizada controlada por Arduino y un lock-in amplifier Stanford Research SR830 para realizar barridos espaciales de una señal medida.  
La comunicación se realiza mediante:
- USB/Serial entre PC y Arduino (control de motores).  
- GPIB entre PC y SR830 (mediciones en fase/cuadratura).  

El software en Python coordina el movimiento, adquiere datos y genera visualizaciones 3D de las magnitudes medidas.

2. Estructura de archivos
-------------------------

graficar.py        -> Funciones de graficación 3D (X, Y, R, φ)  
lockin.py          -> Comunicación con lock-in SR830 vía PyVISA  
mesaxy.py          -> Clase MesaXY: control, barrido y adquisición  
MesaXYSerial.ino   -> Firmware Arduino para control de motores  
requirements.txt   -> Dependencias de Python  
README.txt         -> Documentación técnica  

3. Dependencias de software
---------------------------

Python:
- Python >= 3.8
- Instalar dependencias con:

    pip install -r requirements.txt

Dependencias incluidas:
- numpy
- matplotlib
- pyvisa
- pyserial

Arduino:
- IDE de Arduino 1.8.x o Arduino IDE 2.x
- Librerías estándar (Serial).
- Si se emplean drivers de motores adicionales (ej. AccelStepper), deben instalarse previamente en el IDE.

Controladores GPIB (National Instruments):
- Para que pyvisa detecte el SR830 mediante GPIB es necesario instalar NI-VISA.
- Descargar desde la página oficial de National Instruments:
  https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html
- Es obligatorio instalar los drivers de National Instruments:
  * NI-VISA
  * NI-488.2 (controlador GPIB)
- Ambos pueden descargarse e instalarse desde NI Package Manager.
- Instalar y reiniciar el sistema antes de ejecutar los scripts de Python.

4. Configuración del hardware
-----------------------------

Conexiones:
- Arduino -> PC: USB (puerto serie).
- Mesa XY: conectada a los pines de control definidos en MesaXYSerial.ino.
- Lock-in SR830 -> PC: mediante GPIB (recomendado adaptador GPIB-USB National Instruments).

Parámetros clave:
- Puerto serie Arduino: configurable en mesaxy.py (COM6 en Windows, /dev/ttyUSB0 en Linux).
- Dirección VISA del lock-in: definida en lockin.py (GPIB0::8::INSTR por defecto).

5. Procedimiento de operación
-----------------------------

1. Programación del Arduino
   - Abrir MesaXYSerial.ino en el IDE.
   - Seleccionar placa y puerto.
   - Compilar y cargar firmware.
   - Al iniciar, el Arduino enviará READY por puerto serie.

2. Inicialización en Python
   - Ejecutar mesaxy.py.
   - Verificar la conexión con Arduino (PING -> PONG).
   - Habilitar motores (EN_ON).
   - Realizar homing (HOME).

3. Adquisición de datos
   - Definir barrido con sweep_and_measure(x_max, y_max, res).
   - El res minimo para la configuracion del laboratorio es de 5 micrometros
   - El Arduino mueve la mesa a cada punto y notifica con POS x y.
   - En cada posición, Python consulta al lock-in mediante el comando SNAP? 1,2,3,4.
   - Se almacenan X, Y, R, φ.

4. Visualización de resultados
   - Ejecutar plot_3d() desde mesaxy.py.
   - Se generan cuatro superficies 3D (X, Y, R, φ).

6. Comandos implementados (Arduino ↔ Python)
--------------------------------------------

- READY: enviado al inicio, confirma inicialización.  
- PING -> PONG: verificación de comunicación.  
- EN_ON / EN_OFF: habilitar/deshabilitar motores.  
- HOME: mover a posición de referencia.  
- SWEEP x_max y_max res: iniciar barrido.  
- POS x y: Arduino reporta posición actual.  
- CONT: autorización desde Python para continuar al siguiente punto.  
- OK: finalización de barrido.  
- ERR ...: error en ejecución.  
- DBG ...: mensajes de depuración.  

