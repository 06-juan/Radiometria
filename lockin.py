import pyvisa

def get_measurements(resource_name='GPIB0::8::INSTR', timeout=5000):
    """
    Conecta al SR830 vía GPIB y retorna las mediciones actuales (X, Y, R, φ).
    
    Args:
        resource_name (str): Nombre del recurso VISA, ej. 'GPIB0::8::INSTR'.
        timeout (int): Timeout en ms para la consulta.
    
    Returns:
        dict: {'X': float, 'Y': float, 'R': float, 'phi': float} o None si hay error.
    
    Ejemplo:
        mediciones = get_measurements()
        if mediciones:
            print(mediciones['R'])
    """
    rm = pyvisa.ResourceManager('')
    
    try:
        inst = rm.open_resource(resource_name)
        inst.timeout = timeout
        
        # Verifica conexión
        idn = inst.query('*IDN?').strip()
        if 'SR830' not in idn:
            raise ValueError(f"Instrumento no es SR830. IDN: {idn}")
        
        # Obtiene X, Y, R, φ en una sola consulta
        snap_response = inst.query('SNAP? 1,2,3,4').strip()
        values = [float(val) for val in snap_response.split(',')]
        if len(values) != 4:
            raise ValueError(f"Respuesta SNAP inválida: {snap_response}")
        
        measurements = {
            'X': values[0],      # Componente en fase (V)
            'Y': values[1],      # Componente en cuadratura (V)
            'R': values[2],      # Magnitud (V)
            'phi': values[3]     # Fase (grados)
        }
        
        return measurements
        
    except pyvisa.VisaIOError as e:
        print(f"Error de comunicación VISA: {e}")
        return None
    except Exception as e:
        print(f"Error general: {e}")
        return None
    finally:
        if 'inst' in locals():
            inst.close()
        rm.close()

if __name__ == "__main__":
    mediciones = get_measurements()
    if mediciones:
        print("Mediciones actuales:")
        for key, value in mediciones.items():
            print(f"{key}: {value:.6e}")