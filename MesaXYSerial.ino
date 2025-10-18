#include <AccelStepper.h>

// Definición de pines
#define X_STEP_PIN 2
#define X_DIR_PIN 5
#define Y_STEP_PIN 3
#define Y_DIR_PIN 6
#define ENABLE_PIN 8
#define X_LIMIT_PIN 9
#define Y_LIMIT_PIN 10

// Configuración de pasos por milímetro (ajustar según hardware)
const float STEPS_PER_MM_X = 6400.0; // 1/16 microstepping
const float STEPS_PER_MM_Y = 6400.0;

// Parámetros de homing
const float X_OFFSET_MM = 1.0;
const float Y_OFFSET_MM = 1.0;
const int X_HOME_DIR = 1;
const int Y_HOME_DIR = 1;
const float COARSE_SPEED_X = 1600.0; // pasos/s
const float FINE_SPEED_X = 800.0;   // pasos/s
const float COARSE_SPEED_Y = 1600.0; // pasos/s
const float FINE_SPEED_Y = 800.0;   // pasos/s
const float HOME_ACCEL_X = 3200.0;  // pasos/s^2
const float HOME_ACCEL_Y = 3200.0;  // pasos/s^2

// Configuración inicial de velocidad y aceleración (en pasos/s y pasos/s²)
const float MAX_SPEED = 1000.0; // Velocidad máxima inicial
const float ACCELERATION = 6400.0; // Aceleración moderada

// Direcciones para coordenadas positivas (lejos del home): opuesto al homeDir
const int POS_DIR_X = -X_HOME_DIR;  // Multiplicador para pasos positivos en X (ajustar si es necesario)
const int POS_DIR_Y = -Y_HOME_DIR;  // Multiplicador para pasos positivos en Y (ajustar si es necesario)

// Instancias de AccelStepper
AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);

// Variables globales
float maxSpeed = MAX_SPEED; // Velocidad ajustable
bool motorsEnabled = false;
bool waitingForCont = false;
bool sweepActive = false;
bool homedOK = false; // Estado de homing

void setup() {
  Serial.begin(9600);
  pinMode(ENABLE_PIN, OUTPUT);
  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);
  digitalWrite(ENABLE_PIN, HIGH); // Drivers desactivados (ENABLE es activo bajo)

  // Configurar motores
  stepperX.setMaxSpeed(MAX_SPEED);
  stepperX.setAcceleration(ACCELERATION);
  stepperY.setMaxSpeed(MAX_SPEED);
  stepperY.setAcceleration(ACCELERATION);

  Serial.println("READY");
}

void loop() {
  static String cmdBuffer = "";
  if (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      cmdBuffer.trim();
      if (cmdBuffer.length() > 0) {
        processCommand(cmdBuffer);
      }
      cmdBuffer = "";
    } else {
      cmdBuffer += c;
    }
  }

  // Ejecutar movimientos si no está esperando CONT
  if (!waitingForCont) {
    stepperX.run();
    stepperY.run();
  }
}

void processCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
  } else if (cmd == "EN_ON") {
    digitalWrite(ENABLE_PIN, LOW); // Habilitar drivers
    motorsEnabled = true;
    Serial.println("OK");
  } else if (cmd == "EN_OFF") {
    digitalWrite(ENABLE_PIN, HIGH); // Deshabilitar drivers
    motorsEnabled = false;
    Serial.println("OK");
  } else if (cmd == "HOME") {
    if (!motorsEnabled) {
      digitalWrite(ENABLE_PIN, LOW);
      motorsEnabled = true;
    }
    homeAll();
    digitalWrite(ENABLE_PIN, HIGH);
    motorsEnabled = false;
    Serial.println("OK");
  } else if (cmd == "CONT" && waitingForCont) {
    waitingForCont = false;
    Serial.println("DBG CONT received");
  } else if (cmd == "ABORT" && sweepActive) {
    sweepActive = false;
    waitingForCont = false;
    stepperX.stop();
    stepperY.stop();
    Serial.println("OK");
  } else if (cmd.startsWith("SPEED")) {
    float speed;
    if (parseFloat(cmd, 5, speed) && speed > 0) {
      maxSpeed = speed;
      stepperX.setMaxSpeed(speed);
      stepperY.setMaxSpeed(speed);
      Serial.println("OK");
    } else {
      Serial.println("ERR Invalid speed");
    }
  } else if (cmd.startsWith("TESTMOVE")) {
    float x, y;
    if (parseTwoFloats(cmd, 8, x, y)) {
      if (!homedOK) {
        Serial.println("ERR Not homed");
        return;
      }
      moveToMM(x, y);
      Serial.println("OK");
    } else {
      Serial.println("ERR Invalid TESTMOVE parameters");
    }
  } else if (cmd.startsWith("SWEEP")) {
    float x_max, y_max, res;
    if (parseThreeFloats(cmd, 5, x_max, y_max, res) && x_max > 0 && y_max > 0 && res > 0) {
      if (!homedOK) {
        Serial.println("ERR Not homed");
        return;
      }
      if (!motorsEnabled) {
        digitalWrite(ENABLE_PIN, LOW);
        motorsEnabled = true;
      }
      runSweep(x_max, y_max, res);
    } else {
      Serial.println("ERR Invalid SWEEP parameters");
    }
  } else {
    Serial.println("ERR Unknown command");
  }
}

bool parseFloat(String line, int start, float &value) {
  line.remove(0, start);
  line.trim();
  value = line.toFloat();
  return line.length() > 0 && value >= 0;
}

bool parseTwoFloats(String line, int start, float &x, float &y) {
  line.remove(0, start);
  line.trim();
  int s1 = line.indexOf(' ');
  if (s1 == -1) return false;
  x = line.substring(0, s1).toFloat();
  y = line.substring(s1 + 1).toFloat();
  return x >= 0 && y >= 0;
}

bool parseThreeFloats(String line, int start, float &x_max, float &y_max, float &res) {
  line.remove(0, start);
  line.trim();
  int s1 = line.indexOf(' ');
  int s2 = line.indexOf(' ', s1 + 1);
  if (s1 == -1 || s2 == -1) return false;
  x_max = line.substring(0, s1).toFloat();
  y_max = line.substring(s1 + 1, s2).toFloat();
  res = line.substring(s2 + 1).toFloat();
  return x_max > 0 && y_max > 0 && res > 0;
}

void moveToMM(float x_mm, float y_mm) {
  long x_steps = (long)(x_mm * STEPS_PER_MM_X * POS_DIR_X);
  long y_steps = (long)(y_mm * STEPS_PER_MM_Y * POS_DIR_Y);
  Serial.print("DBG Moving to steps: ");
  Serial.print(x_steps);
  Serial.print(", ");
  Serial.println(y_steps);

  stepperX.moveTo(x_steps);
  stepperY.moveTo(y_steps);

  while (stepperX.distanceToGo() != 0 || stepperY.distanceToGo() != 0) {
    stepperX.run();
    stepperY.run();
  }
}

void stepAndPause(float x, float y) {
  moveToMM(x, y);
  Serial.print("POS ");
  Serial.print(x, 3);
  Serial.print(" ");
  Serial.println(y, 3);

  waitingForCont = true;
  while (waitingForCont && sweepActive) {
    if (Serial.available()) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      processCommand(cmd);
    }
  }
}

void runSweep(float x_max, float y_max, float res) {
  sweepActive = true;
  int nx = (int)(x_max / res) + 1;
  int ny = (int)(y_max / res) + 1;
  Serial.print("DBG Sweep points: nx=");
  Serial.print(nx);
  Serial.print(", ny=");
  Serial.println(ny);

  for (int j = 0; j < ny && sweepActive; j++) {
    if (j % 2 == 0) {
      for (int i = 0; i < nx && sweepActive; i++) {
        stepAndPause(i * res, j * res);
      }
    } else {
      for (int i = nx - 1; i >= 0 && sweepActive; i--) {
        stepAndPause(i * res, j * res);
      }
    }
  }
  if (sweepActive) {
    Serial.println("OK");
  }
  sweepActive = false;
  waitingForCont = false;
}

void waitUntilDone(AccelStepper &s) {
  while (s.distanceToGo() != 0) {
    s.run();
  }
}

void homeAxis(AccelStepper &st, int limitPin, float stepsPerMM, float offsetMM,
              int homeDir, float coarseSpeed, float fineSpeed, float accel) {
  long oneMM = (long)round(stepsPerMM/2); //0.5mm
  long offsetSteps = (long)round(offsetMM * stepsPerMM);
  int awayDir = -homeDir;

  // Asegurar aceleración
  st.setAcceleration(accel);

  // 1) Alejar 1 mm para liberar switch
  st.setMaxSpeed(coarseSpeed);
  st.move(awayDir * oneMM);
  waitUntilDone(st);
  delay(20);
  Serial.println("DBG Moved away 1 mm");

  // 2) Aproximación rápida
  st.setMaxSpeed(coarseSpeed);
  st.move(homeDir * 100000L); // Movimiento largo hacia el switch
  while (digitalRead(limitPin) == HIGH && st.distanceToGo() != 0) {
    st.run();
  }
  st.stop();
  waitUntilDone(st);
  Serial.println("DBG Coarse approach done");

  // 3) Retroceder 1 mm
  st.setMaxSpeed(coarseSpeed);
  st.move(awayDir * oneMM);
  waitUntilDone(st);
  delay(20);
  Serial.println("DBG Moved back 1 mm");

  // 4) Aproximación fina
  st.setMaxSpeed(fineSpeed);
  st.move(homeDir * 100000L);
  while (digitalRead(limitPin) == HIGH && st.distanceToGo() != 0) {
    st.run();
  }
  st.stop();
  waitUntilDone(st);
  Serial.println("DBG Fine approach done");

  // 5) Aplicar offset y fijar cero
  st.setMaxSpeed(coarseSpeed);
  st.move(awayDir * offsetSteps);
  waitUntilDone(st);
  st.setCurrentPosition(0);
  Serial.println("DBG Offset applied, position set to 0");
}

void homeAll() {
  Serial.println("DBG Starting homing");
  homeAxis(stepperX, X_LIMIT_PIN, STEPS_PER_MM_X, X_OFFSET_MM, X_HOME_DIR,
           COARSE_SPEED_X, FINE_SPEED_X, HOME_ACCEL_X);
  homeAxis(stepperY, Y_LIMIT_PIN, STEPS_PER_MM_Y, Y_OFFSET_MM, Y_HOME_DIR,
           COARSE_SPEED_Y, FINE_SPEED_Y, HOME_ACCEL_Y);
  homedOK = true;
  Serial.println("DBG Homing completed");
}