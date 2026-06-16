# constants.py

# Configuración Serial
PORT = 'COM3'
BAUDRATE = 9600

# Límites físicos absolutos de la mesa (en milímetros)
X_MIN = 0.0
X_MAX = 150.0  # Ajusta al tamaño máximo de tu eje X
Y_MIN = 0.0
Y_MAX = 150.0  # Ajusta al tamaño máximo de tu eje Y

# Configuración del control manual (JOG)
DEFAULT_STEP = 5.0   # Movimiento inicial por clic (mm)
STEP_MIN = 1         # Deslizador entero mínimo (corresponde a 0.1 mm si usamos factor)
STEP_MAX = 500       # Deslizador entero máximo (corresponde a 50.0 mm)
STEP_FACTOR = 10.0   # Factor de división para flotantes en el QSlider