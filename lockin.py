import pyvisa

# Variable global para guardar la amplitud deseada (ej. 2.5V o 1V)
LASER_ON_VOLTAGE = 5  
LASER_OFF_VOLTAGE = 1.0 


class SR830:
    def __init__(self, resource_name='GPIB0::8::INSTR', timeout=5000):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout

    def set_amplitude(self, voltage):
        self.inst.write(f'SLVL {voltage}')

    def set_frequency(self, freq):
        self.inst.write(f'FREQ {freq}')

    def get_measurements(self):
        snap = self.inst.query('SNAP? 1,2,3,4').strip()
        x, y, r, phi = map(float, snap.split(','))
        return {'X': x, 'Y': y, 'R': r, 'phi': phi}

    def close(self):
        self.inst.close()
        self.rm.close()

if __name__ == "__main__":
    lockin = SR830()
    mediciones = lockin.get_measurements()
    if mediciones:
        print("Mediciones actuales:")
        for key, value in mediciones.items():
            print(f"{key}: {value:.6e}")