#include <AccelStepper.h>

// --- PINES ---
#define X_STEP_PIN 2
#define X_DIR_PIN 5
#define Y_STEP_PIN 3
#define Y_DIR_PIN 6
#define ENABLE_PIN 8
#define X_LIMIT_PIN 9
#define Y_LIMIT_PIN 10

// --- CONFIGURACIÓN MECÁNICA ---
const float STEPS_PER_MM = 6400.0;
const int X_HOME_DIR = 1;
const int Y_HOME_DIR = 1;

// --- Configuración de Parámetros ---
const int VEL_BUSQUEDA = 5000;    // Velocidad rápida
const int VEL_AJUSTE = 500;      // Velocidad lenta para precisión
const int PASOS_RETROCESO = 3400; // Un poco de espacio para reintentar
const long PASOS_OFFSET = 6400;   // Tu configuración de 1.0 mm      

// Velocidades seguras para Arduino Uno (Máx ~4000-5000)
const float MAX_SPEED_SAFE = 5000.0; 
const float ACCEL_SAFE = 10000.0;

AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);

// --- VARIABLES DE ESTADO ---
bool waitingForCont = false;
bool sweepActive = false;
bool homedOK = false;
String cmdBuffer = "";

// Variables para el barrido (State Machine)
float s_xmax, s_ymax, s_res;
int s_ix = 0, s_iy = 0, s_nx = 0, s_ny = 0;
bool movingToPoint = false;

void setup() {
  Serial.begin(9600);
  pinMode(ENABLE_PIN, OUTPUT);
  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);
  digitalWrite(ENABLE_PIN, HIGH); // Apagados al inicio

  stepperX.setMaxSpeed(MAX_SPEED_SAFE);
  stepperX.setAcceleration(ACCEL_SAFE);
  stepperY.setMaxSpeed(MAX_SPEED_SAFE);
  stepperY.setAcceleration(ACCEL_SAFE);

  delay(500);
  Serial.println("READY");
}

void loop() {
  // 1. Leer Serial
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      cmdBuffer.trim();
      if (cmdBuffer.length() > 0) processCommand(cmdBuffer);
      cmdBuffer = "";
    } else {
      cmdBuffer += c;
    }
  }

  // 2. Lógica del Barrido (Máquina de Estados)
  if (sweepActive && !waitingForCont) {
    if (!movingToPoint) {
      // Calcular siguiente punto
      if (s_iy >= s_ny) {
        finishSweep();
      } else {
        // Lógica de zigzag
        int target_ix = (s_iy % 2 == 0) ? s_ix : (s_nx - 1 - s_ix);
        float tx = target_ix * s_res;
        float ty = s_iy * s_res;
        
        startMoveTo(tx, ty);
        movingToPoint = true;
        
        // Informar a Python
        Serial.print("POS "); Serial.print(tx, 3); Serial.print(" "); Serial.println(ty, 3);
      }
    } else {
      // Estamos moviéndonos. ¿Ya llegamos?
      if (stepperX.distanceToGo() == 0 && stepperY.distanceToGo() == 0) {
        movingToPoint = false;
        delay(100); // Estabilización
        Serial.println("LASER");
        waitingForCont = true; // Pausa hasta que Python diga CONT
        
        // Incrementar índices
        s_ix++;
        if (s_ix >= s_nx) {
          s_ix = 0;
          s_iy++;
        }
      }
    }
  }

  // 3. Ejecutar pasos de motor (SIEMPRE se llama)
  stepperX.run();
  stepperY.run();
}

void processCommand(String cmd) {
  if (cmd == "CONT") {
    waitingForCont = false;
  } 
  else if (cmd == "ABORT") {
    finishSweep();
    stepperX.stop(); stepperY.stop();
  }
  else if (cmd == "HOME") {
    digitalWrite(ENABLE_PIN, LOW);
    homeAll();
    Serial.println("HOMED");
  }
  else if (cmd.startsWith("SWEEP")) {
    // Parseo simple
    int s1 = cmd.indexOf(' ', 6);
    int s2 = cmd.indexOf(' ', s1 + 1);
    if (s1 != -1 && s2 != -1) {
      s_xmax = cmd.substring(6, s1).toFloat();
      s_ymax = cmd.substring(s1 + 1, s2).toFloat();
      s_res = cmd.substring(s2 + 1).toFloat();
      
      s_nx = (int)(s_xmax / s_res) + 1;
      s_ny = (int)(s_ymax / s_res) + 1;
      s_ix = 0; s_iy = 0;
      sweepActive = true;
      waitingForCont = false;
      movingToPoint = false;
      digitalWrite(ENABLE_PIN, LOW);
      Serial.println("DBG SWEEP_START");
    }
  }
}

void startMoveTo(float x, float y) {
  // Invertimos dirección según tu hardware (-1 * steps)
  stepperX.moveTo((long)(x * STEPS_PER_MM * -X_HOME_DIR));
  stepperY.moveTo((long)(y * STEPS_PER_MM * -Y_HOME_DIR));
}

void finishSweep() {
  sweepActive = false;
  waitingForCont = false;
  Serial.println("OK");
}

void homeAll() {
  // --- EJE X ---
  // 1. Busqueda rápida del switch
  stepperX.setMaxSpeed(VEL_BUSQUEDA);
  stepperX.setAcceleration(5000); // Asegura buena respuesta
  stepperX.moveTo(100000L * X_HOME_DIR);
  while(digitalRead(X_LIMIT_PIN) == HIGH) stepperX.run();
  stepperX.stop();
  
  // 2. Alejarse un poco para el ajuste fino
  stepperX.move(-PASOS_RETROCESO * X_HOME_DIR);
  while(stepperX.distanceToGo() != 0) stepperX.run();

  // 3. Ajuste fino (Velocidad lenta)
  stepperX.setMaxSpeed(VEL_AJUSTE);
  stepperX.moveTo(100000L * X_HOME_DIR);
  while(digitalRead(X_LIMIT_PIN) == HIGH) stepperX.run();
  stepperX.stop();

  // 4. Moverse al Offset de 1.0mm (6400 pasos)
  // Cambiamos a velocidad rápida para este movimiento
  stepperX.setMaxSpeed(VEL_BUSQUEDA);
  stepperX.move(-PASOS_OFFSET * X_HOME_DIR); 
  while(stepperX.distanceToGo() != 0) stepperX.run();

  // 5. Establecer este punto como el CERO real
  stepperX.setCurrentPosition(0);

  // --- EJE Y ---
  // 1. Busqueda rápida del switch
  stepperY.setMaxSpeed(VEL_BUSQUEDA);
  stepperY.setAcceleration(5000);
  stepperY.moveTo(100000L * Y_HOME_DIR);
  while(digitalRead(Y_LIMIT_PIN) == HIGH) stepperY.run();
  stepperY.stop();

  // 2. Alejarse un poco
  stepperY.move(-PASOS_RETROCESO * Y_HOME_DIR);
  while(stepperY.distanceToGo() != 0) stepperY.run();

  // 3. Ajuste fino
  stepperY.setMaxSpeed(VEL_AJUSTE);
  stepperY.moveTo(100000L * Y_HOME_DIR);
  while(digitalRead(Y_LIMIT_PIN) == HIGH) stepperY.run();
  stepperY.stop();

  // 4. Moverse al Offset de 1.0mm (6400 pasos)
  stepperY.setMaxSpeed(VEL_BUSQUEDA);
  stepperY.move(-PASOS_OFFSET * Y_HOME_DIR);
  while(stepperY.distanceToGo() != 0) stepperY.run();

  // 5. Establecer este punto como el CERO real
  stepperY.setCurrentPosition(0);

  homedOK = true;
  // Dejar las velocidades listas para el trabajo normal
  stepperX.setMaxSpeed(MAX_SPEED_SAFE);
  stepperY.setMaxSpeed(MAX_SPEED_SAFE);
}