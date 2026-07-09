08/07/26 (2)
Refactor de UI y fix de lógica de medición:
- Pestañas reordenadas: "Movimiento" es la primera pestaña. Al iniciar un
  barrido (3D o Cruz), la UI cambia automáticamente a la pestaña correspondiente.
- Botones "Conectar y Home" y "Emergency Stop" eliminados de movemesa.py
  (redundantes con el panel lateral).
- Botón "Stop / Desconectar" ahora funciona en modo simulación: resetea
  sim_mode, oculta el badge y habilita reconexión al hardware real.
- Slider de resolución: rango 0.01–1.00 mm con decimales (QDoubleValidator),
  factor=100 interno. Los sliders X, Y y Frecuencia siguen siendo enteros.
- Sliders X/Y ahora llegan hasta TableXY.X_MAX/Y_MAX (100 mm) directamente.
- Lógica de área de barrido corregida: los sliders definen el tamaño del
  barrido, NO la posición final. El origin_offset solo desplaza el inicio.
  Se valida que (origen + barrido) no exceda los límites físicos de la mesa.
- Inversión de ejes en flechas del control manual: positivo = izquierda y abajo.
- MoveWorker detecta si la mesa es simulador (sin atributo 'ser') y usa
  move_to() en lugar del protocolo serial Arduino.
- Protección en Grafica3DRealTime.inicializar_malla: valores mínimos de
  x_max=0.1, y_max=0.1, res=0.001 para evitar ZeroDivisionError en GLGridItem.

08/07/26
Modo simulación para debugging sin hardware. Se implementan
MesaXYSimulator y SR830Simulator que imitan la interfaz de los
drivers reales con datos sintéticos y ruido gaussiano. El usuario
puede forzar el modo con --sim o activarlo desde un diálogo cuando
falla la conexión (botones "Iniciar Simulación" / "Cerrar"). Se
aplicaron técnicas de clean code: docstrings descriptivos en todos
los módulos principales, nomenclatura consistente, corrección de
bugs de atributos (DELAYAUTOGAIN → DELAY_AUTO_GAIN), documentación
del protocolo de comunicación serial, y separación de responsabilidades.
También se fixeó sys.path → sys.argv en main.py para QApplication.

5/02/26
ponemos los ejes con configuracion logaritmica y lineal para un mejor analisis de los datos en las graficas 2d, añadimos una funcion al arduino para un futuro barrido multipunto de frecuencia y promediar en el tamaño de la muestra, esta funcion se podria reutilizar en el marcado del area, con un  voltaje de  1.6  o similar para que el laser alumbre super bajo.

25/02/26
version preliminar de barrido en frecuencia, para identificar la frecuencia idonea luego de analisis de la grafica

20/02/26
convinacion de botones conectar y home, ya no era necesario tener dos botones aparte

17/02/26
He añadido numeros a los ejes, automatice la escala, camara y gire 90° la mesa para que no se choque con el tubo de opticas, he implementado un guardado de datos con SQL/duckdb porque estoy estudiando este sistema en Fisica Computacional 1 y poder almacenar distintas mediciones en un solo documento como tablas.

13/02/26
He implementado el pyqtgraph para poder visualizar las mediciones que va tomando el lockin en tiempo real, y no teniendo que esperar hasta el final de la medicion para medir.

12/02/26
He usado el lockin para marcar el ritmo de la medicion (modular el laser), la otra opcion es el arduino pero no es ni de certa igual de preciso.

11/02/26
He usado un Arduino para la mesa xy debido a la facil implementacion con el shield y su code friendly IDE.

09/02/26
He usado una maquina virtual de oracle con su extension de puertos serial, usando una iso y una clave filtrada en internet de windows xp 32bit, para usar el sofware que controla el laser debido a que fue diseñado para una arquitectura de 32bit y los computadores en el futuro (2026) ya funcionan a 64bit.

11/11/25
He diseñado soportes en 3d por la facilidad de testeo y implementacion, ademas de tener una impresora 3d a disposicion, los motores estan "flotando" porque asi nos evitamos el problea que habia con la mesa anterior el motor chocaba y se trababa, no fue idea mia simplemente tome inspiracion de un microscopio que usaron anteriormente haciendo que la mesa se mueva junto con el motor.