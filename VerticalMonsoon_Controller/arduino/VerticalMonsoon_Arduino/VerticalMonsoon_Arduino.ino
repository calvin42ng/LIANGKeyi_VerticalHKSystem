#include <Servo.h>

// Vertical Monsoon: Arduino Uno/Nano compatible
// Input: serial "ON\n" or "OFF\n" at 115200 baud.
// Servos require an EXTERNAL regulated 5V supply; connect grounds together.
// Fan/humidifier outputs drive MOSFET/relay MODULE INPUTS, never loads directly.

const byte SERVO_02_PIN = 3;
const byte SERVO_03_PIN = 5;
const byte SERVO_04_PIN = 6;
const byte FAN_PIN = 8;
const byte HUMIDIFIER_PIN = 9;

// Set false for relay modules that turn ON when input is LOW.
const bool OUTPUT_ACTIVE_HIGH = true;

// Calibrate these angles for your real flap geometry BEFORE attaching linkage.
const int CLOSED_02 = 10, OPEN_02 = 75;
const int CLOSED_03 = 10, OPEN_03 = 85;
const int CLOSED_04 = 10, OPEN_04 = 90;

const unsigned long SERVO_STEP_MS = 25;
const unsigned long COMMAND_TIMEOUT_MS = 3500;
const unsigned long ACTUATOR_START_DELAY_MS = 700;

Servo servo02, servo03, servo04;
int pos02 = CLOSED_02, pos03 = CLOSED_03, pos04 = CLOSED_04;
bool desiredOn = false;
unsigned long lastCommandMs = 0, lastServoStepMs = 0, activationMs = 0;
char inputBuffer[16];
byte inputLen = 0;

void setOutput(byte pin, bool on) {
  digitalWrite(pin, (on == OUTPUT_ACTIVE_HIGH) ? HIGH : LOW);
}
int moveToward(int current, int target) {
  if (current < target) return current + 1;
  if (current > target) return current - 1;
  return current;
}
void handleCommand(const char* cmd) {
  if (strcmp(cmd, "ON") == 0) {
    if (!desiredOn) activationMs = millis();
    desiredOn = true;
    lastCommandMs = millis();
    Serial.println("ACK ON");
  } else if (strcmp(cmd, "OFF") == 0) {
    desiredOn = false;
    lastCommandMs = millis();
    Serial.println("ACK OFF");
  }
}
void setup() {
  pinMode(FAN_PIN, OUTPUT);
  pinMode(HUMIDIFIER_PIN, OUTPUT);
  setOutput(FAN_PIN, false);
  setOutput(HUMIDIFIER_PIN, false);
  Serial.begin(115200);
  servo02.attach(SERVO_02_PIN);
  servo03.attach(SERVO_03_PIN);
  servo04.attach(SERVO_04_PIN);
  servo02.write(pos02);
  servo03.write(pos03);
  servo04.write(pos04);
  lastCommandMs = millis();
}
void loop() {
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (inputLen > 0) {
        inputBuffer[inputLen] = '\0';
        handleCommand(inputBuffer);
        inputLen = 0;
      }
    } else if (inputLen < sizeof(inputBuffer) - 1) {
      inputBuffer[inputLen++] = ch;
    } else {
      inputLen = 0;
    }
  }

  // Safety: return to OFF if Python stops sending commands.
  if (millis() - lastCommandMs > COMMAND_TIMEOUT_MS) desiredOn = false;

  if (millis() - lastServoStepMs >= SERVO_STEP_MS) {
    lastServoStepMs = millis();
    pos02 = moveToward(pos02, desiredOn ? OPEN_02 : CLOSED_02);
    pos03 = moveToward(pos03, desiredOn ? OPEN_03 : CLOSED_03);
    pos04 = moveToward(pos04, desiredOn ? OPEN_04 : CLOSED_04);
    servo02.write(pos02);
    servo03.write(pos03);
    servo04.write(pos04);
  }

  // Start fan and humidifier after flaps have begun opening.
  bool outputsOn = desiredOn && (millis() - activationMs >= ACTUATOR_START_DELAY_MS);
  setOutput(FAN_PIN, outputsOn);
  setOutput(HUMIDIFIER_PIN, outputsOn);
}
